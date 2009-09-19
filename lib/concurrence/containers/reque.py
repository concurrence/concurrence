# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from collections import deque

class ReorderQueue(object):
    
    def __init__(self):
        self._finished = {}
        self._queue = deque()

    def start(self, request):
        """notes the start of a request"""
        self._queue.append(request)

    def finish(self, request, response):
        """finishes the given request with its corresponding response and yields
        any available (request, response) in order"""
        self._finished[request] = response
        while True:
            if self._queue and self._queue[0] in self._finished:
                request = self._queue.popleft()
                response = self._finished[request]
                del self._finished[request]
                yield (request, response)
            else:
                break

