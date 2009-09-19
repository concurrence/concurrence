# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class LockType(object):
    def __init__(self, *args, **kwargs):
        pass        

    def acquire(self, waitflag=None):        
        return True
 
    __enter__ = acquire
 
    def __exit__(self, typ, val, tb):
        pass
 
    def release(self):
        pass
    
    def locked(self):
        return False

class RLock(LockType):
    pass

class Lock(LockType):
    pass

class Thread(object):
    def getName(self):
        return 'dummy'

class ThreadLocal(object):
    def __init__(self):
        pass        
       
class _Timer(object):
    pass

local = ThreadLocal

_currentThread = Thread()

def currentThread():
    return _currentThread

def _shutdown(*args, **kwargs):
    pass
