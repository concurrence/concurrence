
from concurrence import unittest, dispatch, TimeoutError, Tasklet
from concurrence.core import FileDescriptorEvent
from concurrence.io import Socket


class TestIO(unittest.TestCase):
    def testReadableWritableProperties(self):
        
        socket = Socket.new()
        writable = socket.writable
        self.assertTrue(isinstance(writable, FileDescriptorEvent))
        readable = socket.readable
        self.assertTrue(isinstance(readable, FileDescriptorEvent))

        socket.readable = None

        #TODO test why is socket.readable event not deallocated immediatly?

if __name__ == '__main__':
    unittest.main(timeout = 10.0)
