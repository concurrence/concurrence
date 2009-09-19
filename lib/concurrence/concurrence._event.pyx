#
# event.pyx
#
# libevent Python bindings
#
# Copyright (c) 2004 Dug Song <dugsong@monkey.org>
# Copyright (c) 2003 Martin Murray <murrayma@citi.umich.edu>
#
# $Id: event.pyx,v 1.12 2005/09/12 03:16:15 dugsong Exp $

"""event library

This module provides a mechanism to execute a function when a
specific event on a file handle, file descriptor, or signal occurs,
or after a given time has passed.
"""

__author__ = ( 'Dug Song <dugsong@monkey.org>',
               'Martin Murray <mmurray@monkey.org>' )
__copyright__ = ( 'Copyright (c) 2004 Dug Song',
                  'Copyright (c) 2003 Martin Murray' )
__license__ = 'BSD'
__url__ = 'http://monkey.org/~dugsong/pyevent/'
__version__ = '0.3'

import sys
import logging
import collections

cdef extern from "Python.h":
    void  Py_INCREF(object o)
    void  Py_DECREF(object o)
    
ctypedef void (*event_handler)(int fd, short evtype, void *arg)

cdef extern from "string.h":
    char *strerror(int errno)

cdef extern from "errno.h":
    int errno

cdef extern from "event.h":
    struct timeval:
        unsigned int tv_sec
        unsigned int tv_usec
    
    struct event_t "event":
        int   ev_fd
        int   ev_flags
        void *ev_arg

    void event_init()
    char *event_get_version()
    char *event_get_method()
    void event_set(event_t *ev, int fd, short event,
                   event_handler handler, void *arg)
    void evtimer_set(event_t *ev, event_handler handler, void *arg)
    int  event_add(event_t *ev, timeval *tv)
    int  event_del(event_t *ev)
    int  event_loop(int flags)
    int  event_pending(event_t *ev, short, timeval *tv)

    int EVLOOP_ONCE
    int EVLOOP_NONBLOCK

EV_TIMEOUT = 0x01
EV_READ    = 0x02
EV_WRITE   = 0x04
EV_SIGNAL  = 0x08
EV_PERSIST = 0x10

triggered = collections.deque()

cdef void __event_handler(int fd, short evtype, void *arg):
    (<object>arg).__callback(evtype)

class EventError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg + ": " + strerror(errno))

cdef class event:
    """event(callback, evtype=0, handle=None) -> event object
    
    Create a new event object with a user callback.

    Arguments:

    callback -- user callback with (ev, handle, evtype, arg) prototype
    arg      -- optional callback arguments
    evtype   -- bitmask of EV_READ or EV_WRITE, or EV_SIGNAL
    handle   -- for EV_READ or EV_WRITE, a file handle, descriptor, or socket
                for EV_SIGNAL, a signal number
    """
    cdef event_t ev
    cdef object evtype, callback
    cdef timeval tv

    def __init__(self, callback, short evtype = 0, handle = -1):

        self.callback = callback
        self.evtype = evtype
        if evtype == 0 and not handle:
            evtimer_set(&self.ev, __event_handler, <void *>self)
        else:
            if not isinstance(handle, int): 
                handle = handle.fileno()
            event_set(&self.ev, handle, evtype, __event_handler, <void *>self)

    def __callback(self, short evtype):
        if not self.pending():
            Py_DECREF(self)
        
        triggered.append((self.callback, evtype))
            
    def add(self, float timeout=-1):
        """Add event to be executed after an optional timeout."""
        if not self.pending():
            Py_INCREF(self)
            
        if timeout >= 0.0:
            self.tv.tv_sec = <long>timeout
            self.tv.tv_usec = <long>((timeout - <float>self.tv.tv_sec) * 1000000.0)
            if event_add(&self.ev, &self.tv) == -1:
                raise EventError("could not add event")
        else:
            self.tv.tv_sec = self.tv.tv_usec = 0
            if event_add(&self.ev, NULL) == -1:
                raise EventError("could not add event")

    def pending(self):
        """Return 1 if the event is scheduled to run, or else 0."""
        return event_pending(&self.ev, EV_TIMEOUT|EV_SIGNAL|EV_READ|EV_WRITE, NULL)
    
    def delete(self):
        """Remove event from the event queue."""
        if self.pending():
           if event_del(&self.ev) == -1:
                raise EventError("could not delete event")
           Py_DECREF(self)
    
    def __dealloc__(self):
        self.delete()
    
    def __repr__(self):
        return '<event flags=0x%x, callback=%s' % (self.ev.ev_flags, self.callback)

def version():
    return event_get_version()

def method():
    return event_get_method()

def loop():
    """Dispatch all pending events on queue in a single pass."""
    if event_loop(EVLOOP_ONCE) ==  -1:
        raise EventError("error in event_loop")
    return triggered

# XXX - make sure event queue is always initialized.
event_init()

