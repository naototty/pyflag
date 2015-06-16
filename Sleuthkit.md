# Sleuthkit Integration #

Pyflag use sleuthkit for filesystem-level analysis. This page describes the way
sleuthkit is integrated into pyflag. In particular it documents the python 'sk'
module shipped with pyflag.

## History ##

In very early  pyflag releases, pyflag shelled-out directly to sleuthkit tools
(e.g. fls, ils etc) and parsed their results to populate a database schema
within pyflag. Parsing was a bit error-prone and slow.

Later we wrote a program called 'dbtool' to populate the initial filesystem
database. The dbtool program was written in C and had sleuthkit code linked
into it directly. dbtool excercised the functionallity of sleuthkit in a single
hit. e.g. much like using 'fls', followed by 'ils', followed by 'istat' for
each file.

The database schema includes all filesystem metadata available in sleuthkit
including filenames, inode metadata (timestamps) and block allocations for
every file. Once the filesystem was populated, we never needed to use sleuthkit
again. File IO was performed by looking up the blocks in the metadata tables
and reading from the image source directly.

This worked reasonably well for a while but had a few drawbacks. For example,
sleuthkit now supports NTFS compression. By doing our own direct block IO, we
cannot use these sleuthkit features.

It was decided that a python interface into sleuthkit would be the best
solution for our needs. This way we have sleuthit always loaded and can access
any of its functionallity at any time. There are performance benefits to this
approach also.

## Python Module ##

The python sleuthkit module is called 'sk'. It is written in C and can be found
in the files sk.c and sk.h under ./src/filesystems/sleuthit/python directory in
the pyflag distribution.

The module provides a simple filesystem-like interface into sleuthkit which
emulates pythons native filesystem methods. Extensions are provided to access
sleuthkit specific forensics data.

The module can be build standalone as it does not depend on the pyflag framework.
However it is not packaged separately at this stage.

## Documentation ##

sk provides two main classes, skfs and skfile. It also provides a mmls method.

### skfs ###

The skfs class represents a sleuthkit filesystem. The constructor looks like this:
  * **sk.skfs(imgfile, imgoff=0, fstype=None)**:   Object constructor. imgfile must be a python file-like object (provides read, seek, tell). fstype is a string of any of the supported sleuthkit file types (e.g. ntfs, fat, etc) see 'fls -f list' for a full list. The default of None uses sleuthkit's builtin autodetection which is probably best most of the time.

The skfs object provides the following methods:

  * **listdir(path, alloc=True, unalloc=False)**:   List directory contents under path. alloc and unalloc controls whether directory entries found in unused space are returned.

  * **stat(path=None, inode=0)**:      Stat a file. Arguements can either be a path or an inode. inode can be an integer or a string (e.g. 123-1-128 to retrieve a specific NTFS attribute). Returns a stat\_result object just like os.stat in python.

  * **fstat(skfile)**:     Stat an already open skfile.

  * **walk(path=None, inode=0, alloc=True, unalloc=False, names=True, inodes=False)**:      Walk filesystem (like python's os.walk). This function is a generator which walks the directory tree starting at path or inode. alloc and unalloc control whether directory entries found in unused space are returned. names and inodes control what the function should return. The default behavior is to generate lists of string paths just like os.walk. If both are true, the function will generate lists of (inode, path) tuples. This is often more useful as doing further lookups (e.g. open, stat etc) using the inode is significantly faster than using a string path. Internally this is much like 'fls' (file\_walk).

  * **iwalk(inode=0, alloc=False, unalloc=True)**:     Return inodes. Internally this is much like 'ils' (inode\_walk). Note that this function has not been implemented as a generator, so it is best used only to return deleted inodes (default behavior) or else a potentially very large list will be built in memory.

  * **open(path=None, inode=0)**:      Open a file, returns an skfile object. Opening by inode is faster than using path.

In addition, skfs has the following members:

```
    skfs.block_size
    skfs.root_inum
    skfs.first_inum
    skfs.last_inum
```

### skfile ###

The skfile class has the following methods:

  * **skfile.close()**:   Close file
  * **skfile.seek(offset, whence=0)**:    Seek to position. whence meaning is the same as in python.
  * **skfile.tell()**:    Show current file position
  * **skfile.read(length, slack=False)**:    Read data from file. If slack=True, the read will continue up until the end of the final block, thus returning slack space.
  * **skfile.blocks()**:  Returns a list of filesystem blocks which the file occupies.
### mmls ###

The mmls class method takes a file-like object and returns a list of tuples
containing information about the image, just like mmls.

## Examples ##

### Basic FS Operations ###

```
#!/usr/bin/env python

import sk

fd = open('uploads/pyflag_stdimage_0.1')

# open skfs
fs = sk.skfs(fd)

# list the root directory
fs.listdir('/')

# perform a full directory walk
for root, dirs, files in fs.walk('/'):
    print root
    for dir in dirs:
        print dir
# open a file within the filesystem
f = fs.open('hello.txt')

# print the file contents
print f.read()
```

### Additional Operations ###
```
#!/usr/bin/env python

import sk

fd = open('uploads/pyflag_stdimage_0.1')

# open skfs
fs = sk.skfs(fd)

# generate deleted directory entries
for root, dirs, files in fs.walk('/', alloc=False, unalloc=True):
    print root, dirs, files

# generate deleted inodes
for inode in fs.iwalk():
    print inode
# stat a file
s = fs.stat('hello.txt')
print "Timestamps: m=%s, a=%s, c=%s" % (s.st_mtime, s.st_atime, s.st_ctime)

# print file block addresses
f = fs.open('hello.txt')
print f.blocks()

# read slack space from file
f.seek(0, 2)
slack = f.read(slack=True)
```