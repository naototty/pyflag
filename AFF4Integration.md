# Introduction #

PyFlag has some very interesting features which have proved very useful, such as the concept of the Virtual File System. On the other hand, some features were lacking such as persistent management of case data, archiving and porting data is a complex task.

We transferred many of the useful features to the AFF4 forensic file format. This allowed us to share some of the useful features already found in PyFlag with other forensic software.

  * The AFF4 file format allows us to store many streams within the same volume. These streams can be named using anything that is globally unique. The result is that an AFF4 volume resembles a Virtual File System (VFS) in the sense that the streams can be named in an arbitrary directory structure.
  * PyFlag provided limited support for describing streams using and offset/length operator. This allowed us to denote VFS inode in terms of other inodes. AFF4 takes this idea further by defining Map streams. These streams allow us to describe complex transformations of one stream into another. For example, a reassembled TCP stream is just a map off the individual packet data. The AFF4 map stream allows PyFlag to store derived data in a very efficient way because we do not need to make multiple copies of the same data.
  * PyFlag has a tradition of explaining how each VFS inode was derived by explaining each transformation made on the original data. This tradition is expanded in AFF4 since many AFF4 streams are just maps of other streams. For example, a stream describing a file from a filesystem is simply a map of the block allocation from the original image. This not only provides efficient storage for the extracted file (since we dont need to copy it again) but also serves as an important evidentiary tool to explain how we arrive at the file from the block allocation table.

# Current State of Affairs #

This section describes how AFF4 is planned to be integrated into PyFlag.

PyFlag has the concept of a VFS - a virtual filesystem which only exists in the database. The VFS has Inodes (which are PyFlag terminology for various Objects). VFS Inodes are opened by instantiating VFSFile objects - special classes which handle specific types of Inodes.

PyFlag currently maintains a cache folder stored in the RESULTDIR parameter. Cached files include files which are derived from other files during analysis and take too long to reconstruct on the fly. Previous versions of PyFlag just stored cache files in this directory, but this proved to be inefficient for large cases. Currently all access to the cache files are made through the CacheManager class (i.e. no code touches the cache directly). This should make it easier to adapt to new types of Caches.

# Development proposal #

Our proposal is in several parts:

  1. AFF4 volumes may be loaded using a new report. This creates a new VFS Inode for each AFF4 stream. The Inode name is the same as the AFF4 URN.
  1. New VFSFile classes are written to provide access to the AFF4 streams using the AFF4 library. The AFF4File class provides a detailed explain() method which can produce a report of how each stream is constructed (e.g. Maps targeting certain streams etc).
  1. A new CacheManager class was written to produce an AFF4 volume instead of the RESULTDIR. The CacheManager API was extended to allow for the creation of maps, as well as strings.
  1. All code which uses VFSCreate will be reviewed to produce new AFF4 objects - Maps will be created in preference to copying data out (for example, stream reassembler, filesystem loaders etc). New VFS Inodes will be created using the CacheManager inside the result volume.
  1. Private AFF4 streams will be written to back up any PyFlag database tables. This serves as a way to archive the current state of the case. The result AFF4 volume is synchronised to the current state of the database.

The overall result is that at any time, the result AFF4 volume can be taken to a new system and imported into a new PyFlag installation, to completely recreate the current content of the case. Furthermore, the result AFF4 volume is a regular AFF4 volume and can be processed by any tool supporting the AFF4 standard, regardless of how the VFS Inodes were derived. This allows for a complete interoperable solution with different forensic software.