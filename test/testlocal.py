from __future__ import with_statement

import logging
import time

from concurrence import unittest, Tasklet, TaskLocal, TaskInstance

class TestTaskLocal(unittest.TestCase):
    """test tasklet local storage"""
    def testSingleTask(self):
        
        local = TaskLocal()

        local.piet = 10
        
        self.assertEquals(10, local.piet)
        
        try:        
            x = local.klaas
            self.fail('expected attribute error')
        except AttributeError:
            pass
        
        local.piet = 20
        
        self.assertEquals(True, hasattr(local, 'piet'))
        self.assertEquals(False, hasattr(local, 'klaas'))
        self.assertEquals(20, local.piet)
        
        del local.piet
        
        self.assertEquals(False, hasattr(local, 'piet'))
        
        try:        
            x = local.piet
            self.fail('expected attribute error')
        except AttributeError:
            pass
 
    def testMultiTask(self):
 
        local = TaskLocal()
        
        def t():
            local.piet = []
            for i in range(10):
                local.piet.append(i)
                Tasklet.yield_()
            self.assertEquals(range(10), local.piet)

        t1 = Tasklet.new(t)()
        t2 = Tasklet.new(t)()
        
        Tasklet.join_all([t1,t2])
        
        self.assertEquals(2, len(local._d.keys())) #the 2 tasks are sill around, so local keeps their values
        
        #check that values are gone from dict
        #when tasks are gone
        del t1
        del t2
        #we need to yield, because our 2 tasks were suspended by the join
        #yield will run the scheduler again, so our tasks can properly finish

        #the only strange thing is we need 2 yields for python, stackless requires just 1
        Tasklet.yield_()
        Tasklet.yield_()

        self.assertEquals([], local._d.keys())
            
    def testRecursive(self):
        
        #non-recursive
        local = TaskLocal()
        
        local.piet = 20
        
        def t():
            try:
                local.piet
                self.fail('expected attr error')
            except AttributeError:
                pass
        
        Tasklet.join(Tasklet.new(t)())
        
        #recursive
        local = TaskLocal(True)
        
        local.piet = 30
        
        def t():
            self.assertEquals(30, local.piet)
        
        Tasklet.join(Tasklet.new(t)())
        

class Adder(object):
    def __init__(self, x):
        self.x = x
        
    def sum(self, y):
        return self.x + y 
    
class TestTaskInstance(unittest.TestCase):

    def testTaskInstance(self):
        
        AdderInstance = TaskInstance(True)

        try:
            AdderInstance.sum(10)
            self.fail('expected attribute error')
        except AttributeError:
            pass
        
        def t():
            return AdderInstance.sum(20)
            
        with AdderInstance.set(Adder(10)):
            self.assertEquals(30, AdderInstance.sum(20))
            #check that child task can also find it
            self.assertEquals(30, Tasklet.join(Tasklet.new(t)()))

        #should have been unset
        try:
            AdderInstance.sum(10)
            self.fail('expected attribute error')
        except AttributeError:
            pass

    def testTaskInstance2(self):

        AdderInstance = TaskInstance(True)
        
        with AdderInstance.set(Adder(10)):
            
            self.assertEquals(30, AdderInstance.sum(20))
            
            #now start 2 child tasks
            def t():
                self.assertEquals(30, AdderInstance.sum(20)) #expect to find parents instance
                #now set my own instance
                with AdderInstance.set(Adder(20)):
                    self.assertEquals(40, AdderInstance.sum(20))
                #now it must be unset, and we will find parents instance instead
                self.assertEquals(30, AdderInstance.sum(20))
                
            t1 = Tasklet.new(t)()
            t2 = Tasklet.new(t)()
            Tasklet.join_all([t1, t2])
            
            self.assertEquals(30, AdderInstance.sum(20))
        
if __name__ == '__main__':
    unittest.main()        
