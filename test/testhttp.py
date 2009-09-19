
import logging
import time

from concurrence import Tasklet, TimeoutError, unittest
from concurrence.http import HTTPError, WSGIServer, HTTPConnection
from concurrence.wsgi import WSGISimpleRouter, WSGISimpleMessage
from concurrence.io import Buffer, Socket

SERVER_PORT = 8080

class TestHTTP(unittest.TestCase):
    def setUp(self):
        application = WSGISimpleRouter()
        for i in range(10):
            application.map('/hello/%d' % i, WSGISimpleMessage("Hello World %d" % i))

        class WSGISleeper(WSGISimpleMessage):
            def __call__(self, environ, start_response):
                sleep_seconds = int(environ['QUERY_STRING'])
                Tasklet.sleep(sleep_seconds)
                self.response = 'slept %d' % sleep_seconds
                return WSGISimpleMessage.__call__(self, environ, start_response)

        class WSGIPOSTSaver(WSGISimpleMessage):
            def __call__(self, environ, start_response):
                self.environ = environ
                f = environ['wsgi.input']
                self.body = f.read(int(environ['HTTP_CONTENT_LENGTH']))
                return WSGISimpleMessage.__call__(self, environ, start_response)                
            
        self.saver = WSGIPOSTSaver('ok')
        application.map('/sleep', WSGISleeper('zzz...'))
        application.map('/post', self.saver)

        self.server = WSGIServer(application)
        self.socket_server = self.server.serve(('0.0.0.0', SERVER_PORT))

    def tearDown(self):
        self.socket_server.close()
        self.server = None

    def testSimple(self):
        cnn = HTTPConnection()
        cnn.connect(('localhost', SERVER_PORT))

        request = cnn.get('/hello/1')
        response = cnn.perform(request)
        self.assertEquals(200, response.status_code)
        chunks = list(response.iter)
        self.assertEquals('Hello World 1', chunks[0])

        request = cnn.get('/hello/2')
        response = cnn.perform(request)
        self.assertEquals(200, response.status_code)
        body = response.body
        self.assertEquals('Hello World 2', body)

        request = cnn.get('/xxx')
        response = cnn.perform(request)
        self.assertEquals(404, response.status_code)
        chunks = list(response)
        self.assertEquals('Not Found', chunks[0])

        cnn.close()            

    def testInterleaved1(self):
        cnn = HTTPConnection()
        cnn.connect(('localhost', SERVER_PORT))

        cnn.send(cnn.get('/hello/1'))
        cnn.send(cnn.get('/hello/2'))

        response = cnn.receive()
        self.assertEquals(200, response.status_code)
        chunks = list(response)
        self.assertEquals('Hello World 1', chunks[0])

        response = cnn.receive()
        self.assertEquals(200, response.status_code)
        chunks = list(response)
        self.assertEquals('Hello World 2', chunks[0])

        cnn.close()            

    def testInterleaved3(self):
        """tests that http client and server really support pipelining"""
        cnn = HTTPConnection()
        cnn.connect(('localhost', SERVER_PORT))

        #we do 2 requests that should take 2 seconds to complete each.
        #if server/client pipelining was not working, fetching the 2 urls
        #would take 4 seconds on a single connection
        #if pipelining works, it should take just 2 seconds

        start = time.time()

        cnn.send(cnn.get('/sleep?2'))
        cnn.send(cnn.get('/sleep?2'))

        list(cnn.receive())
        list(cnn.receive())

        end = time.time()

        self.assertAlmostEqual(2, end - start, places = 1)
        
        cnn.close()

    def testInterleaved4(self):
        """tests that http server returns responses in correct order"""
        cnn = HTTPConnection()
        cnn.connect(('localhost', SERVER_PORT))

        #we do 2 requests that should take 2 seconds to complete each.
        #if server/client pipelining was not working, fetching the 2 urls
        #would take 4 seconds on a single connection
        #if pipelining works, it should take just 2 seconds

        start = time.time()

        cnn.send(cnn.get('/sleep?3'))
        cnn.send(cnn.get('/sleep?1'))
        response1 = cnn.receive()
        response2 = cnn.receive()

        #we expect response1 to be returned first, because it was made first
        #eventhough it takes longer 
        self.assertEquals('slept 3', response1.body)
        self.assertEquals('slept 1', response2.body)       

        end = time.time()

        self.assertAlmostEqual(3, end - start, places = 1)
        
        cnn.close()

    def fetch10(self, s, uri):

        b = Buffer(1024)
        b.clear()
        b.write_bytes("GET %s HTTP/1.0\r\n" % uri)
        b.write_bytes("\r\n")
        b.flip()
        s.write(b)
        
        b.clear()
        s.read(b)
        b.flip()
        return b.read_bytes(b.remaining)

    def testHTTP10(self):
        s = Socket.connect(('localhost', SERVER_PORT))
        r1 = self.fetch10(s, '/hello/1')
        r2 = self.fetch10(s, '/hello/2')
        self.assertEquals('', r2)

    def testHTTPReadTimeout(self):
        self.server.read_timeout = 2
    
        cnn = HTTPConnection()

        try:
            cnn.connect(('localhost', SERVER_PORT))

            Tasklet.sleep(1)

            response = cnn.perform(cnn.get('/hello/1'))
            
            self.assertEquals('HTTP/1.1 200 OK', response.status)
            self.assertEquals('Hello World 1', response.body)

            Tasklet.sleep(3)

            try:        
                list(cnn.perform(cnn.get('/hello/2')))
                self.fail('expected eof')
            except HTTPError, e:
            	pass
	    except:
                self.fail('expected http errror')       
        finally:
            cnn.close()

    def testHTTPPost(self):
        cnn = HTTPConnection()

        try:
            cnn.connect(('localhost', SERVER_PORT))
            for i in [1, 2, 4, 8, 16, 32, 100, 1000, 10000, 100000, 200000]:
                post_data = 'test post data' * i
                request = cnn.post('/post', post_data, host = 'testhost.nl')
                response = cnn.perform(request)
                self.assertEquals('ok', response.body)
                self.assertTrue('HTTP_CONTENT_LENGTH' in self.saver.environ)
                self.assertEquals(len(post_data), int(self.saver.environ['HTTP_CONTENT_LENGTH']))
                self.assertEquals(post_data, self.saver.body)
                self.assertEquals('testhost.nl', self.saver.environ['HTTP_HOST'])
        finally:
            cnn.close()        
        
if __name__ == '__main__':
    unittest.main(timeout = 100.0)

