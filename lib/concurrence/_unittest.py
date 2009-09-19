# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import unittest
import logging

from concurrence import dispatch, Tasklet, quit 
from concurrence.core import EXIT_CODE_TIMEOUT

from concurrence.io import IOStream


class TestCase(unittest.TestCase):
    def setUp(self):
        logging.debug(self)

    def tearDown(self):
        try:
            Tasklet.yield_() #this make sure that everything gets a change to exit before we start the next test
        except:
            pass

def main(timeout = None):

    logging.basicConfig()
    logging.root.setLevel(logging.DEBUG)

    if timeout is not None:
        Tasklet.later(timeout, quit, name = 'unittest_timeout')(EXIT_CODE_TIMEOUT)
        
    dispatch(unittest.main)
