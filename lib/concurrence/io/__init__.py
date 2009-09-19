# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

    
from _io import Buffer, BufferOverflowError, BufferUnderflowError, BufferInvalidArgumentError

class IOStream(object):
    """abstract class to indicate that something is a stream and capable
    of the basic read and write ops on a buffer"""
    def write(self, buffer, timeout = -1.0):
        """should write available bytes from the buffer into stream and return
        the number of bytes written (could be less than available), or 0 on EOF
        or raise error, or timeout"""

    def read(self, buffer, timeout = -1.0):
        """should read from the stream into buffer and return number of bytes read, or 0 on EOF
        or raise error, or timeout"""
        pass
    
from concurrence.io.socket import Socket, SocketServer
from concurrence.io.buffered import BufferedReader, BufferedWriter, BufferedStream

#TODO what if more arguments are needed for connect?, eg. passwords etc?
class Connector(object):
    """connector class for connection oriented IO  (TCP), prevents the need for client protocol libraries to hardcode a 
    particular way to achieve a connection (e.g. no need to explicitly reference sockets"""
    @classmethod
    def connect(cls, endpoint):
        if isinstance(endpoint, Connector):
            assert False, "TODO"
        else:
            #default is to connect to Socket and endpoint is address
            from concurrence.io.socket import Socket
            from concurrence.timer import Timeout
            return Socket.connect(endpoint, Timeout.current())

class Server(object):
    """server class for connection oriented IO (TCP), prevents the need for server protocol libraries to hardcode a 
    particular way to serve a connection (e.g. no need to explicitly reference Server Sockets"""
    @classmethod
    def serve(cls, endpoint, handler):
        if isinstance(endpoint, Server):
            assert False, "TODO"
        else:
            #default is to server using SocketServer, endpoint is addresss  
            from concurrence.io.socket import SocketServer
            socket_server = SocketServer(endpoint, handler)
            socket_server.serve()
            return socket_server

