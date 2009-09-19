# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import weakref

from concurrence import Tasklet

class TaskLocal(object):
    """A TaskLocal class analogous to pythons ThreadLocal object"""
    
    class _LocalAttributes(object): pass #the instance that will hold the local attributes for a given task
    
    def __init__(self, recursive = False):
        #the only addition in TaskLocal vs ThreadLocal is recursive lookups
        #e.g. if enabled, when an attribute is not found for the calling
        #tasks, the corresponding local for the parent task is checked,
        #up the tree of tasks, until either it is found in some parent, or
        #not, in which case an AttributeError is raised
        self._recursive = recursive
        #we use a weak dict with tasklets as keys,
        #that way we don't need to store the locals on the tasklet itself
        #and also when a tasklet is gc'd, its locals will disappear automatically
        self._d = weakref.WeakKeyDictionary() # tasklet->dict of attributes
        
    def __getattr__(self, key):
        #TODO PROFILING this method seems to be quite expensive in profiling
        #can we cache the route up into the parent or something?
        d = self._d
        current = Tasklet.current()
        while current is not None:
            if (not current in d) or (not hasattr(d[current], key)):
                if not self._recursive:
                    break
                else:
                    current = current.parent() #continue checking parent task locals 
            else:
                return getattr(d[current], key)
            
        raise AttributeError(key)
        
    def __setattr__(self, key, value):
        if key in ['_d', '_recursive']: #to protect from infinite recursion during __init__
            self.__dict__[key] = value
        else:
            d = self._d
            current = Tasklet.current()
            if not current in d: #task specific attributes instance not created yet               
                d[current] = self._LocalAttributes()
            setattr(d[current], key, value)

    def __delattr__(self, key):
        #note: del attr is not recursive!
        d = self._d
        current = Tasklet.current()
        if (not current in d) or (not hasattr(d[current], key)):
            raise AttributeError(key)
        else:
            delattr(d[current], key)
            
class TaskInstance(TaskLocal):
    """A Task scoped Instance, e.g. it is similar to TaskLocal in that it contains
    state that is specific to a task, the difference is, that here the state for the
    task is set explicitly using the 'set' method, instead of being created on first
    attribute access"""
    def __enter__(self):
        return self
     
    def __exit__(self, type, value, traceback):        
        self.unset()

    def unset(self):
        """unsets the instance for current task"""
        del self._d[Tasklet.current()]
        
    def set(self, instance):
        """specifically sets the given instance for current task"""
        self._d[Tasklet.current()] = instance
        return self
    
