# -*- coding: utf-8 -*-

from concurrence import unittest, Tasklet, TimeoutError

from concurrence.web import Application, Controller, Filter, web
from concurrence.web.filter import TimeoutFilter, JSONFilter
from concurrence.http.client import HTTPConnection

class CallManyFilter(Filter):
    def __init__(self, n):
        self.n = n
        
    def __call__(self, next, *args, **kwargs):
        result = ''
        for i in range(self.n):
            result += next(*args, **kwargs)
        return result
    
class TestController(Controller):

    @web.route('/hello')
    def hello(self):
        return u"Héllo World!"

    @web.route('/many')
    @web.filter(CallManyFilter(10))
    def many(self):
        return "blaat"
        
    @web.route('/timeout')
    @web.filter(TimeoutFilter())
    def timeout(self):
        Tasklet.sleep(2.0)
        raise TimeoutError() #simulate it because sleep does not honor timeouts
        
    @web.route('/json')
    @web.filter(JSONFilter())
    def json(self):
        return "[1,2,3,4]"            
        
class TestWeb(unittest.TestCase):

    def setUp(self):

        application = Application()
        application.add_controller(TestController())
        application.configure()
        self.server = application.serve(('localhost', 8080))

    def tearDown(self):

        self.server.close()

    def testWeb(self):

        cnn = None
        try:           
            cnn = HTTPConnection()
            cnn.connect(('localhost', 8080))
            response = cnn.perform(cnn.get('/hello'))
            status = response.status
            self.assertEquals('HTTP/1.1 200 OK', status)    
            self.assertEquals('text/html; charset=UTF-8', response.get_header('Content-Type'))
            self.assertEquals('13', response.get_header('Content-Length'))
            self.assertEquals(u"Héllo World!",  ''.join(response).decode('UTF-8'))
        finally:
            if cnn: cnn.close()

    def testWebTimeout(self):

        cnn = None
        try:           
            cnn = HTTPConnection()
            cnn.connect(('localhost', 8080))

            request = cnn.get('/timeout')
            request.add_header('Timeout', 1.0)
            response = cnn.perform(request)
            status = response.status            
            self.assertEquals('HTTP/1.1 500 Internal Server Error', status)    
            self.assertEquals('text/plain', response.get_header('Content-Type'))
            
        finally:
            if cnn: cnn.close()
        
    def testWebJSON(self):

        cnn = None
        try:           
            cnn = HTTPConnection()
            cnn.connect(('localhost', 8080))
            response = cnn.perform(cnn.get('/json'))
            status = response.status
            self.assertEquals('HTTP/1.1 200 OK', status)    
            self.assertEquals('application/json; charset=UTF-8', response.get_header('Content-Type'))
            self.assertEquals('9', response.get_header('Content-Length'))
            self.assertEquals("[1,2,3,4]",  response.body)
        finally:
            if cnn: cnn.close()
        
    def testMany(self):
        cnn = None
        try:           
            cnn = HTTPConnection()
            cnn.connect(('localhost', 8080))
            response = cnn.perform(cnn.get('/many'))
            self.assertEquals('blaat' * 10, response.body)
        finally:
            if cnn: cnn.close()
        
if __name__ == '__main__':
    unittest.main(timeout = 100)
