import os

from concurrence import unittest, Tasklet
from concurrence.memcache.client import MemcacheNode, MemcacheError

class MemcacheTest(unittest.TestCase):
    def testNodeBasic(self):
        
        node = MemcacheNode()
        node.connect(('127.0.0.1', 11211))

        node.set('test1', '12345')
        node.set('test2', '67890')

        self.assertEquals('12345', node.get('test1'))
        self.assertEquals(None, node.get('test3'))
        self.assertEquals({'test1': '12345', 'test2': '67890'}, node.get(['test1', 'test2', 'test3']))

        #update test2
        node.set('test2', 'hello world!')

        self.assertEquals({'test1': '12345', 'test2': 'hello world!'}, node.get(['test1', 'test2', 'test3']))
       
        #update to unicode type
        node.set('test2', u'C\xe9line')
        self.assertEquals(u'C\xe9line', node.get('test2'))

        #update to some other type
        node.set('test2', {'piet': 'blaat', 10: 20})
        self.assertEquals({'piet': 'blaat', 10: 20}, node.get('test2'))

        node.close()
        
if __name__ == '__main__':
    unittest.main(timeout = 60)
