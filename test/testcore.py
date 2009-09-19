
import logging
import time
import sys

from concurrence import unittest, Tasklet, Channel, TimeoutError, TaskletError, JoinError, Message

class TestTasklet(unittest.TestCase):
    def testSleep(self):
        start = time.time()
        Tasklet.sleep(1.0)
        end = time.time()
        
        self.assertAlmostEqual(1.0, end - start, places = 1)
        
    def testJoinResult(self):
        """test normal join and checks that parent will get child result"""
        def child(i):
            return i

        ch1 = Tasklet.new(child)(1)
        ch2 = Tasklet.new(child)(2)  

        self.assertEquals(1, Tasklet.join(ch1))
        self.assertEquals(2, Tasklet.join(ch2))

    def testJoinKill(self):
        """tests that we can join a tasklet that gets killed"""
        def child(i):   
            Tasklet.sleep(1000)
        
        def killer(t):
            t.kill()

        ch1 = Tasklet.new(child)(1)
        ch2 = Tasklet.later(1, killer)(ch1)  

        try:
            Tasklet.join(ch1)
            self.fail('expected join error')
        except JoinError, e:
            self.assertEquals(ch1, e.tasklet) 
            self.assertTrue(isinstance(e.cause, TaskletExit))
        

    def testJoinAfterExit(self):
        def child(i):
            return i
 
        ch1 = Tasklet.new(child)(1)
        ch2 = Tasklet.new(child)(2)  

        Tasklet.yield_() #make sure children are run

        self.assertEquals(1, Tasklet.join(ch1))
        self.assertEquals(2, Tasklet.join(ch2))

    def testJoinTimeout(self):
        """test join where child does not exit within timeout"""
        def child():
            Tasklet.sleep(10.0)

        ch = Tasklet.new(child)()

        try:
            Tasklet.join(ch, 1.0)
            self.fail('expected timeout error')
        except TimeoutError:
            pass #ok
        except:
            self.fail('expected timeout error')
        finally:
            ch.kill()
            
    def testJoinException(self):
        """test join where child raised exception, checks that parent receives exception"""

        def sub2():
            raise Exception("test_exc")

        def sub1():
            sub2()

        def child():
            sub1()

        ch = Tasklet.new(child)()
        try:
            Tasklet.join(ch)
            self.fail('expected join error')
        except JoinError, e:
            self.assertEquals(ch, e.tasklet)
            self.assertTrue(isinstance(e.cause, Exception))
            self.assertEqual('test_exc', str(e.cause))
        except:
            self.fail('expected tasklet error')
        
    def testJoinAll(self):
        
        def sub0():
            raise Exception("a proper exc")
        
        def sub1():
            return 1
        
        def sub2():
            return 2
        
        def sub3():
            raise Exception("test exc")
        
        subs = [Tasklet.new(sub)() for sub in [sub0, sub1, sub2, sub3]]
        results = Tasklet.join_all(subs)
        
        self.assertTrue(isinstance(results[0], JoinError))
        self.assertTrue(isinstance(results[0].cause, Exception))
        self.assertEquals("a proper exc", str(results[0].cause), Exception)
        self.assertEquals(1, results[1])
        self.assertEquals(2, results[2])

        self.assertTrue(isinstance(results[3], JoinError))
        self.assertTrue(isinstance(results[3].cause, Exception))
        self.assertEquals("test exc", str(results[3].cause), Exception)

        
    def testJoinChildren(self):
        
        def t():
            return 1
        
        for i in range(4):
            Tasklet.new(t)()
        
        self.assertEquals(4, len(Tasklet.current().children()))
            
        result = Tasklet.join_children()
        
        self.assertEquals([1,1,1,1], result)
        
    def testTree(self):
        
        def child(prefix, level, i):
            if level < 2:
                for j in range(2):
                    name = prefix + str(j)
                    Tasklet.new(child, name = name)(name, level + 1, j)  
            Tasklet.sleep(2)

        Tasklet.new(child, 'child')('child', 0, 0)

        Tasklet.sleep(1)

        #for task, level in Tasklet.current().tree():
        #    print '\t' * level, task.name, level
            
        flattened = set([(task.name, level) for (task, level) in Tasklet.current().tree()][1:])
        
        self.assertEquals(set([('child', 1), ('child0', 2), ('child00', 3), ('child01', 3), 
                           ('child1', 2), ('child10', 3), ('child11', 3)]), flattened)

    def testInterval(self):
        
        count = []
        def ival():
            count.append(1) 
        
        #test non immediate    
        ival_task = Tasklet.interval(1.0, ival, False)()
            
        try:
            Tasklet.join(ival_task, 3.0)
        except TimeoutError:
            #expect 2 counts, because interval started after 1 second
            self.assertEquals(2, len(count))
        except:
            self.fail('expected timeout, got %s' % sys.exc_type)
        finally:
            ival_task.kill()
            
        #test immediate
        count = []
        ival_task = Tasklet.interval(1.0, ival, True)()
            
        try:
            Tasklet.join(ival_task, 3.0)
        except TimeoutError:
            #expect 3 counts, because interval started immediately
            self.assertEquals(3, len(count))
        except:
            self.fail('expected timeout')
        finally:
            ival_task.kill()
        
    def testLoop(self):
        recvd = []
        def looper(channel):
            res = channel.receive()
            if res == None:
                raise Exception("some exception")
            else:
                recvd.append(res)
            
        looper_channel = Channel()
        looper_task = Tasklet.loop(looper)(looper_channel)

        for i in range(10):
            looper_channel.send(i)
        self.assertEqual(range(10), recvd)

        self.assertEqual(-1, looper_channel.balance)

        self.assertTrue(looper_task.alive)
        
        looper_channel.send(None) #will trigger exception loop
        
        #must still be working
        recvd = []
        for i in range(10):
            looper_channel.send(i)
        self.assertEqual(range(10), recvd)

        self.assertEqual(-1, looper_channel.balance)
        
        looper_task.kill()

        self.assertEqual(0, looper_channel.balance)
        
        #assert that looper exitted, because it is not receiving anymore
        self.assertFalse(looper_channel.has_receiver())

        self.assertFalse(looper_task.alive)

    def testYield(self):
        
        l = []

        def child(c):
            for i in range(5):
                l.append((c, i))
                Tasklet.yield_()

        ch1 = Tasklet.new(child)(1)
        ch2 = Tasklet.new(child)(2)

        Tasklet.join_all([ch1, ch2])

        self.assertEquals([(1, 0), (2, 0), (1, 1), (2, 1), (1, 2), (2, 2), (1, 3), (2, 3), (1, 4), (2, 4)], l)

    def testMessageSend(self):
        
        class MSG_PONG(Message): pass
        class MSG_PING(Message): pass

        def c(parent):
            for msg, args, kwargs in Tasklet.receive():     
                if msg.match(MSG_PING):
                    self.assertEquals((10, ), args)
                    MSG_PONG.send(parent)(20)

        parent = Tasklet.current()
        child = Tasklet.new(c)(parent)
        i = 0
        MSG_PING.send(child)(10)
        for msg, args, kwargs in Tasklet.receive():
            if msg.match(MSG_PONG):
                self.assertEquals((20, ), args)
                i += 1
                if i > 5: break
                MSG_PING.send(child)(10)

        self.assertEquals(6, i)

        try:
            start = time.time()
            for msg, args, kwargs in Tasklet.receive(2.0):
                self.fail('expected timeout error')            
        except TimeoutError:
            end = time.time()
            self.assertAlmostEqual(2.0, end - start, places = 1)

        child.kill()
        
        
    def testMessageCall(self):
        
        class MSG_TEST_SUM(Message): pass
        class MSG_TEST_MAX(Message): pass
        class MSG_TEST_SLEEP(Message): pass

        
        def c():
            for msg, args, kwargs in Tasklet.receive():
                if msg.match(MSG_TEST_SUM):
                    msg.reply(sum(args))
                elif msg.match(MSG_TEST_MAX):
                    msg.reply(max(args))
                elif msg.match(MSG_TEST_SLEEP):     
                    Tasklet.sleep(args[0])
                    msg.reply(True)
                
        child = Tasklet.new(c)()
        
        self.assertEquals(60, MSG_TEST_SUM.call(child)(10, 20, 30))
        self.assertEquals(30, MSG_TEST_MAX.call(child)(10, 20, 30))
        
        self.assertEquals(True, MSG_TEST_SLEEP.call(child)(1))

        try:
            MSG_TEST_SLEEP.call(child, timeout = 1)(2)
            self.fail("expected timeout")
        except TimeoutError:
            pass #expected
        child.kill()
        
class TestChannel(unittest.TestCase):
    
    def testSendRecv(self):
        """test simple send and receive on a channel"""
        def sender(channel):
            for i in range(3):
                channel.send(i)
        
        def receiver(channel):
            while True:
                recvd.append(channel.receive())
        
        recvd = []
                
        test_channel = Channel()
        
        send_task = Tasklet.new(sender)(test_channel)
        recv_task = Tasklet.new(receiver)(test_channel)

        Tasklet.join(send_task)
        
        self.assertEquals([0,1,2], recvd)
        
        recv_task.kill()
        
    def testRecvTimeout(self):
        
        #receive within timeout
        test_channel = Channel()
        t1 = Tasklet.later(1.0, test_channel.send)(10)
        try:            
            self.assertEqual(10, test_channel.receive(2.0))
        except TimeoutError:
            self.fail('did not expect timeout')
        finally:
            t1.kill()
        
        #receive with timeout
        test_channel = Channel()
        t1 = Tasklet.later(2.0, test_channel.send)(10)
        try:            
            self.assertEqual(10, test_channel.receive(1.0))
            self.fail('expected timeout')
        except TimeoutError:
            pass #expected
        finally:
            t1.kill()
            
    def testSendTimeout(self):
        #send within timeout

        test_channel = Channel()
        tl = Tasklet.later(1.0, test_channel.receive)()
        try:            
            test_channel.send(10, 2.0)
        except TimeoutError:
            self.fail('did not expect timeout')
        finally:
            tl.kill()
        
        #send with timeout
        test_channel = Channel()
        tl = Tasklet.later(2.0, test_channel.receive)()
        try:            
            test_channel.send(10, 1.0)
            self.fail('expected timeout')
        except TimeoutError:
            pass #expected
        finally:
            tl.kill()
            
        
    def testHasReceiver(self):
        
        test_channel = Channel()
        
        def receiver():
            test_channel.receive()
        
        self.assertEquals(False, test_channel.has_receiver())
        
        r = Tasklet.new(receiver)()
        
        Tasklet.sleep(1.0)
        
        self.assertEquals(True, test_channel.has_receiver())
        
        r.kill()
        
        Tasklet.sleep(1.0)
        
        self.assertEquals(False, test_channel.has_receiver())
        
if __name__ == '__main__':
    unittest.main(timeout = 100.0)
