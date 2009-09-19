# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import dispatch, Tasklet, Message
from concurrence.io import Server, Connector, BufferedStream

import logging
import weakref
#import cPickle as pickle
import pickle #TODO why does unittest segfault on cPickle?

#TODO timeouts and exceptions for 'calls'
#TODO management of remote clients (e.g. we could drop the connection if there are no more calls for some time)
#TODO option for private connections and option to turn of auto-flushing, for high troughput asyn messaging

class ObjectReader(object):
    """used to serialize msgs and other objects between a remote server and client"""
    def __init__(self, reader):
        self._unpickler = pickle.Unpickler(reader.file())

    def read_object(self):
        return self._unpickler.load()
       
        
class ObjectWriter(object):
    """used to serialize msgs and other objects between a remote server and client"""
    def __init__(self, writer):
        self._file = writer.file()
        self._pickler = pickle.Pickler(self._file, 2)

    def write_object(self, o):
        self._pickler.dump(o)

    def flush(self):
        self._file.flush()

class MSG_LOOKUP(Message): pass
class MSG_RESULT(Message): pass

class RemoteMessage(Message):
    """proxy of a message in the remote (server side) process"""
    def __init__(self, remote_stream, remote_msg_class, remote_msg_id):
        self._remote_stream = remote_stream
        self._remote_msg_class = remote_msg_class
        self._remote_msg_id = remote_msg_id
        
    def reply(self, result):
        self._remote_stream.write_result_msg(self._remote_msg_id, result)

    def match(self, cls):
        return issubclass(self._remote_msg_class, cls)
        
    @classmethod
    def send(cls, receiver, *args):
        assert False, "NOT AVAILABLE"
    
    @classmethod
    def call(cls, receiver, *args):        
        assert False, "NOT AVAILABLE"
    
    def wait(self):
        assert False, "NOT AVAILABLE"
    
class RemoteStream(object):
    """represents the object stream on the remote (server) side process"""
    def __init__(self, client_stream):
        self._client_stream = BufferedStream(client_stream)
        self._object_reader = ObjectReader(self._client_stream.reader)
        self._object_writer = ObjectWriter(self._client_stream.writer)

    def write_result_msg(self, remote_msg_id, result):
        self._object_writer.write_object((MSG_RESULT, (remote_msg_id, result)))
        self._object_writer.flush()            
    
    def read_msg(self):
        return self._object_reader.read_object()

class RemoteServer(object):
    """remoting server, use this to expose a Task to clients in other processes.
    Use the 'register' method to expose a task. This task will then respond to msgs
    send by clients in other tasks"""
    log = logging.getLogger('RemoteServer')

    def __init__(self):
        self._task_by_name = weakref.WeakValueDictionary()
        self._task_id_by_task = weakref.WeakKeyDictionary()
        self._task_by_task_id = weakref.WeakValueDictionary()
        #the task with id 0 is always available, it provides bootstrap services (e.g. name->task lookup)
        self._task_by_task_id[0] = Tasklet.new(self._bootstrap_service)()

    def _bootstrap_service(self):
        while True:
            for msg, args, kwargs in Tasklet.receive():
                if msg.match(MSG_LOOKUP):
                    name = args[0]
                    if name in self._task_by_name:
                        task_id = self._task_id_by_task.get(self._task_by_name[name], 0)
                    else:
                        task_id = 0
                    msg.reply(task_id)
    

    def handle(self, client_stream):
        #TODO timeout on handling
        remote_stream = RemoteStream(client_stream)
        while True:
            try:
                receiver_task_id, msg_class, msg_id, args, kwargs = remote_stream.read_msg()
            except EOFError:
                break 
            #create a local proxy of the remote msg:        
            msg = RemoteMessage(remote_stream, msg_class, msg_id)
            #send the msg to the task with task_id
            receiver_task = self._task_by_task_id.get(receiver_task_id, None)
            if receiver_task is None:
                self.log.warn("receiver task could not be found for remote msg delivery")
            else:
                receiver_task.send(msg, *args, **kwargs)

    def register(self, name, task = None):  
        if task is None: 
            task = Tasklet.current()
        task_id = id(task)
        self._task_by_name[name] = task        
        self._task_id_by_task[task] = task_id
        self._task_by_task_id[task_id] = task 
        
    def serve(self, endpoint):  
        return Server.serve(endpoint, self.handle)

class RemoteClient(object):
    """Remoteing client. This represents the connection to the remote server.
    Use the lookup method to get a reference to a remote task.
    This reference can then be used to send or call msgs to the remote tasks
    """
    def __init__(self):
        self._stream = None
        self._message_writer_task = None
        self._message_reader_task = None
        self._bootstrap_task = RemoteTasklet(self, 0) #proxy to the remote bootstrap service
        self._blocked_message = {} #message_id -> message, for keeping track of blocking calls

    def _message_writer(self):
        object_writer = ObjectWriter(self._stream.writer)
        for msg, (remote_task_id, args), kwargs in Tasklet.receive():
            object_writer.write_object((remote_task_id, msg.__class__, id(msg), args, kwargs))
            object_writer.flush()
    
    def _message_reader(self):
        object_reader = ObjectReader(self._stream.reader)
        while True:
            msg, args  = object_reader.read_object()
            if issubclass(msg, MSG_RESULT):
                msg_id, result = args
                if msg_id in self._blocked_message:
                    self._blocked_message[msg_id].reply(result)
                else:
                    pass #this happens when caller already gone due to timeout
        
    def connect(self, endpoint):
        self._stream = BufferedStream(Connector.connect(endpoint))
        self._message_writer_task = Tasklet.new(self._message_writer)()
        self._message_reader_task = Tasklet.new(self._message_reader)()

    def close(self):
        self._message_writer_task.kill()
        self._message_reader_task.kill()
        self._stream.close()
        
    def send(self, remote_task_id, msg, args, kwargs):
        self._message_writer_task.send(msg, remote_task_id, args)        
                
    def call(self, remote_task_id, timeout, msg, args, kwargs):
        msg_id = id(msg)
        self._blocked_message[msg_id] = msg
        try:         
            self.send(remote_task_id, msg, args, kwargs)
            result = msg.wait(timeout)
            return result
        finally:
            del self._blocked_message[msg_id]

    def lookup(self, name):
        remote_task_id = MSG_LOOKUP.call(self._bootstrap_task)(name)
        if remote_task_id > 0:
            return RemoteTasklet(self, remote_task_id)
        else:
            return None

class RemoteTasklet(object):
    """Proxy to a remote task. Do not create this yourself, use lookup method on a RemoteClient"""
    def __init__(self, remote_client, remote_task_id):
        self._remote_client = remote_client
        self._remote_task_id = remote_task_id
        
    def send(self, msg, *args, **kwargs):
        assert isinstance(msg, Message)
        self._remote_client.send(self._remote_task_id, msg, args, kwargs)
    
    def call(self, msg, timeout, *args, **kwargs):
        assert isinstance(msg, Message)
        return self._remote_client.call(self._remote_task_id, timeout, msg, args, kwargs)
        

