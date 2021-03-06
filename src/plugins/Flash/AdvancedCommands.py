""" These Flash commands allow more sophisticated operations, most of
which may not be needed by most users. Some operations are
specifically designed for testing and have little use in practice.
"""
import pyflag.pyflagsh as pyflagsh
import pyflag.Registry as Registry
import pyflag.DB as DB
import fnmatch,pdb
import pyflag.FileSystem as FileSystem
import pyflag.Scanner as Scanner
import time, types
import pyflag.pyflaglog as pyflaglog
import BasicCommands
import pyflag.ScannerUtils as ScannerUtils
import pyflag.conf
config=pyflag.conf.ConfObject()

class scan_path(pyflagsh.command):
    """ This takes a path as an argument and runs the specified scanner on the path
    this might be of more use than specifying inodes for the average user since if you load
    two disk images, then you might have /disk1 and /disk2 and want to just run scans over
    one of them, which is simpler to specify using /disk1. """

    def help(self):
        return "scan VFSPath [list of scanners]: Scans the VFS path with the scanners specified"
    
    def complete(self, text,state):
        if len(self.args)>2 or len(self.args)==2 and not text:
            scanners = [ x for x in Registry.SCANNERS.scanners if x.startswith(text) ] +\
                       [ x for x in Registry.SCANNERS.get_groups() if x.startswith(text) ]
            return scanners[state]
        else:
            dbh = DB.DBO(self.environment._CASE)
            dbh.execute("select substr(path,1,%r) as abbrev,path from file where path like '%s%%' group by abbrev limit %s,1",(len(text)+1,text,state))
            return dbh.fetch()['path']
        
    def wait_for_scan(self, cookie):
        """ Waits for scanners to complete """
        
        pdbh = DB.DBO()
        pdbh.check_index('jobs','cookie')
        
        ## Often this process owns a worker as well. In that case we can wake it up:
        Farm.wake_workers()
        
        ## Wait until there are no more jobs left.
        while 1:
            pdbh.execute("select count(*) as total from jobs where cookie=%r and arg1=%r",
                         (cookie,
                          self.environment._CASE))
            row = pdbh.fetch()
            if row['total']==0: break
            time.sleep(1)

    def execute(self):
        scanners=[]
                
        if len(self.args)<2:
            yield self.help()
            return
        elif type(self.args[1]) == types.ListType:
            scanners = self.args[1]
        else: 
            for i in range(1,len(self.args)):
                scanners.extend(fnmatch.filter(Registry.SCANNERS.scanners, self.args[i]))

        ## Assume that people always want recursive - I think this makes sense
        path = self.args[0]
        if not path.endswith("*"):
            path = path + "*"
            
        ## FIXME For massive images this should be broken up, as in the old GUI method
        dbh=DB.DBO(self.environment._CASE)
        dbh.execute("select inode_id from vfs where path rlike %r", fnmatch.translate(path))

        pdbh = DB.DBO()
        pdbh.mass_insert_start('jobs')
    
        ## This is a cookie used to identify our requests so that we
        ## can check they have been done later.
        cookie = int(time.time())
            
        for row in dbh:
            inode = row['inode_id']

            pdbh.mass_insert(
                command = 'Scan',
                arg1 = self.environment._CASE,
                arg2 = row['inode_id'],
                arg3 = ','.join(scanners),
                cookie=cookie,
                )
    
        pdbh.mass_insert_commit()
    
        ## Wait for the scanners to finish:
        self.wait_for_scan(cookie)
        
        yield "Scanning complete"

import pyflag.FlagFramework as FlagFramework

class init_flag_db(pyflagsh.command):
    """ Creates the main flag db if needed """
    def execute(self):
        try:
            dbh = DB.DBO()
        except:
            dbh = DB.DBO('mysql')
            dbh.execute("create database `%s`" % config.FLAGDB)
            dbh = DB.DBO()

        FlagFramework.post_event("init_default_db", None)
        yield "Done"

class delete_iosource(pyflagsh.command):
    """ Deletes an iosource from the current case """
    def complete(self, text, state):
        dbh = DB.DBO(self.environment._CASE)
        dbh.execute("select substr(name,1,%r) as abbrev,name from iosources where name like '%s%%' group by abbrev limit %s,1",(len(text)+1,text,state))
        return dbh.fetch()['name']
    
    def execute(self):
        for iosource in self.args:
            dbh = DB.DBO(self.environment._CASE)
            dbh2 = dbh.clone()
            dbh.delete('inode', where=DB.expand("inode like 'I%s|%%'", iosource))
            dbh.execute("select * from filesystems where iosource = %r", iosource)
            for row in dbh:
                dbh2.delete('file', where=DB.expand("path like '%s%%'", iosource))

            dbh.delete("iosources", where=DB.expand("name=%r", iosource))
            yield "Removed IOSource %s" % iosource

class scan(pyflagsh.command):
    """ Scan a glob of inodes with a glob of scanners """
    def help(self):
        return "scan inode [list of scanners]: Scans the inodes with the scanners specified"

    def complete(self, text,state):
        if len(self.args)>2 or len(self.args)==2 and not text:
            scanners = [ x for x in Registry.SCANNERS.scanners if x.startswith(text) ] + \
                       [ x for x in Registry.SCANNERS.get_groups() if x.startswith(text) ]
            
            return scanners[state]
        else:
            dbh = DB.DBO(self.environment._CASE)
            dbh.execute("select  substr(inode,1,%r) as abbrev,inode from inode where inode like '%s%%' group by abbrev limit %s,1",(len(text)+1,text,state))
            return dbh.fetch()['inode']
    
    def execute(self):
        if len(self.args)<2:
            yield self.help()
            return

        ## Try to glob the inode list:
        dbh=DB.DBO(self.environment._CASE)
        dbh.execute("select inode_id from vfs where !isnull(inode_id) and path rlike %r",
                    (fnmatch.translate(self.args[0])))
        pdbh = DB.DBO()
        pdbh.mass_insert_start('jobs')
        ## This is a cookie used to identify our requests so that we
        ## can check they have been done later.
        cookie = time.time()
        scanners = []
        for i in range(1,len(self.args)):
            scanners.extend(fnmatch.filter(Registry.SCANNERS.scanners, self.args[i]))

        scanners = ScannerUtils.fill_in_dependancies(scanners)
        for row in dbh:
            Scanner.scan_inode_distributed(dbh.case, row['inode_id'], scanners,
                                           cookie=cookie)

            
        self.wait_for_scan(cookie)
        yield "Scanning complete"

    def wait_for_scan(self, cookie):
        """ Waits for scanners to complete """
        import pyflag.Farm as Farm

        while Farm.get_cookie_reference(cookie)>0:
            time.sleep(0.5)
        
        return
    
        print "Waiting for cookie %s" % cookie
        pdbh = DB.DBO()

        ## Often this process owns a worker as well. In that case we can wake it up:
        import pyflag.Farm as Farm
        
        #Farm.wake_workers()
        
        ## Wait until there are no more jobs left.
        while 1:
            pdbh.execute("select * from jobs where cookie=%r limit 1", (cookie))
            row = pdbh.fetch()
            if not row: break
            
            time.sleep(1)
            
class scan_inode(scan):
    """ Scan an inode id with the specified scanners """
    def execute(self):
        if len(self.args)<2:
            yield self.help()
            return

        case = self.environment._CASE
        scanners = []
        for i in range(1,len(self.args)):
            scanners.extend(fnmatch.filter(Registry.SCANNERS.scanners, self.args[i]))
            
        scanners = ScannerUtils.fill_in_dependancies(scanners)
        Scanner.scan_inode(case, self.args[0], scanners, force = True, cookie=time.time())

class scan_file(scan,BasicCommands.ls):
    """ Scan a file in the VFS by name """
    def help(self):
        return "scan file [list of scanners]: Scan the file with the scanners specified "

    def complete(self, text,state):
        if len(self.args)>2 or len(self.args)==2 and not text:
            scanners = [ x for x in Registry.SCANNERS.scanners if x.startswith(text) ] +\
                       [ x for x in Registry.SCANNERS.get_groups() if x.startswith(text) ]
            return scanners[state]
        else:
            dbh = DB.DBO(self.environment._CASE)
            dbh.execute("select  substr(path,1,%r) as abbrev,path from file where path like '%s%%' group by abbrev limit %s,1",(len(text)+1,text,state))
            return dbh.fetch()['path']

    def execute(self):
        if len(self.args)<2:
            yield self.help()
            return
        pdbh = DB.DBO()
        pdbh.mass_insert_start('jobs')
        cookie = int(time.time())
        scanners = []
        for i in range(1,len(self.args)):
            scanners.extend(fnmatch.filter(Registry.SCANNERS.scanners, self.args[i]))

        for path in self.glob_files(self.args[:1]):
            try:
                path, inode, inode_id = self.environment._FS.lookup(path = path)
            except Exception,e:
                continue
            ## This is a cookie used to identify our requests so that we
            ## can check they have been done later.

            pdbh.mass_insert(
                command = 'Scan',
                arg1 = self.environment._CASE,
                arg2 = inode_id,
                arg3 = ','.join(scanners),
                cookie=cookie,
                )

        pdbh.mass_insert_commit()
        
        ## Wait for the scanners to finish:
        if 1 or self.environment.interactive:
            self.wait_for_scan(cookie)
            
        yield "Scanning complete"

##
## This allows people to reset based on the VFS path
##
    
class load_and_scan(scan):
    """ Load a filesystem and scan it at the same time """
    def help(self):
        return """load_and_scan iosource mount_point fstype [list of scanners]:

        Loads the iosource into the right mount point and scans all
        new inodes using the scanner list. This allows scanning to
        start as soon as VFS inodes are produced and before the VFS is
        fully populated.
        """
    def complete(self, text,state):
        if len(self.args)>4 or len(self.args)==4 and not text:
            scanners = [ x for x in Registry.SCANNERS.scanners if x.startswith(text) ] + \
                       [ x for x in Registry.SCANNERS.get_groups() if x.startswith(text) ]
            return scanners[state]
        elif len(self.args)>3 or len(self.args)==3 and not text:
            fstypes = [ x for x in Registry.FILESYSTEMS.class_names if x.startswith(text) ]
            return fstypes[state]
        elif len(self.args)>2 or len(self.args)==2 and not text:
            return 
        elif len(self.args)>1 or len(self.args)==1 and not text:
            dbh = DB.DBO(self.environment._CASE)
            dbh.execute("select substr(value,1,%r) as abbrev,value from meta where property='iosource' and value like '%s%%' group by abbrev limit %s,1",(len(text)+1,text,state))
            return dbh.fetch()['value']
    
    def execute(self):
        if len(self.args)<3:
            yield self.help()
            return

        iosource=self.args[0]
        mnt_point=self.args[1]
        filesystem=self.args[2]
        query = {}

        dbh = DB.DBO()
        dbh.mass_insert_start('jobs')
        ## This works out all the scanners that were specified:
        tmp = []
        for i in range(3,len(self.args)):
            ## Is it a parameter?
            if "=" in self.args[i]:
                prop,value = self.args[i].split("=",1)
                query[prop] = value
            else:
                tmp.extend([x for x in fnmatch.filter(
                    Registry.SCANNERS.scanners, self.args[i]) ])


        scanners = [ ]
        for item in tmp:
            if item not in scanners:
                scanners.append(item)

        ## Load the filesystem:
        try:
            fs = Registry.FILESYSTEMS.dispatch(filesystem)
        except KeyError:
            yield "Unable to find a filesystem of %s" % filesystem
            return

        fs=fs(self.environment._CASE, query)
        fs.cookie = int(time.time())
        fs.load(mnt_point, iosource, scanners)

        ## Wait for all the scanners to finish
        self.wait_for_scan(fs.cookie)
        
        yield "Loading complete"
