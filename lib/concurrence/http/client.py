# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO timeout
#TODO asyn dns resolve

import time
import logging

from concurrence import Tasklet, Channel, Message, __version__
from concurrence.timer import Timeout
from concurrence.io import Connector, BufferedStream
from concurrence.http import HTTPError, HTTPRequest, HTTPResponse

AGENT = 'Concurrence-Http-Client/' + __version__

CHUNK_SIZE = 1024 * 4

class HTTPConnection(object):
    """A HTTP 1.1 Client.
    
    Usage:: 
    
        #create an instance of this class and connect to a webserver using the connect method:
        cnn = HTTPConnection() 
        cnn.connect(('www.google.com', 80))
        
        #create a GET request using the get method:
        request = cnn.get('/index.html')
        
        #finally perform the request to get a response:
        response = cnn.perform(request)
        
        #do something with the response:
        print response.body
    
    """

    log = logging.getLogger('HTTPConnection')

    def connect(self, endpoint):
        """Connect to the webserver at *endpoint*. *endpoint* is a tuple (<host>, <port>)."""
        self._host = None
        if type(endpoint) == type(()):
            try:
                self._host = endpoint[0]
            except: 
                pass                
        self._stream = BufferedStream(Connector.connect(endpoint))

    def receive(self):
        """Receive the next :class:`HTTPResponse` from the connection."""
        try:
            return self._receive()
        except TaskletExit:
            raise
        except EOFError:
            raise HTTPError("EOF while reading response")
        except Exception:
            self.log.exception('')
            raise HTTPError("Exception while reading response")
        
    def _receive(self):

        response = HTTPResponse()

        reader = self._stream.reader
        
        lines = reader.read_lines()
                
        #parse status line
        response.status = lines.next()
        
        #rest of response headers
        for line in lines:
            if not line: break
            key, value = line.split(': ')
            response.add_header(key, value)

        #read data
        transfer_encoding = response.get_header('Transfer-Encoding', None)
        
        try:
            content_length = int(response.get_header('Content-Length'))
        except:
            content_length = None

        #TODO better support large data        
        chunks = []

        if transfer_encoding == 'chunked':
            while True:
                chunk_line = reader.read_line()
                chunk_size = int(chunk_line.split(';')[0], 16)
                if chunk_size > 0:
                    data = reader.read_bytes(chunk_size)
                    reader.read_line() #chunk is always followed by a single empty line
                    chunks.append(data)
                else:
                    reader.read_line() #chunk is always followed by a single empty line
                    break 
        elif content_length is not None:
            while content_length > 0:
                n = min(CHUNK_SIZE, content_length)
                data = reader.read_bytes(n)
                chunks.append(data)
                content_length -= len(data)
        else:
            assert False, 'TODO'

        response.iter = chunks

        return response

    def get(self, path, host = None):
        """Returns a new :class:`HTTPRequest` with request.method = 'GET' and request.path = *path*.
        request.host will be set to the host used in :func:`connect`, or optionally you can specify a
        specific *host* just for this request.
        """
        request = HTTPRequest()
        request.method = 'GET'
        request.path = path
        request.host = host or self._host
        return request

    def post(self, path, body = None, host = None):
        """Returns a new :class:`HTTPRequest` with request.method = 'POST' and request.path = *path*.
        request.host will be set to the host used in :func:`connect`, or optionally you can specify a
        specific *host* just for this request.
        *body* is an optional string containing the data to post to the server.
        """
        request = HTTPRequest()
        request.method = 'POST'
        request.path = path
        request.host = host or self._host
        if body is not None:
           request.body = body
        return request

    def perform(self, request):
        """Sends the *request* and waits for and returns the :class:`HTTPResult`."""
        self.send(request)
        return self.receive()

    def send(self, request):
        """Sends the *request* on this connection."""
        if request.method is None:
            assert False, "request method must be set"
        if request.path is None:
            assert False, "request path must be set"
        if request.host is None:
            assert False, "request host must be set"

        writer = self._stream.writer        
        writer.clear()
        writer.write_bytes("%s %s HTTP/1.1\r\n" % (request.method, request.path))
        writer.write_bytes("Host: %s\r\n" % request.host)
        for header_name, header_value in request.headers:
            writer.write_bytes("%s: %s\r\n" % (header_name, header_value))
        writer.write_bytes("\r\n")
        if request.body is not None:
           writer.write_bytes(request.body)
        writer.flush()        

    def close(self):
        """Close this connection."""
        self._stream.close()
