# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence import Tasklet, Channel, TaskletError
from concurrence.timer import Timeout
from concurrence.io.socket import Socket
from concurrence.io.buffered import BufferedStream
from concurrence.containers.deque import Deque

import cPickle as pickle

#TODO async set
#proper buffer sizes
#bundling of multiple requests in 1 flush
#statistics
#not use pickle for string and unicode types (use flags to indicate this)
#timeout on commands (for clients, support Timeout.current)
#plugable serialization support (and/or provide choise, default (py-serialized, utf-8 encoded json, etc)?
#todo detect timeouts on write/read, and mark host as dead
#keep some time before retrying host
#global consistent hashing algorithm for accessing set of memcached servers

#rename MemcacheNode to MemcacheConnection.
#first, there will be max 1 connection to each host in the system

class MemcacheError(Exception):
    pass

class MemcacheNode(object):
    """this represents the connection/protocol to 1 memcached host
    this class supports concurrent usage of get/set methods by multiple
    tasks, the cmds are queued and performed in order agains the memcached host.    
    """
    def __init__(self):
        self._stream = None

    def connect(self, addr):
        assert self._stream is None, "must not be disconneted before connecting"
        self._stream = BufferedStream(Socket.connect(addr, Timeout.current()))
        self._command_queue = Deque()
        self._response_queue = Deque()
        self._command_writer_task = Tasklet.new(self._command_writer)()
        self._response_reader_task = Tasklet.new(self._response_reader)()

    def _read_response(self, reader):
        cmd, block_channel = self._response_queue.popleft(True)
        try:
            if cmd == 'get':
                result = {} #we will gather 'get' results here
            else:
                result = True
            while True:
                response_line = reader.read_line()
                if cmd == 'get' and response_line.startswith('VALUE'):
                    response_fields = response_line.split(' ')
                    key = response_fields[1]
                    flags = int(response_fields[2])
                    n = int(response_fields[3])
                    encoded_value = reader.read_bytes(n)
                    reader.read_line() #\r\n
                    result[key] = pickle.loads(encoded_value)
                elif cmd == 'get' and response_line == 'END':
                    block_channel.send(result)
                    break                            
                elif cmd == 'set' and response_line == 'STORED':
                    block_channel.send(result)
                    break        
                else:
                    assert False, "unknown protocol state, cmd: %s, response_line: %s" % (cmd, response_line)
        except Exception, e:
            block_channel.send_exception(TaskletError, e, Tasklet.current())
            raise 

    def _write_command(self, writer):
        try:
            cmd, args, block_channel = self._command_queue.popleft(True)
            writer.clear()
            if cmd == 'get':
                writer.write_bytes("get")
                for key in args[0]:
                    writer.write_bytes(" " + key)
            elif cmd in ['set']:
                key, value, flags = args           
                encoded_value = pickle.dumps(value, -1)
                writer.write_bytes("%s %s %d 0 %d\r\n" % (cmd, key, flags, len(encoded_value)))
                writer.write_bytes(encoded_value)
            else:
                assert False, "unknown command %s" % cmd
            writer.write_bytes('\r\n')
            writer.flush()
            self._response_queue.append((cmd, block_channel))
        except Exception, e:
            block_channel.send_exception(TaskletError, e, Tasklet.current())
            raise

    def _response_reader(self):
        reader = self._stream.reader
        while True:
            try:
                self._read_response(reader)
            except Exception, e:
                self.close(e, False, True)
                return #this ends reader
            
    def _command_writer(self):
        writer = self._stream.writer       
        while True:
            try:
                self._write_command(writer)
            except Exception, e:
                self.close(e, True, False)
                return #this ends writer

    def _do_command(self, cmd, *args):
        block_channel = Channel()
        self._command_queue.append((cmd, args, block_channel))
        try:
            return block_channel.receive()
        except TaskletError, e:
            raise MemcacheError(str(e.cause))

    def close(self, exception = None, kill_reader = True, kill_writer = True):
        #assert False, reason
        if kill_reader:     
            self._response_reader_task.kill()
        if kill_writer:
            self._command_writer_task.kill()
        self._response_reader_task = None
        self._command_writer_task = None
        #raise exception on all waiting tasks still in the queues
        for cmd, args, block_channel in self._command_queue:
            block_channel.send_exception(TaskletError, e, Tasklet.current())
        for cmd, block_channel in self._response_queue:
            block_channel.send_exception(TaskletError, e, Tasklet.current())
        self._command_queue = None
        self._response_queue = None
        self._stream.close()
        self._stream = None
        
    def set(self, key, data, flags = 0):
        self._do_command("set", key, data, flags)

    def _get_one(self, key):
        result = self._do_command("get", [key])
        if key in result:
            return result[key]
        else:
            return None

    def get(self, keys):
        if type(keys) == str:
            return self._get_one(keys)
        else:
            return self._do_command("get", keys)
            

