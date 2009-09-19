# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

def disable_threading():
    import sys

    import thread
    sys.modules['thread'] = thread
    import threading
    sys.modules['threading'] = threading
    import dummy_thread
    sys.modules['dummy_thread'] = dummy_thread
    import dummy_threading
    sys.modules['dummy_threading'] = dummy_threading
    import logging
    logging.logThreads = 0

    #for name, _ in sys.modules.items():
    #    print name, _
