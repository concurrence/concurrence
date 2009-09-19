from __future__ import with_statement

import time

from concurrence import dispatch, unittest, Tasklet, TimeoutError
from concurrence.database.mysql import client
from concurrence.database.pool import Pool, NullPool

DB_HOST = 'localhost'
DB_USER = 'concurrence_test'
DB_PASSWD = 'concurrence_test'
DB_DB = 'concurrence_test'

DB_ARGS = {'host': DB_HOST, 'user': DB_USER, 'passwd': DB_PASSWD, 'db': DB_DB}

class TestPool(unittest.TestCase):
    

    def testConnect(self):

        pool = Pool(client, DB_ARGS, max_connections = 2, connect_timeout = 2)
        
        new, cnn1 = pool.connect()
        self.assertTrue(new)
        self.assertTrue(cnn1)
        self.assertEquals(1, pool.connection_count)
        
        new, cnn2 = pool.connect()
        self.assertTrue(new)
        self.assertTrue(cnn2)
        self.assertEquals(2, pool.connection_count)
        
        #check that pool implements Timeout
        #the pool is now empty, so when we try to connect it should timeout
        start = time.time()
        try:
            new, cnn = pool.connect()
            self.fail('expecting timeout')
        except TimeoutError:
            pass
        end = time.time()
        
        self.assertAlmostEqual(2.0, end - start, places = 1)
        
        self.assertEquals(0, pool.idle_connection_count)
        #return 1 cnn to the pool
        closed = pool.disconnect(cnn1)
        self.assertFalse(closed)
        self.assertEquals(1, pool.idle_connection_count)
        #and the other one
        closed = pool.disconnect(cnn2)
        self.assertFalse(closed)
        self.assertEquals(2, pool.idle_connection_count)
        
        
        #check out again
        new, cnn3 = pool.connect()
        self.assertFalse(new) #should not be new, but one of the idle's
        self.assertTrue(cnn3)
        self.assertEquals(cnn2, cnn3) #should have received the last (pool is a stack)
        self.assertEquals(2, pool.connection_count)
        self.assertEquals(1, pool.idle_connection_count)
        
        closed = pool.disconnect(cnn3, close = True)
        self.assertTrue(closed)
        self.assertEquals(1, pool.connection_count)
        self.assertEquals(1, pool.idle_connection_count)
        
    def xtestIdleDisconnect(self):
        
        pool = Pool(client, DB_ARGS, max_connections = 2, connect_timeout = 2)
        
        def qry():
            new, cnn = pool.connect()
            rs = cnn.query("SELECT 1")
            l = list(rs)
            rs.close()
            self.assertEquals([('1',)], l)
            #return it so it becomes idle
            closed = pool.disconnect(cnn)
            self.assertFalse(closed)
            self.assertEquals(1, pool.idle_connection_count)

        qry()
        
        Tasklet.sleep(20)
        
        qry()

    def testMaxAge(self):
        
        pool = Pool(client, DB_ARGS, max_connections = 2, connect_timeout = 2, max_connection_age = 2, 
                    max_connection_age_reaper_interval = 1)
        
        new, cnn1 = pool.connect()
        new, cnn2 = pool.connect()
        
        pool.disconnect(cnn1)
        
        self.assertTrue(cnn1.is_connected())
        self.assertTrue(cnn2.is_connected())
        
        Tasklet.sleep(3)
        
        #cnn1 was idle, should be disconnected now by old age reaper
        self.assertFalse(cnn1.is_connected())
        self.assertTrue(cnn2.is_connected())
        
        pool.disconnect(cnn2)
        #cnn2 should be closed on old age

        self.assertFalse(cnn1.is_connected())
        self.assertFalse(cnn2.is_connected())
        
    def testNullPool(self):
        
        pool = NullPool(client, DB_ARGS)
        
        new1, cnn1 = pool.connect()
        new2, cnn2 = pool.connect()
        
        self.assertTrue(new1)
        self.assertTrue(new2)
        
        self.assertTrue(cnn1.is_connected())
        self.assertTrue(cnn2.is_connected())
        
        pool.disconnect(cnn1, True)
        pool.disconnect(cnn2, False)

        #null pool always disconnects
        self.assertFalse(cnn1.is_connected())
        self.assertFalse(cnn2.is_connected())
        
        
if __name__ == '__main__':
    unittest.main(timeout = 60)        
        
         
        
