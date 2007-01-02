# Michael Cohen <scudette@users.sourceforge.net>
# David Collett <daveco@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.82 Date: Sat Jun 24 23:38:33 EST 2006$
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
""" This modules add support for the ClamAV virus scanner to virus scan all files in the filesystem.

We provide a scanner class and a report to query the results of this scanner.
"""
import pyflag.FlagFramework as FlagFramework
import pyflag.conf
config=pyflag.conf.ConfObject()
import pyflag.FileSystem as FileSystem
import pyflag.Reports as Reports
import pyflag.DB as DB
import os.path
import pyflag.pyflaglog as pyflaglog
from pyflag.Scanner import *
from pyflag.TableObj import StringType, TimestampType, InodeType, FilenameType

class VScan:
    """ Singleton class to manage virus scanner access """
    ## May need to do locking in future, if libclamav is not reentrant.
    def scan(self,buf):
        """ Scan the given buffer, and return a virus name or 'None'"""
        import pyclamav
        
        try:
            ret = pyclamav.scanthis(buf)
            if ret == 0:
                return None
            elif ret[0] == 1:
                return ret[1]
        except Exception,e:
            pyflaglog.log(pyflaglog.WARNING, "Scanning Error: %s" % e)

class VirScan(GenScanFactory):
    """ Scan file for viruses """
    def __init__(self,fsfd):
        GenScanFactory.__init__(self, fsfd)        
        dbh=DB.DBO(self.case)
        dbh.execute(""" CREATE TABLE IF NOT EXISTS `virus` (
        `inode` varchar( 20 ) NOT NULL,
        `virus` tinytext NOT NULL )""")

        self.scanner=VScan()

    def destroy(self):
        dbh=DB.DBO(self.case)
        dbh.check_index('virus','inode')

    def reset(self, inode):
        GenScanFactory.reset(self, inode)
        dbh=DB.DBO(self.case)
        dbh.execute('delete from virus')

    class Scan(MemoryScan):
        def __init__(self, inode,ddfs,outer,factories=None,fd=None):
            MemoryScan.__init__(self, inode,ddfs,outer,factories,fd=fd)
            self.virus = None

        def process_buffer(self,buf):
            if not self.virus:
                self.virus=self.outer.scanner.scan(buf)

        def finish(self):
            dbh=DB.DBO(self.case)
            if self.virus:
                dbh.insert('virus',
                           inode=self.inode,
                           virus=self.virus)

class VirusScan(Reports.report):
    """ Scan Filesystem for Viruses using clamav"""
    name = "Virus Scan (clamav)"
    family = "Disk Forensics"
    description="This report will scan for viruses and display a table of viruses found"

    def display(self,query,result):
        result.heading("Virus Scan Results")
        dbh=self.DBO(query['case'])
        try:
            result.table(
                elements = [ InodeType('Inode','virus.inode',
                                       case=query['case']),
                             FilenameType(case=query['case']),
                             StringType('Virus Detected','virus') ],
                table='virus join file on virus.inode=file.inode ',
                case=query['case'],
                )
        except DB.DBError,e:
            result.para("Unable to display Virus table, maybe you did not run the virus scanner over the filesystem?")
            result.para("The error I got was %s"%e)
            
## UnitTests:
import unittest
import pyflag.pyflagsh as pyflagsh

class VirusScanTest(unittest.TestCase):
    test_case = "PyFlagTestCase"
    order = 20
    def test_scanner(self):
        """ Check the virus scanner works """
        dbh = DB.DBO(self.test_case)

        env = pyflagsh.environment(case=self.test_case)
        pyflagsh.shell_execv(env=env, command="scan",
                             argv=["*",'VirScan'])

        dbh.execute("select * from virus")
        row = dbh.fetch()

        ## We expect to pick this rootkit:
        self.assertEqual(row['inode'], "Itest|K15-0-0|Z46", "Unable to find Trojan.NTRootKit.044")
        
