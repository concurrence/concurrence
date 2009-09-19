from __future__ import with_statement

import time

from concurrence import unittest, Tasklet, Channel, TimeoutError
from concurrence.timer import Timeout

class TimerTest(unittest.TestCase):
    def testPushPop(self):
        
        self.assertEquals(-1, Timeout.current())
        
        Timeout.push(30)
        self.assertAlmostEqual(30, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(-1, Timeout.current())
        Timeout.push(30)
        self.assertAlmostEqual(30, Timeout.current(), places = 1)
        Tasklet.sleep(1.0)
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        #push a temporary short timeout
        Timeout.push(5)
        self.assertAlmostEqual(5, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        
        #try to push a new longer timeout than the parent timeout
        #this should fail, e.g. it will keep the parent timeout
        Timeout.push(60)
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(29, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(-1, Timeout.current())
        
    def testPushPop2(self):
        
        self.assertEquals(-1, Timeout.current())
        Timeout.push(-1)
        self.assertEquals(-1, Timeout.current())
        Timeout.pop()
        self.assertEquals(-1, Timeout.current())
        
        Timeout.push(10)
        self.assertAlmostEqual(10, Timeout.current(), places = 1)        
        Timeout.push(5)
        self.assertAlmostEqual(5, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertAlmostEqual(10, Timeout.current(), places = 1)
        Timeout.pop()
        self.assertEquals(-1, Timeout.current())
        
    def testTimer(self):
        
        ch = Channel()
        
        def sender(times):
            for i in range(times):
                Tasklet.sleep(1.0)
                ch.send(True)
       
        with Timeout.push(10):
            Tasklet.new(sender)(4)
            for i in range(4):
                ch.receive(Timeout.current())
            
        start = time.time()
        try:            
            with Timeout.push(2.5):
                Tasklet.new(sender)(4)
                for i in range(4):
                    ch.receive(Timeout.current())
                self.fail('expected timeout')
        except TimeoutError, e:
            end = time.time()
            self.assertAlmostEqual(2.5, end - start, places = 1)
            

if __name__ == '__main__':
    unittest.main(timeout = 10)
