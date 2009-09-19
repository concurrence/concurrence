# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO try wait read/write optimzation, e.g. don't wait, but try, if EAGAIN, then wait. 
#if ok, then next time expect no wait, otherwise next time expect wait

import logging
import _socket
import types
import os

from errno import EALREADY, EINPROGRESS, EWOULDBLOCK, ECONNRESET, ENOTCONN, ESHUTDOWN, EINTR, EISCONN, ENOENT, EAGAIN

import _io

from concurrence import Tasklet, FileDescriptorEvent
from concurrence.io import IOStream

DEFAULT_BACKLOG = 255    

class Socket(IOStream):
    log = logging.getLogger('Socket')
    
    STATE_INIT = 0
    STATE_LISTENING = 1
    STATE_CONNECTING = 2
    STATE_CONNECTED = 3
    STATE_CLOSING = 4
    STATE_CLOSED = 5
    
    def __init__(self, socket, state = STATE_INIT):
        """don't call directly pls use one of the provided classmethod to create a socket"""
        self.socket = socket

        if _socket.AF_INET == socket.family:
            #always set the nodelay option on tcp sockets. This turns off the Nagle algorithm
            #we don't need this because in concurrence we are always buffering ourselves
            #before sending out data, so no need to let the tcp stack do it again and possibly delay
            #sending
            try:
                self.socket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
            except:
                self.log.warn("could not set TCP_NODELAY")
         
        #concurrence sockets are always non-blocking, this is the whole idea :-) :              
        self.socket.setblocking(0)        
        self.fd = self.socket.fileno()
        self._readable = None #will be created lazily
        self._writable = None #will be created lazily
        self.state = state

    @classmethod
    def from_address(cls, addr):
        """Creates a new socket from the given address. If the addr is a tuple (host, port)
        a normal tcp socket is assumed. if addr is a string, a UNIX Domain socket is assumed"""
        if type(addr) == types.StringType:
            return cls(_socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)) 
        else:
            return cls(_socket.socket(_socket.AF_INET, _socket.SOCK_STREAM))
    
    @classmethod
    def new(cls):
        return cls(_socket.socket(_socket.AF_INET, _socket.SOCK_STREAM))

    @classmethod
    def connect(cls, addr, timeout = -1):
        """creates a new socket and connects it to the given address.
        returns the connected sockets"""
        socket = cls.from_address(addr)
        socket._connect(addr, timeout)        
        return socket
    
    @classmethod
    def from_file_descriptor(cls, fd, socket_family = _socket.AF_UNIX, socket_type = _socket.SOCK_STREAM, socket_state = STATE_INIT):
        return cls(_socket.fromfd(fd, socket_family, socket_type), socket_state)
    
    def _get_readable(self):
        if self._readable is None:
            self._readable = FileDescriptorEvent(self.fd, 'r')
        return self._readable
  
    def _set_readable(self, readable):
        self._readable = readable
    
    readable = property(_get_readable, _set_readable)

    def _get_writable(self):
        if self._writable is None:
            self._writable = FileDescriptorEvent(self.fd, 'w')
        return self._writable
  
    def _set_writable(self, writable):
        self._writable = writable
    
    writable = property(_get_writable, _set_writable)
    
    def fileno(self):
        return self.fd
    
    def set_reuse_address(self, reuse_address):
        self.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, int(reuse_address))
        
    def bind(self, addr):
        self.socket.bind(addr)
        
    def listen(self, backlog = DEFAULT_BACKLOG):
        self.socket.listen(backlog)
        self.state = self.STATE_LISTENING
        
    def accept(self):
        """waits on a listening socket, returns a new socket_class instance
        for the incoming connection"""
        assert self.state == self.STATE_LISTENING, "make sure socket is listening before calling accept"
        while True:
            #we need a loop because sometimes we become readable and still not a valid 
            #connection was accepted, in which case we return here and wait some more.
            self.readable.wait()
            try:        
                s, _ = self.socket.accept()
            except _socket.error, (errno, _):
                if errno in [EAGAIN, EWOULDBLOCK]:
                    #this can happen when more than one process received readability on the same socket (forked/cloned/dupped)
                    #in that case 1 process will do the accept, the others receive this error, and should continue waiting for
                    #readability 
                    continue 
                else:
                    raise 
            
            return self.__class__(s, self.STATE_CONNECTED)

    def _connect(self, addr, timeout = -1.0):
        assert self.state == self.STATE_INIT, "make sure socket is not already connected or closed"
        try:
            err = self.socket.connect_ex(addr)
            serr = self.socket.getsockopt(_socket.SOL_SOCKET, _socket.SO_ERROR)
        except:
            self.log.exception("unexpected exception thrown by connect_ex")
            raise  
        if err == 0 and serr == 0:
            self.state = self.STATE_CONNECTED
        elif err == EINPROGRESS and serr != 0:
            raise IOError(serr, os.strerror(serr))
        elif err == EINPROGRESS and serr == 0:                    
            self.state = self.STATE_CONNECTING
            try:
                self.writable.wait(timeout = timeout)
                self.state = self.STATE_CONNECTED
            except:
                self.state = self.STATE_INIT
                raise
        else:
            #some other error,  
            #unix domain socket that does not exist, Cannot assign requested address etc etc
            raise _io.error_from_errno(IOError)
        
    def write(self, buffer, timeout = -1.0):
        """Blocks till socket becomes writable and then writes as many bytes as possible from given
        buffer to the socket. The buffer position is updated according to the number of bytes read from it.
        This method could possible write 0 bytes. The method returns the total number of bytes written"""
        assert self.state == self.STATE_CONNECTED, "socket must be connected in order to write to it"        
        self.writable.wait(timeout = timeout)
        bytes_written, _ = buffer.send(self.fd) #write to fd from buffer
        if bytes_written < 0:
            raise _io.error_from_errno(IOError)
        else:
            return bytes_written

    def read(self, buffer, timeout = -1.0):
        """Blocks till socket becomes readable and then reads as many bytes as possible the socket into the given
        buffer. The buffer position is updated according to the number of bytes read from the socket.
        This method could possible read 0 bytes. The method returns the total number of bytes read"""
        assert self.state == self.STATE_CONNECTED, "socket must be connected in order to read from it"
        self.readable.wait(timeout = timeout)
        bytes_read, _ = buffer.recv(self.fd) #read from fd to 
        if bytes_read < 0:
            raise _io.error_from_errno(IOError)
        else:
            return bytes_read

    def write_socket(self, socket, timeout = -1):
        """writes a socket trough this socket"""
        self.writable.wait(timeout = timeout)
        _io.msgsendfd(self.fd, socket.fd)
        
    def read_socket(self, socket_class = None, socket_family =  _socket.AF_INET, socket_type = _socket.SOCK_STREAM, socket_state = STATE_INIT, timeout = -1):
        """reads a socket from this socket"""
        self.readable.wait(timeout = timeout)
        fd = _io.msgrecvfd(self.fd)
        return (socket_class or self.__class__).from_file_descriptor(fd, socket_family, socket_type, socket_state)        
                   
    def is_closed(self):
        return self.state == self.STATE_CLOSED 
    
    def close(self):
        assert self.state in [self.STATE_CONNECTED, self.STATE_LISTENING]
        self.state = self.STATE_CLOSING
        if self._readable is not None:
            self._readable.close()
        if self._writable is not None:
            self._writable.close()
        self.socket.close()          
        del self.socket
        del self._readable
        del self._writable
        self.state = self.STATE_CLOSED

class SocketServer(object):
    log = logging.getLogger('SocketServer')

    def __init__(self, endpoint, handler = None):
        self._addr = None
        self._socket = None
        if isinstance(endpoint, Socket):
            self._socket = endpoint
        else:
            self._addr = endpoint
        self._handler = handler
        self._reuseaddress = True
        self._handler_task_name = 'socket_handler'
        self._accept_task = None
        self._accept_task_name = 'socket_acceptor'
        
    @property
    def socket(self):
        return self._socket

    def _handle_accept(self, accepted_socket):
        result = None
        try:
            result = self._handler(accepted_socket)
        except TaskletExit:
            raise
        except:
            self.log.exception("unhandled exception in socket handler")
        finally:
            if result is None and not accepted_socket.is_closed():
                try:
                    accepted_socket.close()
                except TaskletExit:
                    raise
                except:
                    self.log.exception("unhandled exception while forcefully closing client")
        
    def _create_socket(self):
        if self._socket is None:
            if self._addr is None:
                assert False, "address must be set or accepting socket must be explicitly set"
            self._socket = Socket.from_address(self._addr)
            self._socket.set_reuse_address(self._reuseaddress)            
        return self._socket 
        
    def _accept_task_loop(self):
        accepted_socket = self._socket.accept()
        Tasklet.new(self._handle_accept, self._handler_task_name)(accepted_socket)
        
    def bind(self):
        """creates socket if needed, and binds it"""
        socket = self._create_socket()
        socket.bind(self._addr)

    def listen(self, backlog = DEFAULT_BACKLOG):
        """creates socket if needed, and listens it"""
        socket = self._create_socket()
        socket.listen(backlog)
        
    def serve(self):
        """listens and starts a new tasks accepting incoming connections on the configured address"""
        if self._socket is None:
            self.bind()
            self.listen()

        if not callable(self._handler):
            assert False, "handler not set or not callable"
        
        self._accept_task = Tasklet.loop(self._accept_task_loop, name = self._accept_task_name, daemon = True)()

    def close(self):
        self._accept_task.kill()
        self._socket.close()
        
        
        
        
