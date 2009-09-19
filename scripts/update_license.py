import sys
import os

LICENSE = """# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

"""

root = os.path.split(os.path.abspath(sys.argv[0]))[0]
lib = root + os.path.sep + '../lib'

EXTS = ['.py', '.pyx', '.pxd']
EXCLUDE = ['.svn', '_event.pyx']

for path, dirs, files in os.walk(lib):
    for file in files:
        file_path = os.path.join(path, file)
        exclude = False
        for exl in EXCLUDE:
            if exl in file_path: exclude = True
        if exclude: continue
        ext = os.path.splitext(file_path)[1]        
        if not ext in EXTS: continue
        #ok insert license
        f = open(file_path)
        s = f.read()
        f.close()
        s = LICENSE + s
        f = open(file_path, 'w')
        f.write(s)
        f.close()
        print file_path
        #sys.exit()