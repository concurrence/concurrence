# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO write timeout

from __future__ import with_statement

import logging
import urlparse
import httplib
import traceback
import rfc822

from concurrence import Tasklet, Message, Channel, TimeoutError, __version__
from concurrence.io import Server, BufferedStream
from concurrence.containers import ReorderQueue
from concurrence.timer import Timeout
from concurrence.http import HTTPError

SERVER_ID = "Concurrence-Http/%s" % __version__

CHUNK_SIZE = 1024 * 4

HTTP_READ_TIMEOUT = 300 #default read timeout, if no request was read within this time, the connection is closed by server


class WSGIInputStream(object):
    def __init__(self, request, reader):
        transfer_encoding = request.get_request_header('Transfer-Encoding')
        if transfer_encoding is not None and transfer_encoding == 'chunked':
            assert False, 'chunked post not supported yet'

        content_length = request.get_request_header('Content-length')
        if content_length is None:
            self._channel = None
            self._n = None
            self._file = None        
        else:
            self._n = int(content_length)
            self._file = reader.file()
            self._channel = Channel()
    
    def _read_request_data(self):
        if self._n is not None:
            self._channel.receive() #wait till handler has read all input data

    def read(self, n):  
        if self._n > 0:
            data = self._file.read(min(self._n, n))
            self._n -= len(data)
            if self._n == 0:
                self._n = None
                self._file = None
                self._channel.send(True) #unblock reader
                self._channel = None
            return data
        else:
            return '' #EOF
        
    def readline(self):
        assert False, 'TODO'

    def readlines(self):
        assert False, 'TODO'

    def __iter__(self):
        assert False, 'TODO'


class WSGIErrorStream(object):
    def write(self, s):
        logging.error(s)

    def writelines(self, s):
        assert False, 'TODO'

    def flush(self):
        assert False, 'TODO'

        
class WSGIRequest(object):
    log = logging.getLogger('WSGIRequest')
    
    STATE_INIT = 0
    STATE_WAIT_FOR_REQUEST = 1
    STATE_READING_HEADER = 2
    STATE_READING_DATA = 3
    STATE_REQUEST_READ = 4
    STATE_WRITING_HEADER = 5
    STATE_WRITING_DATA = 6
    STATE_FINISHED = 7
    
    _disallowed_application_headers = set(['Date', 'Server'])

    def __init__(self, server):
        self._server = server        
        self.version = None #http version
        self.environ = {}
        self.response_headers = []
        self.status = httplib.NOT_FOUND #or internal server error?
        self.exc_info = None     
        self.state = self.STATE_INIT   
        
    def start_response(self, status, response_headers, exc_info = None):
        self.status = status
        self.response_headers = response_headers
        self.exc_info = exc_info

    def get_response_header(self, key):
        for (_key, value) in self.response_headers:
            if _key == key:
                return value
        return None
        
    def get_request_header(self, key):
        http_key = 'HTTP_' + key.replace('-', '_').upper()
        return self.environ.get(http_key, None)

    def write_response(self, response, writer):
        self.state = self.STATE_WRITING_HEADER
        
        if self.version == 'HTTP/1.0':
            chunked = False
        else:
            chunked = True

        writer.clear()
        
        writer.write_bytes("%s %s\r\n" % (self.version, self.status))        
        for header_name, header_value in self.response_headers:
            if header_name in self._disallowed_application_headers: continue
            writer.write_bytes("%s: %s\r\n" % (header_name, header_value))
        writer.write_bytes("Date: %s\r\n" % rfc822.formatdate())
        writer.write_bytes("Server: %s\r\n" % SERVER_ID) 

        if chunked:
            writer.write_bytes("Transfer-Encoding: chunked\r\n")
        else:
            response = ''.join(response)
            writer.write_bytes("Content-length: %d\r\n" % len(response))
        
        writer.write_bytes("\r\n")
    
        self.state = self.STATE_WRITING_DATA
        
        if chunked:
            for chunk in response:
                writer.write_bytes("%x;\r\n" % len(chunk))
                writer.write_bytes(chunk)
                writer.write_bytes("\r\n")
                
            writer.write_bytes("0\r\n\r\n")
        else:
            writer.write_bytes(response)

        writer.flush() #TODO use special header to indicate no flush needed
        
        self.state = self.STATE_FINISHED
    
    def handle_request(self, application):
        try:
            return application(self.environ, self.start_response)
        except TaskletExit:
            raise
        except:
            self.log.exception("unhandled exception while handling request")
            return self._server.internal_server_error(self.environ, self.start_response)
      
    def read_request_data(self):
        self.environ['wsgi.input']._read_request_data()

    def read_request(self, reader):
        with Timeout.push(self._server.read_timeout):
            self._read_request(reader)

    def _read_request(self, reader):

        self.state = self.STATE_WAIT_FOR_REQUEST
        
        #setup readline iterator        
        lines = reader.read_lines()
        
        #parse status line, this will block to read the first request line
        line = lines.next().split()
        
        self.state = self.STATE_READING_HEADER
        
        u = urlparse.urlparse(line[1])
        
        self.method = line[0]
        if self.method not in ['GET', 'POST']:
            raise HTTPError('Unsupported method: %s' % self.method)

        #TODO validate version
        self.version = line[2]
        self.uri = line[1]

        #build up the WSGI environment
        self.environ['REQUEST_METHOD'] = line[0]
        self.environ['SCRIPT_NAME'] = '' #TODO
        self.environ['PATH_INFO'] = u[2]
        self.environ['QUERY_STRING'] = u[4]
        
        self.environ['wsgi.url_scheme'] = 'http'
        self.environ['wsgi.multiprocess'] = False
        self.environ['wsgi.multithread'] = True
        self.environ['wsgi.run_once'] = False
        self.environ['wsgi.version'] = (1, 0)
        
        #rest of request headers
        for line in lines:
            if not line: break
            key, value = line.split(': ')
            key = key.replace('-', '_').upper()
            value = value.strip()
            
            http_key = 'HTTP_' + key 
            if http_key in self.environ:
                self.environ[http_key] += ',' + value # comma-separate multiple headers
            else:
                self.environ[http_key] = value

        #wsgi complience 
        if 'HTTP_CONTENT_LENGTH' in self.environ:
            self.environ['CONTENT_LENGTH'] = self.environ['HTTP_CONTENT_LENGTH']

        if 'HTTP_CONTENT_TYPE' in self.environ:
            self.environ['CONTENT_TYPE'] = self.environ['HTTP_CONTENT_TYPE']

        #setup required wsgi streams
        self.environ['wsgi.input'] = WSGIInputStream(self, reader)
        self.environ['wsgi.errors'] = WSGIErrorStream()
        
        if not 'HTTP_HOST' in self.environ:
            if self.version == 'HTTP/1.0':
                #ok in version 1.0, TODO what should host in wsgi environ be?
                host = 'localhost'
            else:
                raise HTTPError('Host header field is required in HTTP version > 1.0')
        else:
            host = self.environ['HTTP_HOST']

        if ':' in host:
            host, port = host.split(':')
        else:
            host, port = host, 80

        self.environ['SERVER_NAME'] = host
        self.environ['SERVER_PORT'] = port
        self.environ['SERVER_PROTOCOL'] = self.version
        
        self.state = self.STATE_REQUEST_READ
        

class HTTPHandler(object):
    log = logging.getLogger('HTTPHandler')

    class MSG_REQUEST_HANDLED(Message): pass
    class MSG_WRITE_RESPONSE(Message): pass
    class MSG_RESPONSE_WRITTEN(Message): pass
    class MSG_REQUEST_READ(Message): pass
    class MSG_READ_ERROR(Message): pass
    class MSG_WRITE_ERROR(Message): pass
    
    def __init__(self, server):
        self._server = server     
        self._reque = ReorderQueue()

    def write_responses(self, control, stream):        
        try:
            for msg, (request, response), kwargs in Tasklet.receive():
                request.write_response(response, stream.writer)
                self.MSG_RESPONSE_WRITTEN.send(control)(request, response)
        except Exception, e:
            self.log.exception("Exception in writer")
            self.MSG_WRITE_ERROR.send(control)(None, None)

    def read_requests(self, control, stream):
        try:
            while True:
                request = WSGIRequest(self._server)
                request.read_request(stream.reader)                
                self.MSG_REQUEST_READ.send(control)(request, None)
                request.read_request_data()
        except EOFError, e:
            if request.state == request.STATE_WAIT_FOR_REQUEST:
                pass #this is normal at the end of the http KA connection (client closes) 
        except IOError, e:
            if e.errno == 104 and request.state == request.STATE_WAIT_FOR_REQUEST:
                pass #connection reset by peer while waiting for request
        except TimeoutError, e:
            self.log.warn("Timeout in reader")
        except Exception, e:
            self.log.exception("Exception in reader")

        self.MSG_READ_ERROR.send(control)(None, None)

    def handle_request(self, control, request, application):
        response = self._server.handle_request(request, application)
        self.MSG_REQUEST_HANDLED.send(control)(request, response)       

    def handle(self, socket, application):
        stream = BufferedStream(socket)
        #implements http1.1 keep alive handler
        #there are several concurrent tasks for each connection; 
        #1 for reading requests, 1 or more for handling requests and 1 for writing responses
        #the current task (the one created to handle the socket connection) is the controller task,
        #e.g. it coordinates the actions of it's children by message passing
        control = Tasklet.current()

        #writes responses back to the client when they are ready:
        response_writer = Tasklet.new(self.write_responses, name = 'response_writer')(control, stream)
        #reads requests from clients:
        request_reader = Tasklet.new(self.read_requests, name = 'request_reader')(control, stream)

        #typical flow:
        #1. reader reads in request, sends notification to control (MSG_REQUEST_READ)
        #2. control starts handler for the request
        #3. handler works on request and sends notification to control when finished (MSG_REQUEST_HANDLED)
        #4. control sends message to writer to start writing the response (MSG_WRITE_RESPONSE)
        #5. writer notififies control when response is wriiten (MSG_RESPONSE_WRITTEN)

        #control wait for msgs to arrive:        
        for msg, (request, response), kwargs in Tasklet.receive():
            if msg.match(self.MSG_REQUEST_READ):
                #we use reque to be able to send the responses back in the correct order later
                self._reque.start(request)
                Tasklet.new(self.handle_request, name = 'request_handler')(control, request, application)
                
            elif msg.match(self.MSG_REQUEST_HANDLED):
                #we use reque to retire (send out) the responses in the correct order
                for request, response in self._reque.finish(request, response):
                    self.MSG_WRITE_RESPONSE.send(response_writer)(request, response)
                    
            elif msg.match(self.MSG_RESPONSE_WRITTEN):
                if request.version == 'HTTP/1.0':
                    break #no keep-alive support in http 1.0
                elif request.get_response_header('Connection') == 'close':
                    break #response indicated to close after response
                elif request.get_request_header('Connection') == 'close':
                    break #request indicated to close after response
            elif msg.match(self.MSG_READ_ERROR):
                break #stop and close the connection
            elif msg.match(self.MSG_WRITE_ERROR):
                break #stop and close the connection
            else:   
                assert False, "unexpected msg in control loop"

        #kill reader and writer
        #any outstanding request will continue, but will exit by themselves
        response_writer.kill()
        request_reader.kill()
   
        #close our side of the socket
        stream.close()
        
class WSGIServer(object):
    """A HTTP/1.1 Web server with WSGI application interface.
    
    Usage:: 
    
        def hello_world(environ, start_response):
            start_response("200 OK", [])
            return ["<html>Hello, world!</html>"]

        server = WSGIServer(hello_world)
        server.serve(('localhost', 8080))
    """
    log = logging.getLogger('WSGIServer')
    
    read_timeout = HTTP_READ_TIMEOUT

    def __init__(self, application, request_log_level = logging.DEBUG):
        """Create a new WSGIServer serving the given *application*. Optionally
        the *request_log_level* can be given. This loglevel is used for logging the requests."""
        self._application = application
        self._request_log_level = request_log_level

    def internal_server_error(self, environ, start_response):
        """Default WSGI application for creating a default `500 Internal Server Error` response on any
        unhandled exception.
        The default response will render a traceback with a text/plain content-type.
        Can be overridden to provide a custom response."""           
        start_response('500 Internal Server Error', [('Content-type', 'text/plain')])
        return [traceback.format_exc(20)]

    def handle_request(self, request, application):
        """All HTTP requests pass trough this method. 
        This method provides a hook for logging, statistics and or further processing w.r.t. the *request*."""
        response = request.handle_request(application)
        self.log.log(self._request_log_level, "%s %s", request.status, request.uri)
        return response
        
    def handle_connection(self, socket):
        """All HTTP connections pass trough this method.
        This method provides a hook for logging, statistics and or further processing w.r.t. the connection."""
        HTTPHandler(self).handle(socket, self._application)

    def serve(self, endpoint):
        """Serves the application at the given *endpoint*. The *endpoint* must be a tuple (<host>, <port>)."""
        return Server.serve(endpoint, self.handle_connection)
                        

