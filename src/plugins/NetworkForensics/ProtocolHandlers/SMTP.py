""" This module implements features specific for SMTP Processing """
# Michael Cohen <scudette@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.80.1 Date: Tue Jan 24 13:51:25 NZDT 2006$
# ******************************************************
#
# * This program is free software; you can redistribute it and/or
# * modify it under the terms of the GNU General Public License
# * as published by the Free Software Foundation; either version 2
# * of the License, or (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# ******************************************************
import pyflag.conf
config=pyflag.conf.ConfObject()
from pyflag.Scanner import *
import dissect,sys
import struct,sys,cStringIO
import pyflag.DB as DB
from pyflag.FileSystem import File
import pyflag.IO as IO
import pyflag.FlagFramework as FlagFramework
from NetworkScanner import *
import pyflag.Reports as Reports
import pyflag.logging as logging

class SMTPException(Exception):
    """ Raised if line is an invalid SMTP command """

class SMTP:
    """ Class managing the SMTP State """
    def __init__(self,fd,dbh,ddfs):
        self.fd=fd
        self.dbh = dbh
        self.ddfs = ddfs
        self.dispatcher = {
            'EHLO': self.NOOP,
            'MAIL': self.MAIL,
            'RCPT': self.RCPT,
            'DATA': self.DATA,
            'QUIT': self.NOOP,
            }
        self.mail_from = ''
        self.rcpt_to = []
        self.count=0

    def read_response(self):
        """ This reads the SMTP responses. SMTP is a little nicer than
        POP because we know when a multiline response is finished (by
        the presence of a code followed by space).
        """
        result = ''
        while 1:
            line = self.fd.readline()
            result+=line
            ## Responses with a space after the error code signify end
            ## of response:
            if line[3]==' ':
                return result

            try:
                int(line[:3])
            except:
                raise SMTPException("Invalid response %r" % line)

    def NOOP(self,args):
        self.read_response()

    def MAIL(self,args):
        self.mail_from = args
        self.read_response()
        logging.log(logging.VERBOSE_DEBUG,"Set mail from to %s " % self.mail_from)

    def RCPT(self,args):
        self.rcpt_to = args
        self.read_response()
        logging.log(logging.VERBOSE_DEBUG, "Set RCPT to %s" % self.rcpt_to)
        
    def DATA(self,args):
        result=self.read_response()
        if result[0]=='3':
            start = self.fd.tell()
            while 1:
                line = self.fd.readline()
                if not line or line=='.\r\n':
                    break
                
            end = self.fd.tell()
            length = end-start
            self.count += 1
            logging.log(logging.DEBUG,"Message starts at %s in stream and is %s long" % (start,length))
            return (self.count,"%s:%s" % (start,length))

    def parse(self):
        while 1:
            line = self.fd.readline().strip()

            ## Stop iteration if we are at the end
            if line=='':
                return

            ## If the line has an error code at the start, we are looking
            ## at a response.
            try:
                int(line[:3])
                continue
            except:
                pass

            tmp = line.split(":")
            command = tmp[0].split(" ")
            try:
                yield(self.dispatcher[command[0].upper()](tmp[-1]))
            except KeyError:
                logging.log(logging.DEBUG,"SMTP Command %r not implemented." % command[0])
        
class SMTPScanner(NetworkScanFactory):
    """ Collect information about SMTP transactions.

    This is an example of a scanner which uses packet dissection, as well as the result of the Stream reassembler.
    """
    default = True
    depends = ['StreamReassembler']

    def process_stream(self, stream, factories):
        forward_stream, reverse_stream = self.stream_to_server(stream, "SMTP")
        if not reverse_stream or not forward_stream: return

        combined_inode = "I%s|S%s/%s" % (stream.iosource.name, forward_stream, reverse_stream)
        logging.log(logging.DEBUG,"Openning %s for SMTP" % combined_inode)

        ## We open the file and scan it for emails:
        fd = self.fsfd.open(inode=combined_inode)
        p=SMTP(fd,self.dbh,self.fsfd)
        
        ## Iterate over all the messages in this connection
        for f in p.parse():
            if not f: continue
            
            ## Create the VFS node:
            path=self.fsfd.lookup(inode="I%s|S%s" % (stream.iosource.name, forward_stream))
            path=os.path.dirname(path)
            new_inode="%s|o%s" % (combined_inode,f[1])
            self.fsfd.VFSCreate(None, new_inode,
                                "%s/SMTP/Message_%s" % (path,f[0]),
                                mtime = stream.ts_sec
                                )
            
            ## Scan the new file using the scanner train. If
            ## the user chose the RFC2822 scanner, we will be
            ## able to understand this:
            self.scan_as_file(new_inode, factories)