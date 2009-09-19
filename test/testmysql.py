# -*- coding: latin1 -*-
from __future__ import with_statement

import time

from concurrence import dispatch, unittest, Tasklet
from concurrence.database.mysql import client, dbapi, PacketReadError

DB_HOST = 'localhost'
DB_USER = 'concurrence_test'
DB_PASSWD = 'concurrence_test'
DB_DB = 'concurrence_test'

class TestMySQL(unittest.TestCase):
    
    def testMySQLClient(self):
        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)
        
        rs = cnn.query("select 1")
        
        self.assertEqual([('1',)], list(rs))
        
        rs.close()
        cnn.close()

    def testFetchUnicode(self):
        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)
        
        cnn.query("truncate tbltest")

        for i in range(10):
            self.assertEquals((1, 0), cnn.query("insert into tbltest (test_id, test_string) values (%d, 'test%d')" % (i, i)))

        rs = cnn.query("select test_string from tbltest where test_id = 1")
        s = list(rs)[0][0]
        self.assertTrue(type(s) == str)
        rs.close()
        
        cnn.set_charset('latin1')
        rs = cnn.query("select test_string from tbltest where test_id = 1")
        s = list(rs)[0][0]
        self.assertTrue(type(s) == unicode)        
        rs.close()
        
        cnn.close()
        
        
    def testMySQLClient2(self):
        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)

        cnn.query("truncate tbltest")

        for i in range(10):
            self.assertEquals((1, 0), cnn.query("insert into tbltest (test_id, test_string) values (%d, 'test%d')" % (i, i)))

        rs = cnn.query("select test_id, test_string from tbltest")
        
        #trying to close it now would give an error, e.g. we always need to read
        #the result from the database otherwise connection would be in wrong stat
        try:
            rs.close()
            self.fail('expected exception')
        except client.ClientProgrammingError:
            pass
            
        for i, row in enumerate(rs):
            self.assertEquals((i, 'test%d' % i), row)

        rs.close()
        cnn.close()
        
    def testMySQLTimeout(self):
        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)

        rs = cnn.query("select sleep(2)")
        list(rs)
        rs.close()
        
        from concurrence import TimeoutError
        from concurrence.timer import Timeout

        start = time.time()
        try:
            with Timeout.push(2.0):
                cnn.query("select sleep(4)")
                self.fail('expected timeout')
        except TimeoutError, e:
            end = time.time()
            self.assertAlmostEqual(2.0, end - start, places = 1)
        
        cnn.close()

    def testParallelQuery(self):

        def query(s):
            cnn = dbapi.connect(host = DB_HOST, user = DB_USER, 
                                passwd = DB_PASSWD, db = DB_DB)
            cur = cnn.cursor()
            cur.execute("select sleep(%d)" % s)
            cur.close()
            cnn.close()

        start = time.time()
        ch1 = Tasklet.new(query)(1)
        ch2 = Tasklet.new(query)(2)
        ch3 = Tasklet.new(query)(3)
        Tasklet.join_all([ch1, ch2, ch3])

        end = time.time()
        self.assertAlmostEqual(3.0, end - start, places = 1)

    def testMySQLDBAPI(self):
        
        cnn = dbapi.connect(host = DB_HOST, user = DB_USER, 
                            passwd = DB_PASSWD, db = DB_DB)
        
        cur = cnn.cursor()
        
        cur.execute("truncate tbltest")

        for i in range(10):
            cur.execute("insert into tbltest (test_id, test_string) values (%d, 'test%d')" % (i, i))

        cur.close()
        
        cur = cnn.cursor()
        
        cur.execute("select test_id, test_string from tbltest")
        
        self.assertEquals((0, 'test0'), cur.fetchone())
        
        #check that fetchall gets the remainder
        self.assertEquals([(1, 'test1'), (2, 'test2'), (3, 'test3'), (4, 'test4'), (5, 'test5'), (6, 'test6'), (7, 'test7'), (8, 'test8'), (9, 'test9')], cur.fetchall())

        #another query on the same cursor should work
        cur.execute("select test_id, test_string from tbltest")
        
        #fetch some but not all
        self.assertEquals((0, 'test0'), cur.fetchone())
        self.assertEquals((1, 'test1'), cur.fetchone())
        self.assertEquals((2, 'test2'), cur.fetchone())

        #close whould work even with half read resultset
        cur.close()

        #this should not work, cursor was closed
        try:
            cur.execute("select * from tbltest")
            self.fail("expected exception")
        except dbapi.ProgrammingError:
            pass

    def testLargePackets(self):
        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)
        
        
        cnn.query("truncate tbltest")
        
        c = cnn.buffer.capacity
        
        blob = '0123456789'
        while 1:
            cnn.query("insert into tbltest (test_id, test_blob) values (%d, '%s')" % (len(blob), blob))
            if len(blob) > (c * 2): break
            blob = blob * 2
            
        rs = cnn.query("select test_id, test_blob from tbltest")
        for row in rs:
            self.assertEquals(row[0], len(row[1]))
            self.assertEquals(blob[:row[0]], row[1])
        rs.close()

        #reread, second time, oversize packet is already present
        rs = cnn.query("select test_id, test_blob from tbltest")
        for row in rs:
            self.assertEquals(row[0], len(row[1]))
            self.assertEquals(blob[:row[0]], row[1])
        rs.close()
        cnn.close()

        #have a very low max packet size for oversize packets
        #and check that exception is thrown when trying to read larger packets
        from concurrence.database.mysql import _mysql
        _mysql.MAX_PACKET_SIZE = 1024 * 4

        cnn = client.connect(host = DB_HOST, user = DB_USER, 
                             passwd = DB_PASSWD, db = DB_DB)

        try:
            rs = cnn.query("select test_id, test_blob from tbltest")
            for row in rs:
                self.assertEquals(row[0], len(row[1]))
                self.assertEquals(blob[:row[0]], row[1])
            self.fail()
        except PacketReadError: 
            pass
        finally:
            try:
                rs.close()
            except:
                pass
            cnn.close()

    def testEscapeArgs(self):
        cnn = dbapi.connect(host = DB_HOST, user = DB_USER, 
                            passwd = DB_PASSWD, db = DB_DB)
        
        cur = cnn.cursor()
        
        cur.execute("truncate tbltest")
        
        cur.execute("insert into tbltest (test_id, test_string) values (%s, %s)", (1, 'piet'))
        cur.execute("insert into tbltest (test_id, test_string) values (%s, %s)", (2, 'klaas'))
        cur.execute("insert into tbltest (test_id, test_string) values (%s, %s)", (3, "pi'et"))
        
        #classic sql injection, would return all rows if no proper escaping is done
        cur.execute("select test_id, test_string from tbltest where test_string = %s", ("piet' OR 'a' = 'a",))
        self.assertEquals([], cur.fetchall()) #assert no rows are found
        
        #but we should still be able to find the piet with the apostrophe in its name
        cur.execute("select test_id, test_string from tbltest where test_string = %s", ("pi'et",))
        self.assertEquals([(3, "pi'et")], cur.fetchall())
        
        #also we should be able to insert and retrieve blob/string with all possible bytes transparently
        chars = ''.join([chr(i) for i in range(256)])
        #print repr(chars)
        
        cur.execute("insert into tbltest (test_id, test_string, test_blob) values (%s, %s, %s)", (4, chars, chars))

        cur.execute("select test_string, test_blob from tbltest where test_id = %s", (4,))
        #self.assertEquals([(chars, chars)], cur.fetchall())
        s, b  = cur.fetchall()[0]
        
        #test blob
        self.assertEquals(256, len(b))
        self.assertEquals(chars, b)

        #test string
        self.assertEquals(256, len(s))
        self.assertEquals(chars, s)

        cur.close()

        cnn.close()
        
        
    def testSelectUnicode(self):
        s = u"Céline"
        
        cnn = dbapi.connect(host = DB_HOST, user = DB_USER, 
                            passwd = DB_PASSWD, db = DB_DB, 
                            charset = 'latin-1', use_unicode = True)
        
        cur = cnn.cursor()

        cur.execute("truncate tbltest")
        cur.execute("insert into tbltest (test_id, test_string) values (%s, %s)", (1, 'piet'))
        cur.execute("insert into tbltest (test_id, test_string) values (%s, %s)", (2, s))
        cur.execute(u"insert into tbltest (test_id, test_string) values (%s, %s)", (3, s))
        
        cur.execute("select test_id, test_string from tbltest")
        
        result = cur.fetchall()
        
        self.assertEquals([(1, u'piet'), (2, u'C\xe9line'), (3, u'C\xe9line')], result)

        #test that we can still cleanly roundtrip a blob, (it should not be encoded if we pass
        #it as 'str' argument), eventhough we pass the qry itself as unicode
        blob = ''.join([chr(i) for i in range(256)])
        
        cur.execute(u"insert into tbltest (test_id, test_blob) values (%s, %s)", (4, blob))
        cur.execute("select test_blob from tbltest where test_id = %s", (4,))
        b2 = cur.fetchall()[0][0]
        self.assertEquals(str, type(b2))
        self.assertEquals(256, len(b2))
        self.assertEquals(blob, b2)
        
if __name__ == '__main__':
    unittest.main(timeout = 60)        
        
         
        
