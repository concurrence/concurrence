# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import time

from concurrence import TaskLocal

class _Timeout(object):
    def __init__(self):
        self._timeout_time = [-1]

    def current(self):
        """returns the current timeout time to use in low level 'blocking' operations"""
        if self._timeout_time[-1] < 0:
            return -1
        else:
            timeout = self._timeout_time[-1] - time.time()
            if timeout < 0: timeout = 0.0 #expire immidiatly
            return timeout
        
    def push(self, timeout = -1):   
        current_timeout = self._timeout_time[-1]
        if timeout < 0 and current_timeout < 0:
            self._timeout_time.append(timeout)
        elif timeout < 0 and current_timeout >= 0:
            self._timeout_time.append(current_timeout)
        else:
            _timeout_time = time.time() + timeout    
            if current_timeout < 0:
                self._timeout_time.append(_timeout_time)
            else:
                self._timeout_time.append(min(_timeout_time, current_timeout))
            
    def pop(self):
        assert len(self._timeout_time) > 1, "unmatched pop, did you forget to push?"
        self._timeout_time.pop()
        
    def __enter__(self):
        return self
     
    def __exit__(self, type, value, traceback):
        self.pop()
        

class Timeout:
    """Task based timeout. The :class:`Timeout` class lets you set a timeout for the current task.
    If the task takes longer than *timeout* seconds after the timeout is set, a :class:`~concurrence.core.TimeoutError` is raised
    inside the task.
    
    Timeouts form a stack and you can always :func:`push` a new timeout on top of the current one. Every :func:`push` must be matched
    by a corresponding call to :func:`pop`. As a convenience you can use pythons `with` statement to do the pop automatically.  

    Timeout example::
    
        with Timeout.push(30):  #everything in following block must be finished within 30 seconds
            ...
            ...
            with Timeout.push(5):
                cnn = get_database_connection() #must return within 5 seconds
            ...
            ...
    
    """
     
    _local = TaskLocal()
    
    @classmethod
    def push(cls, timeout):
        """Pushes a new *timeout* in seconds for the current task."""
        try:
            t = cls._local.t
        except AttributeError:
            t = _Timeout()
            cls._local.t = t
        t.push(timeout)
        return t

    @classmethod
    def pop(cls):
        """Pops the current timeout for the current task."""
        try:
            t = cls._local.t
            t.pop()
        except AttributeError:
            assert False, "no timeout was pushed for the current task"

    @classmethod
    def current(cls):
        """Gets the current timeout for the current task in seconds. That is the number of seconds before the current task
        will timeout by raising a :class:`~concurrence.core.TimeoutError`. A timeout of -1 indicates that there is no timeout for the
        current task."""
        try:
            t = cls._local.t
        except AttributeError:
            t = None
        if t is None: #no timeout defined for current task, so return indefinte timeout
            return -1
        else:
            return t.current()
