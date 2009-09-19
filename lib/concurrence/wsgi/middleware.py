# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import logging
import httplib
import os
import mimetypes

class WSGISimpleResponse(object):
    def __init__(self, status_code = httplib.OK, response = None, content_type = 'text/html', headers = []):
        self.status_code = status_code
        self.response = response
        self.content_type = content_type
        self.headers = headers

    def __call__(self, environ, start_response):
        response_text = httplib.responses[self.status_code]
        response_line = "%d %s" % (self.status_code, response_text)
        start_response(response_line, [('Content-type', self.content_type)] + self.headers)
        if self.response is None:
            return [response_text]
        else:
            return [self.response]

RESPONSE_NOT_FOUND = WSGISimpleResponse(httplib.NOT_FOUND)

class WSGISimpleMessage(WSGISimpleResponse):
    def __init__(self, msg):
        WSGISimpleResponse.__init__(self, httplib.OK, msg)
        
class WSGISimpleStatic(WSGISimpleResponse):
    log = logging.getLogger('WSGISimpleStatic')

    def __init__(self, root, prefix):
        self._map = {}
        self._load(root)
        self._root = root
        self._prefix = prefix
        self._not_found = RESPONSE_NOT_FOUND

    def _load(self, root):
        if os.path.isfile(root):
            self._load_file(root, root)
        elif os.path.isdir(root):
            for dirpath, dirnames, filenames in os.walk(root):
                for filename in filenames:
                    self._load_file(root, os.path.join(dirpath, filename))                    
        else:
            assert False, "unknown path type (not a file or dir)"

    def _load_file(self, root, path):
        f = open(path)
        content = f.read()
        f.close()
        content_type, _ = mimetypes.guess_type(path, False)
        if content_type is None:
            assert False, "unknown content type"
        content_length = len(content)
        path = path[len(root):]
        self.log.debug("preloading %s => %d, %s", path, content_length, content_type)
        self._map[path] = (content, content_type, content_length)

    def __call__(self, environ, start_response):
        path_info = environ['PATH_INFO'][len(self._prefix):]
        if path_info in self._map:
            content, content_length, content_type = self._map[path_info]
            response_line = "%d %s" % (200, httplib.responses[200])
            start_response(response_line, [('Content-Type', content_type), ('Content-Length', content_length)])
            return [content]            
        else:     
            return self._not_found(environ, start_response) 

class WSGISimpleRouter(object):
    """a simple router middleware to dispatch to applications based on uri-path"""
    def __init__(self):
        self._mapping = []
        self._not_found = RESPONSE_NOT_FOUND
        
    def map(self, path, application):
        self._mapping.append((path, application))
        
    def __call__(self, environ, start_response):
        path_info = environ['PATH_INFO']
        for path, application in self._mapping:
            if path_info.startswith(path):
                return application(environ, start_response)
        return self._not_found(environ, start_response)        

