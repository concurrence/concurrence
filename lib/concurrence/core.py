# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import sys
import time
import logging
import weakref
import collections
import gc

try:
    import stackless
except ImportError: 
    #we might be running from CPython, or PyPy
    #try the greenlet based stackless emulation
    import _stackless as stackless

if '-Xnogc' in sys.argv:
    logging.warn('disabling gc')    
    gc.disable()

DEBUG_LEAK = False
if '-Xleak' in sys.argv:
    logging.warn('turned on leak detection')
    gc.set_debug(gc.DEBUG_SAVEALL)        
    DEBUG_LEAK = True

from signal import SIGINT
from concurrence import _event

def get_version_info():
    return {'libevent_version': _event.version(),
            'libevent_method': _event.method()}
    
if '-Xversion' in sys.argv:
    print 'libevent: version: %s, method: %s' % (_event.version(),  _event.method())
    print 'python:', sys.version

EXIT_CODE_OK = 0
EXIT_CODE_ERROR = 1
EXIT_CODE_SIGINT = 127
EXIT_CODE_TIMEOUT = 128

class TimeoutError(Exception): 
    """This exception can be raised by various methods that accept *timeout* parameters.""" 
    
class TaskletError(Exception):
    def __init__(self, cause, tasklet):
        self.cause = cause
        self.tasklet = tasklet
    
class JoinError(TaskletError):
    """A JoinError can be raised from any of the :func:`join_XXX` methods of the
    :class:`Tasklet` class."""    
    pass

class Event(object): 
    pass

class FileDescriptorEvent(Event):
    def __init__(self, fd, rw):
        if rw == 'r':
            ev = _event.EV_READ
        elif rw == 'w':
            ev = _event.EV_WRITE
        else:
            assert False, "rw must be one of ['r', 'w']"
        self._event = _event.event(self._on_event, ev, fd)
        self._current_channel = None #this is where read/write ability is notified

    def _on_event(self, ev_type):
        if self._current_channel is None:
            return #already closed
        if ev_type & _event.EV_TIMEOUT:
            self._current_channel.send_exception(TimeoutError, "timeout on fd event")
        else:
            self._current_channel.send(self)

    def notify(self, channel = None, timeout = -1.0):
        if channel is None: channel = Channel()
        self._current_channel = channel
        self._event.add(timeout)
        
    def wait(self, channel = None, timeout = -1.0):
        self.notify(channel, timeout)
        return self._current_channel.receive()        

    def delete(self):
        self._event.delete()

    def close(self):
        self.delete()
        self._event = None
        self._current_channel = None

class SignalEvent(Event):
    def __init__(self, signo, callback, persist = True):
        self._persist = persist
        self._callback = callback
        self._event = _event.event(self._on_event, _event.EV_SIGNAL, signo)
        self._event.add()

    def _on_event(self, ev_type):
        #print 'signal event'
        if self._persist: 
            self._event.add()
        if callable(self._callback):
            self._callback()

    def close(self):
        self._event.delete()
        del self._event
        del self._callback

class TimeoutEvent(Event):
    def __init__(self, timeout, callback, persist = False):
        self._persist = persist
        self._timeout = timeout
        self._callback = callback
        self._event = _event.event(self._on_event, 0)
        self._event.add(timeout)

    def _on_event(self, ev_type):
        #print 'timeout event'
        if self._persist: 
            self._event.add(self._timeout)
        if callable(self._callback):
            self._callback()

    def close(self):
        self._event.delete()
        del self._event
        del self._callback

class Message():
    def __init__(self, reply_channel = None):
        self._reply_channel = reply_channel
        
    def match(self, cls):
        """Checks whether this message is an instance of the given message class *cls*.""" 
        return isinstance(self, cls)
        
    def reply(self, result):
        """Reply to the message and return *result* to the caller."""
        if self._reply_channel is None:
            assert False, "can only reply to a synchronous message, e.g. somebody must be calling us with 'call'"
        else:
            self._reply_channel.send(result)

    def wait(self, timeout = -1):
        if self._reply_channel is None:
            assert False, "can only wait on a synchronous message"
        else:
            return self._reply_channel.receive(timeout)

    @classmethod
    def send(cls, receiver):
        """Asynchronously sends the message *cls* to the given *receiver*."""
        def _sender(*args, **kwargs):
            receiver.send(cls(), *args, **kwargs)
        return _sender
    
    @classmethod
    def call(cls, receiver, timeout = -1):
        """Synchronously send the message *cls* to the given *receiver* and waits 
        for a response. The result will be the response of the *receiver*.
        Optionally a *timeout* in seconds can be specified. If the receiver does not respond within
        the *timeout* period a :class:`TimeoutError` is raised."""
        def _caller(*args, **kwargs):   
            return receiver.call(cls(Channel()), timeout, *args, **kwargs)
        return _caller

class Deque(collections.deque):
    """Deque is an extension of the standard python deque that provides blocking operations and timeouts"""
    def __init__(self, iterable = []):
        collections.deque.__init__(self, iterable)
        self.channel = Channel()
        
    def pop(self, blocking = False, timeout = -1):
        """Pop the last item from the end of the queue. If *blocking* is True, the caller will block for *timeout* seconds until an item 
        becomes available."""
        if len(self) == 0 and blocking:
            self.channel.receive(timeout)
        return collections.deque.pop(self)
    
    def popleft(self, blocking = False, timeout = -1):
        """Pop the first item from the start of the queue. If *blocking* is True, the caller will block for *timeout* seconds until an item 
        becomes available."""
        if len(self) == 0 and blocking:
            self.channel.receive(timeout)
        return collections.deque.popleft(self)
    
    def append(self, x):
        """Append item *x* to the end of the queue."""
        collections.deque.append(self, x)
        if self.channel.balance < 0:
            self.channel.send(True)
                    
    def appendleft(self, x):
        """Append item *x* to the start of the queue."""
        collections.deque.appendleft(self, x)
        if self.channel.balance < 0:
            self.channel.send(True)                    

class Mailbox(Deque):
    """Every tasklet has a mailbox, a queue of messages send by other tasklets that are not yet consumed."""
    pass

class Tasklet(stackless.tasklet):
    """A Tasklet represents an activity that runs concurrently to other Tasklets.
    A Tasklet can be compared to a Thread with the main difference that Tasklets are scheduled co-operatively
    by the Concurrence framework as opposed to Threads, which are scheduled pre-emptively by the OS. 

    Only 1 Tasklet will be actually using 1 CPU at any point in time. But many Tasks
    may be present at the same time. 
    
    A Tasklet can become inactive (block) as soon as it performs some IO, or it explictly releases
    control (for instance by calling :func:`yield_`). 

    As soon as a Tasklet blocks, the Concurrence framework will schedule
    some other Tasklet to run next (in a round-robin fashion).
     
    If a Tasklet became inactive because it needs to wait for IO, The Concurrence framework
    will automatically reschedule that Tasklet again as soon as that IO is complete.""" 
    
    def __init__(self):
        """Please use :func:`new` to create new tasklets"""
        stackless.tasklet.__init__(self)
        self.name = ''
        self._parent = None
        self._children = None
        self._join_channel = None
        self._mailbox = None

    def __exec__(self, f, *args, **kwargs):
        """Wraps the excecution of the task function f in such
        a way that we maintain a nice tree of tasklets. Also
        implements a method to join 2 tasklets such that you can
        wait for a tasklet to exit and receive its result (the result of f)"""
        try:
            self._result = f(*args, **kwargs)           
            if self._join_channel:
                self._join_channel.send(self)
        except TaskletExit, e:
            self._result_exc = e
            if self._join_channel:
                self._join_channel.send_exception(JoinError, e, self)
            else:
                raise
        except Exception, e:
            self._result_exc = e
            if self._join_channel:
                self._join_channel.send_exception(JoinError, e, self)
            else:
                raise
        except:
            self._result_exc = sys.exc_type
            if self._join_channel:
                self._join_channel.send_exception(JoinError, sys.exc_type, self)
            else:
                raise
        finally:
            #i am finished so remove myself from my parents child list
            parent = self.parent()
            if parent:
                parent._remove_child(self)
            self._parent = None
            self._children = None
            self._join_channel = None
            self._mailbox = None
            
    def has_finished(self):
        """Returns whether this Tasklet has already finished or not (either with a result of with an exception)."""
        return hasattr(self, '_result') or hasattr(self, '_result_exc')
    
    def _add_child(self, child):
        if self._children is None:
            self._children = set()
        self._children.add(child)
        
    def _remove_child(self, child):
        if self._children is not None:         
            self._children.remove(child)
        
    def children(self):
        """Gets the set of children of this Tasklet"""
        if self._children is None:
            return set()
        else:
            return self._children

    #TODO parent() and children() should be properties
    def _set_parent(self, parent):
        self._parent = weakref.ref(parent)

    def parent(self):
        """Gets the parent of this Tasklet. This method may return None if the parent is no longer there."""
        if self._parent is not None:
            return self._parent()
        else:
            return None
    
    @property
    def mailbox(self):
        """The queue of messages send by other tasklets that are not yet consumed. Use :func:`receive` to get pending message for the current task.
        Alternatively you can use the methods of :class:`Mailbox` directly.
        """
        if self._mailbox is None:
            self._mailbox = Mailbox()
        return self._mailbox 

    def send(self, msg, *args, **kwargs):
        self.mailbox.append((msg, args, kwargs))                  
    
    def call(self, msg, timeout, *args, **kwargs):
        self.send(msg, *args, **kwargs)
        return msg.wait(timeout)

    @classmethod
    def receive(cls, timeout = -1):
        """A generator that yields the next pending :class:`Message` in the :attr:`mailbox` of the current task. This
        method returns a tuple (msg, args, kwargs) for each message received. If no message is available the task blocks
        and waits for a message to arrive."""
        self = cls.current()
        mailbox = self.mailbox
        while True:
            x = mailbox.popleft(True, timeout)
            yield x
            
    @classmethod
    def yield_(cls):
        """Calls the scheduler to cooperatively schedule some other tasks.
        The current class will block and some other task will continue. The current task remains runnable
        and after some time it will be scheduled again and this method will return.
        If there is no other task runnable, this method is a no-op. 
        :func:`yield_` is used when a task is busy processing some
        lengthy calculation that contains no other blocking events like IO or timeouts. 
        By calling :func:`yield_` once in a while it can prevent itself from hogging 
        the CPU and give other tasks some change to do some work as well."""
        cls.sleep(0.0) 
        #note that we don't use stackless.schedule() here anymore. This would still hog the CPU, never getting
        #never getting into the libevent loop again. by using sleep we prevent this    

    def _get_result(self):
        if hasattr(self, '_result'):
            return self._result
        elif hasattr(self, '_result_exc'):
            raise JoinError(self._result_exc, self)
        else:
            assert False, 'Cannot get result of a task that has not finished'
        
    @classmethod
    def join(cls, t, timeout = -1):
        """The current task will block and wait for the given task *t* to complete. When *t* is finished, this method will return
        its result value. If *t* finishes with an exception this method will raise a :class:`JoinError`. Optionally a *timeout* in seconds may
        be specified. If *task* does not finish within *timeout* a :class:`TimeoutError` will be raised."""
        if t.has_finished():
            return t._get_result()
        if t._join_channel is not None:
            assert False, "Tasklet can only be joined once"
        t._join_channel = Channel()
        try:
            _ = t._join_channel.receive(timeout)
            return t._get_result() 
        finally:
            t._join_channel = None
        
    @classmethod
    def join_all(cls, tasks, timeout = -1):
        """The current task will block and wait for the given *tasks* to complete. When all *tasks* have finished a list of 
        results is returned. If a task finishes with an exception the result value for that task will be an instance of :class:`JoinError`.
        Optionally a *timeout* for the wait can be specified. If all *tasks* do not finish within *timeout* a :class:`TimeoutError` will be
        raised."""
            
        if timeout != -1:
            deadline = time.time() + timeout
        else:
            deadline = -1
            
        results = {}
        
        for t in tasks[:]: #tasks are copied to prevent modification during iteration
            try:
                if deadline == -1:
                    results[t] = cls.join(t, -1)
                else:
                    results[t] = cls.join(t, deadline - time.time())
            except JoinError, je:
                results[je.tasklet] = je
            except TaskletExit:
                raise
            except:
                assert False, "expecting only join errors here"
            
        return [results[t] for t in tasks]
    
    @classmethod
    def join_children(cls, timeout = -1):
        """A convenience method for joining all children of the current task. Behaves as :func:`join_all` where *tasks* is the list
        of children."""
        return cls.join_all(list(cls.current().children()), timeout = -1)
        
    @classmethod
    def loop(cls, f, **kwargs):
        """Creates a new task that will execute the given callable *f* in a loop.
        See :func:`new` for a description of any further keyword arguments.
        Any exception that is raised by *f* is caught and logged but the loop will continue running. A looping
        task can be stopped by calling :func:`kill` on it."""
        def _loop(*args, **kwargs):
            while True:
                try:
                    f(*args, **kwargs)
                except TaskletExit:
                    break
                except:
                    logging.exception("unhandled exception in Tasklet.loop")
                    cls.sleep(1.0) #prevent hogging the cpu if exception repeats
        
        return cls.new(_loop, **kwargs)
    
    @classmethod
    def interval(cls, timeout, f, immediate = False, **kwargs):
        """Creates a new task that will execute the given callable *f* every
        *timeout* seconds. If *immediate* is True, *f* will be called as soon as the 
        task is started. Otherwise, the newly started task will wait *timeout* seconds before
        calling *f* for the first time. See :func:`new` for a description of any further keyword arguments.
        Any exception that is raised by *f* is caught and logged but the interval task will continue running. An interval
        task can be stopped by calling :func:`kill` on it."""
        def _interval(*args, **kwargs):
            if immediate: f(*args, **kwargs)
            while True:
                cls.sleep(timeout)
                try:
                    f(*args, **kwargs)
                except TaskletExit:
                    break
                except:
                    logging.exception("unhandled exception in Tasklet.interval")
        return cls.new(_interval, **kwargs)

    @classmethod
    def rate(cls, rate, f, **kwargs):
        """Creates a new task that will call *f* *rate* times per second. The main difference with :func:`interval` is that
        this method is more accurate in calling *f* exactly *rate* times per second independent of the load generated by *f* and or
        other tasks running on the system. It does this by varying the interval on the basis of the difference between the target interval
        1 / *rate* and the actual interval found by measuring the timing. See :func:`new` for a description of any further keyword arguments.
        As a convenience the current time is passed as the first parameter to *f*.
        """
        def _interval(*args, **kwargs):
            sleep_channel = Channel()
            target_timeout = timeout = 1.0 / rate
            min_timeout = 0.5 * target_timeout
            max_timeout = 1.5 * target_timeout
            last_time = time.time()
            while True:
                try:
                    sleep_channel.receive(timeout)
                except TimeoutError:
                    current_time = time.time()
                    actual_timeout = current_time - last_time
                    last_time = current_time
                    diff = actual_timeout - target_timeout
                    next_timeout = timeout - diff
                    timeout = (0.8 * timeout) + (0.2 * next_timeout)
                    if timeout > max_timeout: timeout = max_timeout
                    if timeout < min_timeout: timeout = min_timeout
                try:
                    f(current_time, *args, **kwargs)
                except TaskletExit:
                    break
                except:
                    logging.exception("unhandled exception in Tasklet.rate")
        return cls.new(_interval, **kwargs)
    
    @classmethod
    def receiver(cls, f, **kwargs):
        """Creates a new task will that will wait for messages to arrive and calls *f* (msg, *args, **kwargs)
        for each :class:`Message` received. 
        See :func:`new` for a description of any further keyword arguments."""
        def _receiver():
            for msg, args, kwargs in cls.receive():
                try:
                    f(msg, *args, **kwargs)
                except TaskletExit:
                    break
                except:
                    logging.exception("unhandled exception in Tasklet.receiver")
        return cls.new(_receiver, **kwargs)

    @classmethod 
    def sleep(cls, timeout):
        """Blocks the current task for the given *timeout* in seconds."""
        sleep_channel = Channel()
        try:
            sleep_channel.receive(timeout)
        except TimeoutError:
            pass #expected to happen after timeout

    @classmethod       
    def current(cls):
        """Returns a reference to the currently running task"""
        return stackless.getcurrent()

    @classmethod 
    def later(cls, timeout, f, **kwargs):
        """Creates a new task that will first sleep for *timeout* seconds
        before calling *f*. See :func:`new` for a description of any further keyword arguments."""
        def x(*args, **kwargs):
            cls.sleep(timeout)
            return f(*args, **kwargs)
        return cls.new(x, **kwargs)
        
    @classmethod
    def new(cls, f, name = '', daemon = False):
        """Creates a new task that will run callable *f*. The new task can optionally
        be named *name*. If no *name* is given a name is derived from the callable *f*.
        
        The result of *f* will be the result of the tasklet. *f* may throw an exception, in which case
        the exception will be the result of the tasklet."""
        t = cls()
        if name is '':
            t.name = f.__name__
        else:
            t.name = name
        def w(*args, **kwargs):
            t.__exec__(f, *args, **kwargs)
        
        t.bind(w)
        if not daemon:
            parent = cls.current()    
            #stackless main task is not an instance of our Tasklet class (but of stackless.tasklet)
            #so we can only keep parent/child relation for Tasklet instances
            if isinstance(parent, cls):
                t._set_parent(parent)
                parent._add_child(t)
            
        return t

    def __str__(self):
        return "<Tasklet name='%s'>" % self.name

    def tree(self, level = 0):
        """An inorder treewalk starting at the current task and 
        iterating over its children, grandchildren etc. this generator
        yields tuples (task, level)."""
        yield (self, level)
        if self._children:
            for child in self._children:
                for child_task, child_level in child.tree(level + 1):
                    yield (child_task, child_level)
 
    def kill(self):
        """Raise a TaskletExit exception in the task. This will normally kill the task.
        Note that TaskletExit is a subclass of SystemExit and thus not a subclass of Exception.
        This means that if a task explicitly catches either TaskletExit or SystemExit it could
        prevent itself from being killed."""
        #overridden for documentation purposes
        stackless.tasklet.kill(self)

class Channel(object):
    """A Channel is a method for transfering control and/or communicate between Tasklets. 
    Please note that the Channel class is basically a small wrapper around a 
    `stackless channel <http://www.stackless.com/wiki/Channels>`_. 
    It was overridden in Concurrence to provide timeouts on the :func:`send` and :func:`receive` methods.

    A :class:`Tasklet` can :func:`receive` from a Channel as soon as some other Tasklet will :func:`send` on the 
    channel. If there is no sender the receiving Tasklet will block until a sender is available. If a sender and a 
    receiver are available, the sender will pass a value to the receiver and execution will continue in the receiver (The sender will
    become 'runnable' as well, but will be placed at the end of the scheduling queue).
    
    The reverse works the same. If there is a sender but no receiver, the sender will block until a receiver arrives. As soon
    as a receiver arrives, the value of the sender is passed and execution continues with the receiver (The sender will become `runnable`
    again, but will be placed at the end of the scheduling queue).
    """

    def __init__(self):
        self._channel = stackless.channel()

    @property
    def balance(self):
        return self._channel.balance

    def has_receiver(self):
        """Whether this Channel has any waiting receivers."""
        return self.balance < 0

    def has_sender(self):
        """Whether this Channel has any waiting senders."""
        return self.balance > 0
    
    def send_exception(self, *args, **kwargs):
        """Send an exception trough the channel instead of some value. This will immediatly raise the exception in the receiver."""
        self._channel.send_exception(*args, **kwargs)

    def receive(self, timeout = -1):
        """Receive from the channel. If there is no sender, the caller will block until there is one.
        Optionally you can specify a *timeout*. If a sender does not show up within the *timeout* period a
        :class:`TimeoutError` is raised. The method returns the value given by the sender.""" 
        if timeout == -1:
            #most common without timeout
            return self._channel.receive()
        else:
            current_task = Tasklet.current()
            def on_timeout():
                current_task.raise_exception(TimeoutError)
            event_timeout = TimeoutEvent(timeout, on_timeout)
            try:
                return self._channel.receive()
            finally:
                event_timeout.close()

    def send(self, value, timeout = -1):
        """Sends to the channel. If there is no receiver, the caller will block until there is one.
        If a receiver is present, the *value* will be passed to the receiver and execution will continue in the 
        receiver. 
        Optionally you can specify a *timeout*. If a receiver does not show up within the *timeout* period a
        :class:`TimeoutError` is raised.""" 
        if timeout == -1: 
            #most common without timeout
            self._channel.send(value)
        else:
            #setup timeout event
            current_task = Tasklet.current()
            def on_timeout():
                current_task.raise_exception(TimeoutError)
            event_timeout = TimeoutEvent(timeout, on_timeout)
            try:
                self._channel.send(value)
            finally:
                event_timeout.close()

_running = False #whether we are currently in dispatch, used stop the dispatch (use quit method)
_exitcode = EXIT_CODE_OK

def quit(exitcode = EXIT_CODE_OK):
    """Quits the concurrence program and exit to the OS with *exitcode*"""
    global _running
    global _exitcode
    _exitcode = exitcode
    _running = False
    
#monkey patch sys exit to call our quit in order
#to properly finish our dispatch loop
sys._exit = sys.exit
sys.exit = quit

def _print_objects(objs):
    d = {}
    for x in objs:
        if hasattr(x, '__class__'):
            name = x.__class__.__module__ + '.' + x.__class__.__name__
            if name in d:
                d[name] += 1
            else:
                d[name] = 1

    for name, count in sorted(d.items()):
        print name, count

def disable_threading():
    """Monkey patches python libs so that all threading stuff is gone"""
    from concurrence import _threading
    _threading.disable_threading()
    
def _dispatch(f = None):
    """The main dispatch routine. This is the starting point of any Concurrence program. 
    The dispatcher schedules tasklets until the :func:`quit` function is called or a SIGINT signal is received.
    As a convenience a callable *f* can be provided that will be run in a new Tasklet."""
    #first install signal handler
    #this way we can quit the program easily from the command line 
    #also, this makes libevent block on the first loop
    #otherwise when there are no events in the beginning, loop will not 
    #block and our main dispatch loop would claim 100% CPU time
    def interrupt():
        quit(EXIT_CODE_SIGINT)
    event_interrupt = SignalEvent(SIGINT, interrupt)
    
    #the heartbeat makes sure the main loop below at least
    #makes a cycle every second. otherwise, if there are no pending signals
    #libevent._loop would block indefinitly, causing our loop never to check
    #if it still must be _running...
    event_heartbeat = TimeoutEvent(1.0, None, True)
    
    if callable(f):
        Tasklet.new(f)()
        
    global _running
    _running = True
    try:
        #this is it, the main dispatch loop...
        #tasklets are scheduled to run by stackless, 
        #and if no more are runnable, we wait for IO events to happen
        #that will trigger tasks to become runnable
        #ad infinitum...
        while _running:
            try:
                while stackless.getruncount() > 1:
                    stackless.schedule()
            except TaskletExit:
                pass
            except:
                logging.exception("unhandled exception in dispatch schedule")
            #note that we changed the way pyevent notifies us of pending events
            #instead of calling the callbacks from within the pyevent extension
            #it returns the list of callbacks that have to be called.
            #calling from pyevent would give us a C stack which is not
            #optimal (stackless would hardswitch instead of softswitch)
            triggered = _event.loop()
            while triggered:
                callback, evtype = triggered.popleft()
                try:
                    callback(evtype)
                except TaskletExit:
                    raise
                except:
                    logging.exception("unhandled exception in dispatch event callback")
    finally:
        event_interrupt.close()
        event_heartbeat.close()
        
    if DEBUG_LEAK: 
        logging.warn("alive objects:")
        gc.collect()
        _print_objects(gc.get_objects())
        logging.warn('garbage:')
        _print_objects(gc.garbage)

    sys._exit(_exitcode)

def _profile(f = None):
    import resource 
    def cpu():
        return (resource.getrusage(resource.RUSAGE_SELF).ru_utime +
                resource.getrusage(resource.RUSAGE_SELF).ru_stime)

    from cProfile import Profile
    prof = Profile(cpu)
    try:
        prof = prof.runctx("_dispatch(f)", globals(), locals())
    except SystemExit:
        pass    

    import pstats
    stats = pstats.Stats(prof)
    stats.strip_dirs()
    stats.sort_stats('time')
    stats.print_stats(20)
        
def dispatch(f = None):
    if '-Xprofile' in sys.argv:
        _profile(f)
    else:
        _dispatch(f)

