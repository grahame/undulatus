
Undulatus, a command line twitter client based upon the 
python twitter tools package.

See the file 'LICENSE' for licensing and copyright information.

You'll need:

*  Python 3.1
*  CouchDB
*  Git

To get going;

1.  'git submodule init'; 'git submodule update'  
    this will grab the python twitter tools, and couchdb wrappers
2.  install couchdb on localhost
3.  start undulatus:  
    `./undulatus.py screenname`
4.  .. it ought to just work.

Note: there's a bug in the Python couchdb wrapper that I'm using, 
so if it fails just after launch with a traceback try restarting 
immediately. This should only happen on first-ever launch, or 
after `undulatus.js` has been updated.

