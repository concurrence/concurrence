# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import types

cdef extern from "sys/socket.h":
    int recv(int, void *, int, int)
    int send(int, void *, int, int)

cdef extern from "string.h":
    cdef void *memmove(void *, void *, int)
    cdef void *memcpy(void *, void *, int)
    cdef void *memchr(void *, int, int)
     
cdef extern from "stdlib.h":
    cdef void *calloc(int, int)
    cdef void free(void *)    

cdef extern from "Python.h":
    object PyString_FromStringAndSize(char *, int)
    object PyString_FromString(char *)
    int PyString_AsStringAndSize(object obj, char **s, Py_ssize_t *len) except -1

cdef extern from "pyerrors.h":    
    object PyErr_SetFromErrno(object)
    
cdef extern from "io_base.h":
    int sendfd(int, int)
    int recvfd(int)
    
def error_from_errno(object exc):
    return PyErr_SetFromErrno(exc)

class BufferError(Exception):
    pass

class BufferOverflowError(BufferError):
    pass

class BufferUnderflowError(BufferError):
    pass

class BufferInvalidArgumentError(BufferError):
    pass


cdef class Buffer:
    """Creates a :class:`Buffer` object. The buffer class forms the basis for IO in the Concurrence Framework.
    The buffer class represents a mutable array of bytes of that can be read from and written to using the
    read_XXX and write_XXX methods. 
    Operations on the buffer are performed relative to the current :attr:`position` attribute of the buffer.
    A buffer also has a current :attr:`limit` property above which no data may be read or written. 
    If an operation tries to read beyond the current :attr:`limit` a BufferUnderflowError is raised. If an operation 
    tries to write beyond the current :attr:`limit` a BufferOverflowError is raised.
    The general idea of the :class:`Buffer` was shamelessly copied from java NIO. 
    """

    def __cinit__(self, int capacity, Buffer parent = None):
        if parent is not None: 
            #this is a copy contructor for a shallow
            #copy, e.g. we reference the same data as our parent, but have our
            #own position and limit (use .duplicate method to get the copy)
            self._parent = parent #this incs the refcnt on parent
            self._buff = parent._buff
            self._position = parent._position
            self._limit = parent._limit
            self.capacity = parent.capacity
        else:
            #normal constructor
            self._parent = None
            self.capacity = capacity
            self._buff = <unsigned char *>(calloc(1, self.capacity))
        
    def __dealloc__(self):
        if self._parent is None:
            free(self._buff)
        else:
            self._parent = None #releases our refcnt on parent             
        
    def __init__(self, int capacity, Buffer parent = None):
        """Create a new empty buffer with the given *capacity*."""
        self.clear()

    def duplicate(self):
        """Return a shallow copy of the Buffer, e.g. the copied buffer 
        references the same bytes as the original buffer, but has its own
        independend position and limit."""
        return Buffer(0, self)
        
    def copy(self, Buffer src, int src_start, int dst_start, int length):
        """Copies *length* bytes from buffer *src*, starting at position *src_start*, to this
        buffer at position *dst_start*."""
        if length < 0:
            raise BufferInvalidArgumentError("length must be >= 0")
        if src_start < 0:
            raise BufferInvalidArgumentError("src start must be >= 0")
        if src_start > src.capacity:
            raise BufferInvalidArgumentError("src start must <= src capacity")
        if src_start + length > src.capacity:
            raise BufferInvalidArgumentError("src start + length must <= src capacity")
        if dst_start < 0:
            raise BufferInvalidArgumentError("dst start must be >= 0")
        if dst_start > self.capacity:
            raise BufferInvalidArgumentError("dst start must <= dst capacity")
        if dst_start + length > self.capacity:
            raise BufferInvalidArgumentError("dst start + length must <= dst capacity")
        #now we can safely copy!
        memcpy(self._buff + dst_start, src._buff + src_start, length)        
        
    def clear(self):
        """Prepares the buffer for relative read operations. The buffers :attr:`limit` will set to the buffers :attr:`capacity` and
        its :attr:`position` will be set to 0."""
        self._limit = self.capacity
        self._position = 0

    def flip(self):
        """Prepares the buffer for relative write operations. The buffers :attr:`limit` will set to the buffers :attr:`position` and
        its :attr:`position` will be set to 0."""
        self._limit = self._position
        self._position = 0

    def rewind(self):
        """Sets the buffers :attr:`position` back to 0."""
        self._position = 0

    cdef int _skip(self, int n) except -1:
        if self._position + n <= self.limit:
            self._position = self._position + n
            return n
        else:
            raise BufferUnderflowError()
        
    def skip(self, int n):
        """Updates the buffers position by skipping n bytes. It is not allowed to skip passed the current :attr:`limit`. 
        In that case a :exc:`BufferUnderflowError` will be raised and the :attr:`position` will remain the same"""
        return self._skip(n)
                
    cdef int _remaining(self):
        return self._limit - self._position

    property remaining:
        def __get__(self):
            return self._limit - self._position

    property limit:
        def __get__(self):
            return self._limit
        
        def __set__(self, limit):
            if limit >= 0 and limit <= self.capacity and limit >= self._position:
                self._limit = limit
            else:
                if limit < 0:
                    raise BufferInvalidArgumentError("limit must be >= 0")
                elif limit > self.capacity:
                    raise BufferInvalidArgumentError("limit must be <= capacity")
                elif limit < self._position:
                    raise BufferInvalidArgumentError("limit must be >= position")
                else:
                    raise BufferInvalidArgumentError() 

    property position:
        def __get__(self):
            return self._position
        
        def __set__(self, position):
            if position >= 0 and position <= self.capacity and position <= self._limit:
                self._position = position
            else:
                if position < 0:
                    raise BufferInvalidArgumentError("position must be >= 0")
                elif position > self.capacity:
                    raise BufferInvalidArgumentError("position must be <= capacity")
                elif position > self._limit:
                    raise BufferInvalidArgumentError("position must be <= limit")
                else:                    
                    raise BufferInvalidArgumentError()
                                                
    cdef int _read_byte(self) except -1:
        cdef int b
        if self._position + 1 <= self._limit:             
            b = self._buff[self._position]
            self._position = self._position + 1
            return b
        else:
            raise BufferUnderflowError()
                                                        
    def read_byte(self):
        """Reads and returns a single byte from the buffer and updates the :attr:`position` by 1."""
        return self._read_byte()
        
    def recv(self, int fd):
        """Reads as many bytes as will fit up till the :attr:`limit` of the buffer from the filedescriptor *fd*.
        Returns a tuple (bytes_read, bytes_remaining). If *bytes_read* is negative, a IO Error was encountered. 
        The :attr:`position` of the buffer will be updated according to the number of bytes read.
        """
        cdef int b
        b = recv(fd, self._buff + self._position, self._limit - self._position, 0)
        if b > 0: self._position = self._position + b
        return b, self._limit - self._position

    def send(self, int fd):
        """Sends as many bytes as possible up till the :attr:`limit` of the buffer to the filedescriptor *fd*.
        Returns a tuple (bytes_written, bytes_remaining). If *bytes_written* is negative, an IO Error was encountered.
        """
        cdef int b
        b = send(fd, self._buff + self._position, self._limit - self._position, 0)
        if b > 0: self._position = self._position + b
        return b, self._limit - self._position
        
    def compact(self):
        """Prepares the buffer again for relative reading, but any left over data still present in the buffer (the bytes between
        the current :attr:`position` and current :attr:`limit`) will be copied to the start of the buffer. The position of the buffer
        will be right after the copied data.
        """
        cdef int n
        n = self._limit - self._position 
        if n > 0 and self._position > 0:
            if n < self._position: 
                memcpy(self._buff + 0, self._buff + self._position, n)
            else:
                memmove(self._buff + 0, self._buff + self._position, n)
        self._position = n
        self._limit = self.capacity

    def __getitem__(self, object i):
        cdef int start, end, stride
        if type(i) == types.IntType:
            if i >= 0 and i < self.capacity:
                return self._buff[i]
            else:        
                raise BufferInvalidArgumentError("index must be >= 0 and < capacity")
        elif type(i) == types.SliceType:
            start, end, stride = i.indices(self.capacity)
            return PyString_FromStringAndSize(<char *>(self._buff + start), end - start)
        else:
            raise BufferInvalidArgumentError("wrong index type")

    def __setitem__(self, object i, object value):
        cdef int start, end, stride
        cdef char *b 
        cdef Py_ssize_t n
        if type(i) == types.IntType:
            if type(value) != types.IntType:
                raise BufferInvalidArgumentError("value must be integer")
            if value < 0 or value > 255:
                raise BufferInvalidArgumentError("value must in range [0..255]")
            if i >= 0 and i < self.capacity:
                self._buff[i] = value
            else:
                raise BufferInvalidArgumentError("index must be >= 0 and < capacity")
        elif type(i) == types.SliceType:
            start, end, stride = i.indices(self.capacity)
            PyString_AsStringAndSize(value, &b, &n)
            if n != (end - start):
                raise BufferInvalidArgumentError("incompatible slice")
            memcpy(self._buff + start, b, n)
        else:
            raise BufferInvalidArgumentError("wrong index type")
        
    def read_short(self):
        """Read a 2 byte little endian integer from buffer and updates position."""
        cdef int s
        if 2 > (self._limit - self._position):
            raise BufferUnderflowError()
        else:
             s = self._buff[self._position] + (self._buff[self._position + 1] << 8)
             self._position = self._position + 2
             return s
        
    cdef object _read_bytes(self, int n):
        """reads n bytes from buffer, updates position, and returns bytes as a python string"""
        if n > (self._limit - self._position):
            raise BufferUnderflowError()
        else:
            s = PyString_FromStringAndSize(<char *>(self._buff + self._position), n)
            self._position = self._position + n
            return s
            
    def read_bytes(self, int n = -1):
        """Reads n bytes from buffer, updates position, and returns bytes as a python string,
        if there are no n bytes available, a :exc:`BufferUnderflowError` is raised."""
        if n == -1:
            return self._read_bytes(self._limit - self._position)
        else:
            return self._read_bytes(n)
    
    def read_bytes_until(self, int b):
        """Reads bytes until character b is found, or end of buffer is reached in which case it will raise a :exc:`BufferUnderflowError`."""
        cdef int n, maxlen
        cdef char *zpos, *start 
        if b < 0 or b > 255:
            raise BufferInvalidArgumentError("b must in range [0..255]")
        maxlen = self._limit - self._position
        start = <char *>(self._buff + self._position)
        zpos = <char *>(memchr(start, b, maxlen))
        if zpos == NULL:
            raise BufferUnderflowError()
        else:
            n = zpos - start
            s = PyString_FromStringAndSize(start, n)
            self._position = self._position + n + 1
            return s

    def read_line(self, int include_separator = 0):
        """Reads a single line of bytes from the buffer where the end of the line is indicated by either 'LF' or 'CRLF'.
        The line will be returned as a string not including the line-separator. Optionally *include_separator* can be specified
        to make the method to also return the line-separator."""
        cdef int n, maxlen
        cdef char *zpos, *start 
        maxlen = self._limit - self._position
        start = <char *>(self._buff + self._position)
        zpos = <char *>(memchr(start, 10, maxlen))
        if zpos == NULL:
            raise BufferUnderflowError()
        else:
            n = zpos - start
            if self._buff[self._position + n - 1] == 13: #\r\n
                if include_separator:
                    s = PyString_FromStringAndSize(start, n + 1)
                    self._position = self._position + n + 1
                else:
                    s = PyString_FromStringAndSize(start, n - 1)
                    self._position = self._position + n + 1
            else: #\n
                if include_separator:
                    s = PyString_FromStringAndSize(start, n + 1)
                    self._position = self._position + n + 1
                else:
                    s = PyString_FromStringAndSize(start, n)
                    self._position = self._position + n + 1                                    
            return s
    
    def scan_until_xmltoken(self):
        # < == 60, > == 62, ? == 63, / == 47
        # retval '<' = 0, '>' = 1, '</' = 2, '/>' = 3, '<?' = 4, '?>' = 5
        cdef int p, l
        
        if self._position == self._limit:
            raise BufferUnderflowError()
        
        p = self._position
        l = self._limit - 1
        while p < l:
            if self._buff[p] == 60 and self._buff[p + 1] == 47: # '</'
                self._position = p + 2
                return 2
            elif self._buff[p] == 47 and self._buff[p + 1] == 62: # '/>'
                self._position = p + 2
                return 3
            elif self._buff[p] == 60 and self._buff[p + 1] == 63: # '<?'
                self._position = p + 2
                return 4
            elif self._buff[p] == 63 and self._buff[p + 1] == 62: # '?>'
                self._position = p + 2
                return 5
            elif self._buff[p] == 60: # '<'
                self._position = p + 1
                return 0
            elif self._buff[p] == 62: # '>'
                self._position = p + 1
                return 1
            else:
                p = p + 1

        #we can also report '>' at end of buffer
        if self._buff[p] == 62: # '>'
            self._position = p + 1
            return 1

        raise BufferUnderflowError()
        
    def write_bytes(self, s):
        """Writes a number of bytes given by the python string s to the buffer and updates position. Raises 
        :exc:`BufferOverflowError` if you try to write beyond the current :attr:`limit`."""
        cdef char *b 
        cdef Py_ssize_t n
        PyString_AsStringAndSize(s, &b, &n)
        if n > (self._limit - self._position):
            raise BufferOverflowError()
        else:
            memcpy(self._buff + self._position, b, n)
            self._position = self._position + n
            return n

    def write_buffer(self, Buffer other):
        """writes available bytes from other buffer to this buffer"""
        self.write_bytes(other.read_bytes(-1)) #TODO use copy
                
    cdef int _write_byte(self, unsigned int b) except -1:
        """writes a single byte to the buffer and updates position"""
        if self._position + 1 <= self._limit:             
            self._buff[self._position] = b
            self._position = self._position + 1
            return 1
        else:
            raise BufferOverflowError()

    def write_byte(self, unsigned int b):
        """writes a single byte to the buffer and updates position"""
        return self._write_byte(b)

    def write_int(self, unsigned int i):
        """writes a 32 bit integer to the buffer and updates position (little-endian)"""
        if self._position + 4 <= self._limit:             
            self._buff[self._position + 0] = (i >> 0) & 0xFF
            self._buff[self._position + 1] = (i >> 8) & 0xFF
            self._buff[self._position + 2] = (i >> 16) & 0xFF
            self._buff[self._position + 3] = (i >> 24) & 0xFF
            self._position = self._position + 4
            return 4
        else:
            raise BufferOverflowError()

    def write_short(self, unsigned int i):
        """writes a 16 bit integer to the buffer and updates position (little-endian)"""
        if self._position + 2 <= self._limit:             
            self._buff[self._position + 0] = (i >> 0) & 0xFF
            self._buff[self._position + 1] = (i >> 8) & 0xFF
            self._position = self._position + 2
            return 2
        else:
            raise BufferOverflowError()
        
    
    def __repr__(self):
        s = []
        for i in range(min(16, self.capacity)):
            s.append('%02x' % self._buff[i])
        return '<Buffer object at %x, pos=%d, lim=%d, cap=%d,\n\t[%s]>' % (id(self), self.position, self.limit, self.capacity, ' '.join(s))
    
    def __str__(self):
        return repr(self)
    
def msgsendfd(dst_fd, fd):
    return sendfd(dst_fd, fd)

def msgrecvfd(src_fd):
    return recvfd(src_fd)



