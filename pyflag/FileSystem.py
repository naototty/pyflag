# ******************************************************
# Copyright 2004: Commonwealth of Australia.
#
# Developed by the Computer Network Vulnerability Team,
# Information Security Group.
# Department of Defence.
#
# Michael Cohen <scudette@users.sourceforge.net>
# David Collett <daveco@users.sourceforge.net>
#
# ******************************************************
#  Version: FLAG $Version: 0.75 Date: Sat Feb 12 11:21:40 EST 2005$
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

""" Module contains classes used to access filesystems loaded into the database.

When Flag loads a filesystem into the database, meta information about inodes, files and their allocation is stored within the database. The specific implementation of how this information is stored is abstracted here by use of the FileSystem object. The FileSystem object presents a well defined API to allow callers to query the case database about the filesystem.

The FileSystem class is an abstract class which is implemented as derived classes. Users of this class need to call the FS_Factory to get a concrete implementation. The implementation deals with representing the directory structure, and provides access to the files within the filesystem.

The File class abstracts an interface for accessing the data within a specific file inside the filesystem. Although this is very similar to the standard python file-like interface, there are some minor differences.

In order for callers to have access to a specific file on the filesystem, they need to instantiate a FileSystem object by using FS_Factory, and then ask this instance for a File object by using the FileSystem.open method. It is discouraged to instantiate a File object directly.

Virtual Filesystems (vfs) are also supported by this subsystem in order to support archives such as zip and pst files. Files within filesystems are uniquely identified in the flag databases by an inode string. The inode string can have multiple parts delimited by the pipe ('|') character indicating that a virtual filesystem is to be used on the file. The first letter in the part indicates the virtual filesystem to use, here is an example:
'D123|Z14' Here 'D' indicates the DBFS filesystem, Z indicates the Zip vfs.
This inode therefore refers to the 14 file in the zip archive contained in inode 123 of the DBFS filesystem. VFS
"""
import os,os.path
import pyflag.conf
config=pyflag.conf.ConfObject()

import pyflag.DB as DB
import pyflag.IO as IO
import pyflag.FlagFramework as FlagFramework
from pyflag.FlagFramework import normpath
import pyflag.Registry as Registry
import pyflag.logging as logging
import time
import math
import bisect
import zipfile
import cStringIO
import pyflag.Scanner as Scanner

class FileSystem:
    """ This is the base class for accessing file systems in PyFlag. This class is abstract and is here purely for documentation purposes """
    def __init__(self, case, table, fd):
        """ Constructor for creating an new filesystem object """
        pass
    
    def longls(self,path='/'):
        """ list directory content longly """
        pass

    def VFSCreate(self,root_inode,inode):
        """ This method creates inodes within the virtual filesystem.

        This facility allows callers to extend the VFS to include more virtual files.
        """

    def ls(self, path="/", dirs=None):
        """list directory contents"""
        pass

    def dent_walk(self, path='/'):
        """A generator which returns directory entries under the given path, one at a time """
        pass

    def lookup(self, path=None,inode=None):
        """return the inode number for the given path, or else the path for the given inode number. """
        pass

    def open(self, path=None, inode=None):
        """ Opens the specified path or Inode providing a file like object.

        This object can then be used to read data from the specified file.
        @note: Only files may be opened, not directories."""

        if not inode:
            inode = self.lookup(path)
        if not inode:
            raise IOError('Inode not found for file')

        if not path:
            path = self.lookup(inode=inode)
        if not path:
            raise IOError('File not found for inode')

        # open the file, first pass will generally be 'D' or 'M'
        # then any virtual file systems (vfs) will kick in
        parts = inode.split('|')
        sofar = [] # the inode part up to the file we want 
        retfd = self.fd
        for part in parts:
            sofar.append(part)
            try:
                retfd = Registry.VFS_FILES.vfslist[part[0]](self.case, self.table, retfd, '|'.join(sofar))
            except IndexError:
                raise IOError, "Unable to open inode: %s, no VFS" % part

        return retfd

    def istat(self, path=None, inode=None):
        """ return a dict with information (istat) for the given inode or path. """
        pass

    def isdir(self,directory):
        """ Returns 1 if directory is a directory, 0 otherwise """
        pass

    def exists(self,path):
        """ Returns 1 if path exists, 0 otherwise """
        pass

    def resetscanfs(self,callbacks):
        """ This is called to reset all the scanners. """
        
    def scanfs(self, callbacks):
        """ Read every file in fs, and call given scanner callbacks for each file.
        
        callbacks is a list of scanner classes derived from Scanner.GenScan. These classes
        have a process and finish methods.
        For each file, scanfs will create a new object of each of the given classes,
        then begin reading the file in buffers of (say) 1MB, each time calling the 
        process method of each of the new objects with the buffer just read.
        When all data has been read from the file, scanfs will call the finished method of each object.
        It will then start over with the next file.
        
        The purpose of this method is to do all analysis which must read file data in one place
        for performance, currently this includes file typing, file hashing and virus scanning"""
        pass
    

class DBFS(FileSystem):
    """ Class for accessing filesystems using data in the database """
    def __init__(self, case, table, fd):
        """ Initialise the DBFS object """
        self.fd = fd
        self.table = table
        self.case = case
        self.dbh = DB.DBO(case)
        try:
            self.dbh.execute("select value from meta_%s where name='block_size'",self.table);
            self.block_size = int(self.dbh.fetch()["value"])
        except:
            self.blocksize = 1024

    def VFSCreate(self,root_inode,inode,new_filename,**properties):
        """ Extends the DB filesystem to include further virtual filesystem entries.

        Note that there must be an appropriate VFS driver for the added inodes, or else they may not be viewable.
        @arg root_inode: The inode that will serve as the root for the new inode
        @arg inode: The proposed inode name for the new inode (without the | to the root_inode). This needs to be understood by the VFS driver.
        @arg new_filename: The prposed new filename for the VFS file. This may contain directories in which case sub directories will also be created.
        """
        ## filename is the filename in the filesystem for the zip file.
        if root_inode:
            filename = self.lookup(inode=root_inode)
        else:
            filename = '/'

        ## Check if the directories all exist properly:
        dirs = os.path.dirname(new_filename).split('/')
        name = os.path.basename(new_filename)

        for d in range(len(dirs)):
            if not dirs[d]: continue
            if d>0:
                path = normpath("%s/%s/" % (filename,"/".join(dirs[:d])))
            else:
                path = normpath("%s/" % filename)

            self.dbh.execute("select * from file_%s where path=%r and name=%r",(self.table, path, dirs[d]))
            if not self.dbh.fetch():
                if root_inode != None:
                    self.dbh.execute("insert into file_%s set path=%r,name=%r,status='alloc',mode='d/d',inode='%s|%s-'",(self.table,path,dirs[d],root_inode,inode))
                else:
                    self.dbh.execute("insert into file_%s set path=%r,name=%r,status='alloc',mode='d/d',inode='%s-'",(self.table,path,dirs[d],inode))

        path = normpath("%s/%s/" % (filename,os.path.dirname(new_filename)))
        ## Add the file itself to the file table
        if root_inode:
            self.dbh.execute("insert into file_%s set status='alloc',mode='r/r',inode='%s|%s',path=%r, name=%r",(self.table,root_inode,inode,normpath(path+'/'),name))
        else:
            self.dbh.execute("insert into file_%s set status='alloc',mode='r/r',inode='%s',path=%r, name=%r",(self.table,inode,normpath(path+'/'),name))

        ## Add the file to the inode table:
        extra = ','.join(["%s=%%r" % p for p in properties.keys()])
        if extra:
            extra=','+extra

        if root_inode!=None:
            self.dbh.execute("insert into inode_%s set inode='%s|%s'" + extra ,[self.table, root_inode,inode] + properties.values())
        else:
            self.dbh.execute("insert into inode_%s set inode='%s'" + extra ,[self.table, inode] + properties.values())
        
        ## Set the root file to be a d/d entry so it looks like its a virtual directory:
        self.dbh.execute("select * from file_%s where mode='d/d' and inode=%r and status='alloc'",(self.table,root_inode))
        if not self.dbh.fetch():
            self.dbh.execute("select * from file_%s where mode='r/r' and inode=%r and status='alloc'",(self.table,root_inode))
            row = self.dbh.fetch()
            if row:
                self.dbh.execute("insert into file_%s set mode='d/d',inode=%r,status='alloc',path=%r,name=%r",(self.table,root_inode,row['path'],row['name']))

    def longls(self,path='/', dirs = None):
        if(dirs == 1):
            self.dbh.execute("select path,mode,inode,name from file_%s where path=%r and mode like 'd%%'", (self.table, path))
        elif(dirs == 0):
            self.dbh.execute("select path,mode,inode,name from file_%s where path=%r and mode like 'r%%'", (self.table, path))
        else:
            self.dbh.execute("select path,mode,inode,name from file_%s where path=%r", (self.table, path))

        ## This is done rather than return the generator to ensure that self.dbh does not get interfered with...
        return [dent for dent in self.dbh]
    
    def ls(self, path="/", dirs=None):
        return [ dent['name'] for dent in self.longls(path,dirs) ]

    def dent_walk(self, path='/'):
        self.dbh.execute("select name, mode, status from file_%s where path=%r order by name" % (self.table, path))
        for i in self.dbh:
            yield(i)
    
    def lookup(self, path=None,inode=None):
        if path:
            dir,name = os.path.split(path)
            if not name:
                dir,name = os.path.split(path[:-1])
            if dir == '/':
                dir = ''

            self.dbh.execute("select inode from file_%s where path=%r and (name=%r or name=concat(%r,'/'))", (self.table,dir+'/',name,name))
            res = self.dbh.fetch()
            if not res:
                return None
            return res["inode"]
        else:
            self.dbh.execute("select concat(path,name) as path from file_%s where inode=%r order by status", (self.table,inode))
            res = self.dbh.fetch()
            if not res:
                return None
            return res["path"]
        
    def istat(self, path=None, inode=None):
        if not inode:
            inode = self.lookup(path)
        if not inode:
            return None
        self.dbh.execute("select inode, status, uid, gid, from_unixtime(mtime) as `mtime`, from_unixtime(atime) as `atime`, from_unixtime(ctime) as `ctime`, from_unixtime(dtime) as `dtime`, mode, links, link, size from inode_%s where inode=%r",(self.table, inode))
        return self.dbh.fetch()

    def isdir(self,directory):
        if not directory.endswith('/'):
            directory+='/'
        self.dbh.execute("select mode from file_%s where path=%r",(self.table,directory))
        row=self.dbh.fetch()
        if row:
            return 1
        else:
            return 0
        
    def exists(self,path):
        dir,file=os.path.split(path)
        self.dbh.execute("select mode from file_%s where path=%r and name=%r",(self.table,dir,file))
        row=self.dbh.fetch()
        if row:
            return 1
        else:
            return 0

    def resetscanfs(self,scanners):
        for i in scanners:
            try:
                i.reset()
            except DB.DBError,e:
                logging.log(logging.ERRORS,"Could not reset Scanner %s: %s" % (i,e))
        
    def scanfs(self, scanners, action=None):
        ## Prepare the scanner factory for scanning:
        for s in scanners:
            s.prepare()
        
        dbh2 = DB.DBO(self.case)
        dbh3=DB.DBO(self.case)

        dbh3.execute('select inode, concat(path,name) as filename from file_%s where mode="r/r" and status="alloc"',self.table)
        count=0
        for row in dbh3:
            # open file
            count+=1
            if not count % 100:
                logging.log(logging.INFO,"File (%s) is inode %s (%s)" % (count,row['inode'],row['filename']))
                
            try:
                fd = self.open(inode=row['inode'])
                Scanner.scanfile(self,fd,scanners)
                fd.close()
            except Exception,e:
                logging.log(logging.ERRORS,"%r: %s" % (e,e))
                continue
        
        for c in scanners:
            c.destroy()

# redundant???
#class MountedFS(DBFS):
#    """ This class implements FS access for mounted directories on the host """
#    def open(self, path=None, inode=None):
#        if not path:
#            self.dbh.execute("select path,name from file_%s where inode=%r",(self.table, inode))
#            row=self.dbh.fetch()
#            path=row['path']+"/"+row['name']
#        
#        return MountedFS_file(self.case, self.table, self.fd, inode,os.path.normpath(self.fd.mount_point+path))

class File:
    """ This abstract base class documents the file like object used to read specific files in PyFlag.
    Each subclass must impliment this interface
    """
    readptr = None
    size = None
    def __init__(self, case, table, fd, inode):
        """ The constructor for this object.
        @arg case: Case to use
        @arg table: The base name for all tables
        @arg fd: An already open data source, may be iosource, or another 'File'
        @arg inode: The inode of the file to open, the while inode ending with the part relevant to this vfs
        @note: This is not meant to be called directly, the File object must be created by a valid FileSystem object's open method.
        """
        # each file should remember its own part of the inode
        self.case = case
        self.table = table
        self.fd = fd
        self.inode = inode
        self.readptr =0
        self.size=0

    def close(self):
        """ Fake close method. """
        pass
    
    def seek(self, offset, rel=None):
        """ Seeks to a specified position inside the file """
        if rel==1:
            self.readptr += offset
        elif rel==2:
            self.readptr = self.size + offset
        else:
            self.readptr = offset
            
        if(self.size>0 and self.readptr > self.size):
            self.readptr = self.size
         
    def tell(self):
        """ returns the current read pointer"""
        return self.readptr

    def read(self, length=None):
        """ Reads length bytes from file, or less if there are less bytes in file. If length is None, returns the whole file """
        pass

    def stats(self):
        """ Returns a dict of statistics about the content of the file. """
        pass
    
def FS_Factory(case,table,fd):
    """ This is the filesystem factory, it will create the most appropriate filesystem object available.

    @arg case: Case to use
    @arg table: The base name for all tables
    @arg fd: An already open iosource
    """
    ## If the iosource is special we handle it here:
    class_name = (("%s" % fd.__class__).split("."))[-1]
    #if class_name== "mounted":
    #    return MountedFS(case,table,fd)
    #else:
    return DBFS(case,table,fd)


# helper to get filename of cached files
# ofter created by scanners
##def make_filename(case, inode):
##    """ This function should return a fairly unique name for saving the file in the tmp directory.
    
##    This class implementes a standard filename formatting convention:
##    $RESULTDIR/$case_$inode
    
##    Where inode is the filename in the filesystem.
##    """
##    dbh = DB.DBO(None)
##    return("%s/%s_%s" % (
##        config.RESULTDIR, case, dbh.MakeSQLSafe(inode)))

### create a dict of all the File subclasses by specifier
##import sys
##vfslist={}
##for cls in dir():
##    try:
##        CLS=sys.modules[__name__].__dict__[cls]
##        if issubclass(CLS,File) and CLS != File:
##            vfslist[CLS.specifier]=CLS
##    except TypeError:
##        pass
