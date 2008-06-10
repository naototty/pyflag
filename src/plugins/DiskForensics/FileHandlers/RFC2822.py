""" This scanner handles RFC2822 type messages, creating VFS nodes for all their children """
# Michael Cohen <scudette@users.sourceforge.net>
# David Collett <daveco@users.sourceforge.net>
# Gavin Jackson <gavz@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.87-pre1 Date: Tue Jun 10 13:18:41 EST 2008$
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
import os.path
import pyflag.pyflaglog as pyflaglog
import pyflag.Scanner as Scanner
import pyflag.Reports as Reports
import pyflag.DB as DB
import pyflag.conf
config=pyflag.conf.ConfObject()
import email, email.Utils,time
from pyflag.FileSystem import File


class RFC2822(Scanner.GenScanFactory):
    """ Scan RFC2822 Mail messages and insert record into email table"""
    default = True
    depends = ['TypeScan']
    
    def __init__(self,fsfd):
        Scanner.GenScanFactory.__init__(self,fsfd)
        dbh=DB.DBO(self.case)

    class Scan(Scanner.StoreAndScanType):
        types = [ 'message/rfc2822' ]

        def external_process(self,fd):		    
            count = 0
            try:
                a=email.message_from_file(fd)

                pyflaglog.log(pyflaglog.DEBUG,"Found an email message in %s" % self.inode)
		
		#Mysql is really picky about the date formatting
                date = email.Utils.parsedate(a.get('Date'))
                if not date:
                    raise Exception("No Date field in message - this is probably not an RFC2822 message at all.")

                dbh=DB.DBO(self.case)
                dbh.insert('email',
                           inode = self.inode,
                           _date =  "from_unixtime(%r)" % int(time.mktime(date)),
                           to = a.get('To'),
                           _from = "%r" % a.get('From'),
                           subject = a.get('Subject'))

                for part in a.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue

                    filename = part.get_filename()
                    data = part.get_payload(decode=1)

                    ## Sometimes the filename is specified in the
                    ## content-type header:
                    try:
                        for x,y in part.get_params():
                            if x =="name":
                                filename=y
                                break
                    except:
                        pass

                    if not filename: filename="Attachment %s" % count

                    ## Create the VFS node:
                    self.ddfs.VFSCreate(self.inode,"m%s" % count, filename,
                                        mtime = time.mktime(date), size=len(data)
                                        )

                    ## Now call the scanners on new file:
                    new_inode = "%s|m%s" % (self.inode,count)
                    fd=self.ddfs.open(inode=new_inode)
                    Scanner.scanfile(self.ddfs,fd,self.factories)
                    fd.close()
                    
                    count+=1
                    
            except Exception,e:
                pyflaglog.log(pyflaglog.DEBUG,"RFC2822 Scan: Unable to parse inode %s as an RFC2822 message (%s)" % (self.inode,e))
                
class RFC2822_File(File):
    """ A VFS Driver for reading mail attachments """
    specifier = 'm'

    def __init__(self, case, fd, inode):
        File.__init__(self, case, fd, inode)
        self.cache()

    def read(self, length=None):
        try:
            return File.read(self,length)
        except IOError:
           pass

        if self.readptr > 0:
            return ''
        
        self.fd.seek(0)
        a=email.message_from_file(self.fd)
        my_part = self.inode.split('|')[-1]
        attachment_number = int(my_part[1:])
        #print "attchement number %s" % attachment_number
        count = 0

        for part in a.walk():
            if part.get_content_maintype() == 'multipart':
                continue

            if count==attachment_number:
                self.message = part.get_payload(decode=1)
                self.readptr += len(self.message)
                #print "Returning %s" % part.get_payload()
                return self.message

            count+=1

        return ''
##class RFC2822CachedFile(CachedFile, RFC2822_File):
##    target_class = RFC2822_File
