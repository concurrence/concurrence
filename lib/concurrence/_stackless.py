# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

"""This module implements the stackless API on top of py.magic greenlet API
This way it is possible to run concurrence applications on top of normal python
using the greenlet module.
Because the greenlet module uses only 'hard' switching as opposed to stackless 'soft' switching
it is a bit slower (about 35%), but very usefull because you don't need to install stackless.
Note that this does not aim to be a complete implementation of stackless on top of greenlets,
just enough of the stackless API to make concurrence run.
This code was inspired by:
http://aigamedev.com/programming-tips/round-robin-multi-tasking and
also by the pypy implementation of the same thing (buggy, not being maintained?) at 
https://codespeak.net/viewvc/pypy/dist/pypy/lib/stackless.py?view=markup
"""

try:
    from py.magic import greenlet #as of version 1.0 of py, it does not supply greenlets anymore
except ImportError:
    from greenlet import greenlet #there is an older package containing just the greenlet lib

from collections import deque

class TaskletExit(SystemExit):pass

import __builtin__
__builtin__.TaskletExit = TaskletExit


class bomb(object):
    """used as a result value for sending exceptions trough a channel"""
    def __init__(self, exc_type = None, exc_value = None, exc_traceback = None):
        self.type = exc_type
        self.value = exc_value
        self.traceback = exc_traceback

    def raise_(self):
        raise self.type, self.value, self.traceback

class channel(object):
    """implementation of stackless's channel object"""
    def __init__(self):
        self.balance = 0
        self.queue = deque()
        
    def receive(self):
        return _scheduler._receive(self)

    def send(self, data):
        return _scheduler._send(self, data)

    def send_exception(self, exp_type, *args):
        self.send(bomb(exp_type, exp_type(*args)))

    def send_sequence(self, iterable):
        for item in iterable:
            self.send(item)
        

            
class tasklet(object):
    """implementation of stackless's tasklet object"""
    
    def __init__(self, f = None, greenlet = None, alive = False):
        self.greenlet = greenlet
        self.func = f
        self.alive = alive
        self.blocked = False
        self.data = None
        
    def bind(self, func):
        if not callable(func):
            raise TypeError('tasklet function must be a callable')
        self.func = func

    def __call__(self, *args, **kwargs):
        """this is where the new task starts to run, e.g. it is where the greenlet is created
        and the 'task' is first scheduled to run"""
        if self.func is None:
            raise TypeError('tasklet function must be a callable')

        def _func(*_args, **_kwargs):
            try:
                self.func(*args, **kwargs)
            except TaskletExit:
                pass #let it pass silently
            except:
                import logging
                logging.exception('unhandled exception in greenlet')
                #don't propagate to parent
            finally:
                assert _scheduler.current == self
                _scheduler.remove(self)
                if _scheduler._runnable: #there are more tasklets scheduled to run next
                    #this make sure that flow will continue in the correct greenlet, e.g. the next in the schedule
                    self.greenlet.parent = _scheduler._runnable[0].greenlet
                self.alive = False            
                del self.greenlet
                del self.func
                del self.data

        self.greenlet = greenlet(_func)
        self.alive = True
        _scheduler.append(self)
        return self

    def kill(self):
        _scheduler.throw(self, TaskletExit)

    def raise_exception(self, *args):
        _scheduler.throw(self, *args)

    def __str__(self):
        return repr(self)

    def __repr__(self):
        if hasattr(self, 'name'):
            _id = self.name
        else:
            _id = str(self.func)
        return '<tasklet %s at %0x>' % (_id, id(self))

class scheduler(object):
    def __init__(self):
        self._main_task = tasklet(greenlet = greenlet.getcurrent(), alive = True) 
        #all non blocked tast are in this queue
        #all tasks are only onces in this queue
        #the current task is the first item in the queue
        self._runnable = deque([self._main_task])
    
    def schedule(self):
        """schedules the next tasks and puts the current task back at the queue of runnables"""
        self._runnable.rotate(-1)
        next_task = self._runnable[0]
        next_task.greenlet.switch()
        
    def schedule_block(self):
        """blocks the current task and schedules next"""
        self._runnable.popleft()
        next_task = self._runnable[0]
        next_task.greenlet.switch()

    def throw(self, task, *args):
        if not task.alive: return #this is what stackless does
        
        assert task.blocked or task in self._runnable

        task.greenlet.parent = self._runnable[0].greenlet
        if task.blocked:
            self._runnable.appendleft(task)
        else:
            self._runnable.remove(task)
            self._runnable.appendleft(task)

        task.greenlet.throw(*args) 


    def _receive(self, channel):
        #Receiving 1):
        #A tasklet wants to receive and there is
        #a queued sending tasklet. The receiver takes
        #its data from the sender, unblocks it,
        #and inserts it at the end of the runnables.
        #The receiver continues with no switch.
        #Receiving 2):
        #A tasklet wants to receive and there is
        #no queued sending tasklet.
        #The receiver will become blocked and inserted
        #into the queue. The next sender will
        #handle the rest through "Sending 1)".        
        if channel.queue: #some sender
            channel.balance -= 1
            sender = channel.queue.popleft()
            sender.blocked = False
            self._runnable.append(sender)
            data, sender.data = sender.data, None
        else: #no sender
            current = self._runnable[0]
            channel.queue.append(current)
            channel.balance -= 1
            current.blocked = True
            try:    
                self.schedule_block()
            except:
                channel.queue.remove(current)
                channel.balance += 1
                current.blocked = False
                raise

            data, current.data = current.data, None

        if isinstance(data, bomb):
            data.raise_()
        else:
            return data

    def _send(self, channel, data):
        #  Sending 1):
        #    A tasklet wants to send and there is
        #    a queued receiving tasklet. The sender puts
        #    its data into the receiver, unblocks it,
        #    and inserts it at the top of the runnables.
        #    The receiver is scheduled.
        #  Sending 2):
        #    A tasklet wants to send and there is
        #    no queued receiving tasklet.
        #    The sender will become blocked and inserted
        #    into the queue. The next receiver will
        #    handle the rest through "Receiving 1)".     
        #print 'send q', channel.queue   
        if channel.queue: #some receiver   
            channel.balance += 1
            receiver = channel.queue.popleft()
            receiver.data = data
            receiver.blocked = False
            self._runnable.rotate(-1)
            self._runnable.appendleft(receiver)
            self._runnable.rotate(1)
            self.schedule()
        else: #no receiver
            current = self.current
            channel.queue.append(current)
            channel.balance += 1
            current.data = data
            current.blocked = True
            try:
                self.schedule_block()
            except:
                channel.queue.remove(current)
                channel.balance -= 1
                current.data = None
                current.blocked = False
                raise
        
    def remove(self, task):
        assert task.blocked or task in self._runnable
        if task in self._runnable:
            self._runnable.remove(task)
    
    def append(self, task):
        assert task not in self._runnable
        self._runnable.append(task)
        
    @property
    def runcount(self):
        return len(self._runnable) 

    @property
    def current(self):
        return self._runnable[0]

#there is only 1 scheduler, this is it:
_scheduler = scheduler()

def getruncount():
    return _scheduler.runcount

def getcurrent():
    return _scheduler.current

def schedule():
    return _scheduler.schedule()


