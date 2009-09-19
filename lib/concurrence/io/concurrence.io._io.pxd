# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

cdef class Buffer:
    cdef unsigned char *_buff
    cdef Buffer _parent
    cdef readonly int capacity
    cdef int _limit
    cdef int _position

    cdef int _skip(self, int n) except -1                
    cdef int _remaining(self)
    cdef int _read_byte(self) except -1
    cdef int _write_byte(self, unsigned int b) except -1

    cdef object _read_bytes(self, int n)
