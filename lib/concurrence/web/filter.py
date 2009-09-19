# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from __future__ import with_statement

import httplib
import logging
import traceback
import time

from concurrence.web import Filter
from concurrence import json, TimeoutError

class JSONFilter(Filter):
    def __call__(self, next, *args, **kwargs):
        try:
            self.response.content_type = 'application/json'
            return next(*args, **kwargs)
        except TaskletExit:
            raise
        except Exception, e:
            logging.exception("exception in json request")
            if self.response.status_int < 400:
                self.response.status = httplib.INTERNAL_SERVER_ERROR
            return json.dumps({'message': unicode(e), 'trace': unicode(traceback.format_exc(10))})
    
from concurrence.timer import Timeout

class TimeoutFilter(Filter):
    """a filter that checks the request headers for a timeout header
    and sets a timeout for this request as required"""
    def __call__(self, next, *args, **kwargs):
        timeout = float(self.request.environ.get('HTTP_TIMEOUT', '-1'))
        with Timeout.push(timeout):
            return next(*args, **kwargs)
