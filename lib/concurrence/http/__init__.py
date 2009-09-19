# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class HTTPError(Exception): pass

class HTTPRequest(object):
    """A class representing a HTTP request."""
    
    def __init__(self, path = None, method = None, host = None):
        """Create a new http request for *path* using *method* to *host*."""
        self.path = path
        self.method = method
        self.host = host
        self.headers = []
        self._body = None

    def add_header(self, key, value):
        """Adds a new header to the request with name *key* and given *value*."""        
        self.headers.append((key, value))

    def _set_body(self, body):
        if body is not None: 
            assert type(body) == str
            self.add_header('Content_length', len(body))
        self._body = body

    def _get_body(self):
        return self._body

    body = property(_get_body, _set_body, doc = 'sets *body* data for the request')

class HTTPResponse(object):
    """Represents a HTTP Response."""
    
    def __init__(self):
        self.headers = []
        self.status = ''
        self.iter = None

    @property
    def status_code(self):
        """Returns the HTTP response code as an integer."""
        return int(self.status.split()[1])

    @property
    def status_reason(self):
        """Returns the reason part of the HTTP response line as a string."""
        return self.status.split()[2]

    def get_header(self, key, default = None):
        """Gets the HTTP response header with the given case-insensitive *key*. Returns *default*
        if the header is not found."""
        key = key.lower()
        for (_key, value) in self.headers:
            if key == _key.lower():
                return value
        return default

    def add_header(self, key, value):
        """Adds a new header to the response with name *key* and given *value*."""
        self.headers.append((key, value))

    @property
    def body(self):
        """Returns the body of the response as a string."""
        return ''.join(list(self.iter))

    def __iter__(self):
        return iter(self.iter)

from concurrence.http.server import WSGIServer
from concurrence.http.client import HTTPConnection
