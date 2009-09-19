from concurrence import unittest
from concurrence.io import IOStream
from concurrence.io.buffered import Buffer, BufferedReader

class TestStream(IOStream):
    def __init__(self, s, chunk_size = 4):
        self.s = s
        self.chunk_size = chunk_size
        
    def read(self, buffer, timeout = -1.0):

        if not self.s:
            raise EOFError("while reading")

        n = min(self.chunk_size, buffer.remaining, len(self.s))

        buffer.write_bytes(self.s[:n])

        self.s = self.s[n:]

        return n

class TestBuffered(unittest.TestCase):
    def testCompatibleReadLines(self):
        
        for chunk_size in [4, 8, 16, 32, 64, 128]:
            b = Buffer(1024)

            test_stream = TestStream('hello world!\nTest\n\nPiet\nKlaas\nPietBlaat\n', chunk_size = chunk_size)
            
            f = BufferedReader(test_stream, b).file()
            
            lines = f.readlines()

            self.assertEquals('hello world!\n', lines.next())
            self.assertEquals('Test\n', lines.next())
            self.assertEquals('\n', lines.next())
            self.assertEquals('Piet\n', lines.next())
            self.assertEquals('Klaas\n', lines.next())
            self.assertEquals('PietBlaat\n', lines.next())
            self.assertEquals('', lines.next())

        
            #line without newline at end of buffer, should report without newline
            test_stream = TestStream('hello world!\nTest', chunk_size = chunk_size)
            f = BufferedReader(test_stream, b).file()
            lines = f.readlines()
            self.assertEquals('hello world!\n', lines.next())
            self.assertEquals('Test', lines.next())
            self.assertEquals('', lines.next())
        
    def testCompatibleRead(self):
        import cStringIO

        for buffer_size in [1, 2, 4, 8, 16, 32, 1024]:
            for chunk_size in [1, 2, 4, 8, 16]:
                def test_stream(s):
                    b = Buffer(buffer_size)
                    f = BufferedReader(TestStream(s, chunk_size = chunk_size), b).file()
                    i = cStringIO.StringIO(s)
                    return (i, f)

                i, f = test_stream('piet')

                self.assertEquals(i.read(8), f.read(8))
                self.assertEquals(i.read(8), f.read(8))  
                    
                i, f = test_stream('piet')
                
                self.assertEquals(i.read(2), f.read(2))
                self.assertEquals(i.read(2), f.read(2))
                self.assertEquals(i.read(4), f.read(4))
                self.assertEquals(i.read(4), f.read(4))

                i, f = test_stream('piet')
                
                self.assertEquals(i.read(2), f.read(2))
                self.assertEquals(i.read(4), f.read(4))

                for x in range(30):
                    i, f = test_stream('piet klaas aap' * x)
                    self.assertEquals(i.read(), f.read())

    
if __name__ == '__main__':
    unittest.main(timeout = 10)


