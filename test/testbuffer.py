from concurrence import unittest
from concurrence.io.buffered import Buffer, BufferUnderflowError, BufferInvalidArgumentError

class TestBuffer(unittest.TestCase):
    def testDuplicate(self):

        b = Buffer(1024)
        c = b.duplicate()
        
        self.assertEqual(b.position, c.position)
        self.assertEqual(b.limit, c.limit)
        self.assertEqual(b.capacity, c.capacity)

        b.write_bytes('test')

        #check that position is independend from c
        self.assertNotEqual(b.position, c.position)
        self.assertEqual(b.limit, c.limit)
        self.assertEqual(b.capacity, c.capacity)

        #but data buffer should be shared with c, so c should be able to read it
        self.assertEquals('test', c.read_bytes(4))

        #if we delete b, c should still be able to reference the buffer, (it will keep b around
        #until it itself is released
        del b
        c.clear()
        self.assertEquals('test', c.read_bytes(4))
        del c #this releases buffer b as well, we cannot test this, but this should not crash :-)

    def testGetSetItem(self):
        b = Buffer(1024)
        
        try:
            x = b[-1]
            self.fail()
        except BufferInvalidArgumentError:
            pass
        x = b[0]
        x = b[1023]
        try:            
            x = b[1024]
            self.fail()
        except BufferInvalidArgumentError:
            pass
        try:            
            x = b[1025]
            self.fail()
        except BufferInvalidArgumentError:
            pass
        

        try:
            b[-1] = 1
            self.fail()
        except BufferInvalidArgumentError:
            pass
        b[0] = 1
        b[1023] = 1
        try:            
            b[1024] = 1
            self.fail()
        except BufferInvalidArgumentError:
            pass
        try:            
            b[1025] = 1
            self.fail()
        except BufferInvalidArgumentError:
            pass

        try:
            b[0] = -1
            self.fail()
        except BufferInvalidArgumentError:
            pass

        try:
            b[0] = 256
            self.fail()
        except BufferInvalidArgumentError:
            pass
        
    def testSlice(self):
        b = Buffer(1024)
        for i in range(1024):
            b[i] = i % 256

        self.assertEquals(0, b[0])
        self.assertEquals(255, b[1023])
        self.assertEquals('\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f', b[0:16])
        self.assertEquals('\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff', b[-16:])

        try:
            b[0:16] = '1234567890123456xxx'
            self.fail()
        except BufferInvalidArgumentError:
            pass

        b[0:16] = '1234567890123456'
        b[16:32] = '1234567890123456'
        b[-16:] = '1234567890123456'
        self.assertEquals('1234567890123456', b[0:16])
        self.assertEquals('1234567890123456', b[16:32])
        self.assertEquals('1234567890123456', b[-16:])
    

    def testInt(self):
        b = Buffer(1024)
        b.write_int(0x4A3B2C1D)
        #write_int is little-endian
        self.assertEquals(['0x1d', '0x2c', '0x3b', '0x4a'], [hex(b[i]) for i in range(4)])

    def testString1(self):
        S = 'Henk\0Punt'
        b = Buffer(1024)
        self.assertEqual(0, b.position)
        self.assertEqual(1024, b.limit)                
        b.write_bytes(S)
        self.assertEqual(9, b.position)
        self.assertEqual(1024, b.limit)
        b.flip()                
        self.assertEqual(0, b.position)
        self.assertEqual(9, b.limit)
        
    def testString2(self):
        b = Buffer(1024)
        self.assertEqual(0, b.position)
        self.assertEqual(1024, b.limit)                
        self.assertEqual('\0' * 10, b.read_bytes(10))
        b.clear()
        b.flip()
        #try read string past limit
        try:
            b.read_bytes(10)
            self.fail("expected buffer underflow")
        except BufferUnderflowError:
            pass #expected
     
    def testReadBytesUntil(self):
        b = Buffer(1024)
        b.write_bytes('hello world!')
        b.flip()
        self.assertEquals('hello', b.read_bytes_until(ord(' ')))
        self.assertEquals('world', b.read_bytes_until(ord('!')))

        b = Buffer(1024)
        b.write_bytes('hello world!\nTest\n\nPiet\nKlaas\n')
        b.flip()
        self.assertEquals('hello world!', b.read_bytes_until(10))
        self.assertEquals('Test', b.read_bytes_until(10))
        self.assertEquals('', b.read_bytes_until(10))
        self.assertEquals('Piet', b.read_bytes_until(10))
        self.assertEquals('Klaas', b.read_bytes_until(10))
        try:
            b.read_bytes_until(10)
            self.fail("expected buffer underflow")
        except BufferUnderflowError:
            pass
        

    def testReadLine(self):
        b = Buffer(1024)
        
        b.clear()
        b.write_bytes('hello world!\n')
        b.flip()
        self.assertEquals('hello world!', b.read_line())
        self.assertEquals(b.position, b.limit)

        b.clear()
        b.write_bytes('hello world!\r\n')
        b.flip()
        self.assertEquals('hello world!', b.read_line())
        self.assertEquals(b.position, b.limit)

        b.clear()
        b.write_bytes('hello world!\r')
        b.flip()
        try:
            b.read_line()
            self.fail('expected BufferUnderFlow')
        except BufferUnderflowError:
            pass
        

        b.clear()
        b.write_bytes('hello world!\n')
        b.flip()
        self.assertEquals('hello world!\n', b.read_line(True))
        self.assertEquals(b.position, b.limit)

        b.clear()
        b.write_bytes('hello world!\r\n')
        b.flip()
        self.assertEquals('hello world!\r\n', b.read_line(True))
        self.assertEquals(b.position, b.limit)

        b.clear()
        b.write_bytes('hello world!\r')
        b.flip()
        try:
            b.read_line(True)
            self.fail('expected BufferUnderFlow')
        except BufferUnderflowError:
            pass
        
        b.clear()
        b.write_bytes('line1\nline2\r\nline3\nline4\r\n')
        b.flip()
        self.assertEquals('line1', b.read_line())
        self.assertEquals('line2', b.read_line())
        self.assertEquals('line3', b.read_line())
        self.assertEquals('line4', b.read_line())
        self.assertEquals(b.position, b.limit)
        
        b.clear()
        b.write_bytes('line1\nline2\r\nline3\nline4\r\n')
        b.flip()
        self.assertEquals('line1\n', b.read_line(True))
        self.assertEquals('line2\r\n', b.read_line(True))
        self.assertEquals('line3\n', b.read_line(True))
        self.assertEquals('line4\r\n', b.read_line(True))
        self.assertEquals(b.position, b.limit)
        
    def testBytes(self):
        #test that we can write all bytes into buffer
        #and get them back without any encoding/decoding stuff going on

        #a string with all possible bytes
        B = ''.join([chr(i) for i in range(256)])
        
        b = Buffer(1024)
        b.write_bytes(B)
        b.flip()
        
        self.assertEqual(256, b.limit)
        x = b.read_bytes(256)

        self.assertEquals(B, x)

    def testCopy(self):
        b = Buffer(1024)
        c = Buffer(1024)
        
        try:
            c.copy(b, 0, 0, -1)
            self.fail()
        except BufferInvalidArgumentError:
            pass

        try:
            c.copy(b, 0, 0, 1025)
            self.fail()
        except BufferInvalidArgumentError:
            pass

        try:
            c.copy(b, 1, 0, 1024)
            self.fail()
        except BufferInvalidArgumentError:
            pass

        try:
            c.copy(b, 0, 1, 1024)
            self.fail()
        except BufferInvalidArgumentError:
            pass

        b[0] = 1
        b[10] = 2
        b[1023] = 3
        c.copy(b, 0, 0, 1024)
        self.assertEquals(1, c[0])
        self.assertEquals(2, c[10])
        self.assertEquals(3, c[1023])
        
        c.copy(b, 0, 10, 20)
        self.assertEquals(1, c[10])
        self.assertEquals(2, c[20])
        self.assertEquals(3, c[1023])







if __name__ == '__main__':
    unittest.main(timeout = 10)












