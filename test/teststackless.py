
import unittest
import logging

logging.basicConfig(level = logging.DEBUG)

from concurrence.core import stackless

class TestError(Exception): pass

class TestStackless(unittest.TestCase):
    
    def setUp(self):
        logging.debug(self)
        
    def testSchedule(self):

        res1 = []
        res2 = []
        
        def ch1():
            for i in range(10):
                res1.append((i, stackless.getruncount()))
                stackless.schedule()

        def ch2():
            for i in range(10):
                res2.append((i, stackless.getruncount()))
                stackless.schedule()

        child1 = stackless.tasklet(ch1)()
        child2 = stackless.tasklet(ch2)()

        self.assertEquals(3, stackless.getruncount()) #main + ch1, ch2

        while stackless.getruncount() > 1:
            stackless.schedule()

        self.assertEquals([(0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3)], res1)
        self.assertEquals([(0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3)], res2)

        self.assertEquals(1, stackless.getruncount()) #main
        
    def testChannel(self):
        
        c = stackless.channel()
        
        recvd = []
        
        def ch1():
            for i in range(10):
                recvd.append(c.receive())

        def ch2():
            for i in range(10):
                c.send(i)

        child1 = stackless.tasklet(ch1)()
        child2 = stackless.tasklet(ch2)()

        self.assertEquals(3, stackless.getruncount()) #main
        
        while stackless.getruncount() > 1:
            stackless.schedule()

        self.assertEquals(range(10), recvd)
        
        self.assertEquals(1, stackless.getruncount()) #main
        
    def testChannelException(self):


        c = stackless.channel()

        result = []

        def ch1():
            for i in range(2):
                try:
                    result.append(c.receive())
                except TestError, te:
                    result.append(te)
             
        def ch2():
            c.send(True)
            c.send_exception(TestError, "test")

        child1 = stackless.tasklet(ch1)()
        child2 = stackless.tasklet(ch2)()

        self.assertEquals(3, stackless.getruncount()) #main + ch1 + ch2
        
        while stackless.getruncount() > 1:
            stackless.schedule()

        self.assertEquals(True, result[0])
        self.assertTrue(isinstance(result[1], TestError))
        
        self.assertEquals(1, stackless.getruncount()) #main

    def testKillOnChannel(self):
        
        c = stackless.channel()
        
        def child(r):
            r.b1 = c.balance
            r.rc1 = stackless.getruncount()
            r.cur1 = stackless.getcurrent()
            r.blocked1 = r.cur1.blocked
            r.alive1 = r.cur1.alive
            try:
                c.receive()
            finally:
                r.b2 = c.balance
                r.rc2 = stackless.getruncount()
                r.cur2 = stackless.getcurrent()
                r.blocked2 = r.cur2.blocked
                r.alive2 = r.cur2.alive

        class result: pass

        r = result()
        ch = stackless.tasklet(child)(r)
        
        stackless.schedule()

        ch.kill()

        self.assertEquals((0, 0), (r.b1, r.b2))
        self.assertEquals((2, 2), (r.rc1, r.rc2))
        self.assertTrue(r.cur1 == r.cur2)
        self.assertEquals((False, False), (r.blocked1, r.blocked2))
        self.assertEquals((True, True), (r.alive1, r.alive2))

    def testExceptionOnChannel(self):
        
        c = stackless.channel()
        
        def child(r):
            r.b1 = c.balance
            try:
                c.receive()
            except TestError:
                r.b2 = c.balance

        class result: pass

        r = result()
        ch = stackless.tasklet(child)(r)
        
        stackless.schedule()

        ch.raise_exception(TestError)
        
        self.assertEquals((0, 0), (r.b1, r.b2))

    def testKillOnSchedule(self):

        class result: pass

        r = result()

        def child1():
            i = 0
            while True:
                i += 1
                #print 'c', i
                r.rc1 = stackless.getruncount()
                r.cur1 = stackless.getcurrent()
                r.blocked1 = r.cur1.blocked
                r.alive1 = r.cur1.alive

                try:
                    stackless.schedule()    
                except TaskletExit:
                    #print 'kill'
                    r.rc2 = stackless.getruncount()
                    r.cur2 = stackless.getcurrent()
                    r.blocked2 = r.cur2.blocked
                    r.alive2 = r.cur2.alive
                    raise

        ch1 = stackless.tasklet(child1)()

        x = 0
        while True:
            x += 1
            stackless.schedule()    
            if x == 10: 
                ch1.kill()
            if x >= 15:
                break

        self.assertEquals((2, 2), (r.rc1, r.rc2))
        self.assertTrue(r.cur1 == r.cur2)
        self.assertEquals((False, False), (r.blocked1, r.blocked2))
        self.assertEquals((True, True), (r.alive1, r.alive2))

    def testKillOrder(self):
        
        def ch1():
            #print 'ch1 start', stackless.getcurrent()
            try:
                for i in range(10):
                    #print 1, i
                    stackless.schedule()
            except:
                #print '1', 'some exc in 1', stackless.getruncount()
                #print '1', stackless.getcurrent(), stackless.getcurrent().alive
                raise

        def ch2():
            for i in range(10):
                #print 2, i
                stackless.schedule()
                if i == 5:
                    #print '2', '!!!!!!!!KILL!!!!'
                    child1.kill()
                    #print '2', stackless.getcurrent(), stackless.getruncount()
            #print '2', 'DONE'
        child1 = stackless.tasklet(ch1)()
        child2 = stackless.tasklet(ch2)()

        for i in range(20):
            #print 's', i, stackless.getruncount(), child1.alive, child2.alive#, stackless._scheduler._runnable
            stackless.schedule()
        #while stackless.getruncount() > 2:
        #    stackless.schedule()

if __name__ == '__main__':
    unittest.main()
