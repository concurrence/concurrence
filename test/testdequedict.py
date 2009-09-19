import unittest

from concurrence.containers.dequedict import DequeDict

class DequeDictTest(unittest.TestCase):
    def testDequeDict(self):        
        m = DequeDict()
        m.appendleft("piet", 10)
        self.assertEquals(1, len(m))
        m.appendleft("klaas", 20)
        self.assertEquals(2, len(m))
        self.assertTrue("piet" in m)
        self.assertTrue("klaas" in m)
        self.assertFalse("jan" in m)
        self.assertTrue("jan" not in m)
        i = m.iteritemsright()
        self.assertEquals(("piet", 10), i.next())
        self.assertEquals(("klaas", 20), i.next())
        m.movehead("piet")
        i = m.iteritemsright()
        self.assertEquals(("klaas", 20), i.next())
        self.assertEquals(("piet", 10), i.next())
        try: 
            i.next()
            self.fail("expected end of iter")
        except:
            pass
        self.assertEquals(m["piet"], 10)
        del m["piet"]
        self.assertEquals(1, len(m))
        self.assertTrue("piet" not in m)
        self.assertEquals(("klaas", 20), m.pop())
        self.assertEquals(0, len(m))
        
    def testPickle(self):
        m = DequeDict()
        N = 10
        for i in range(N):
            m.append(i, i)
        p1 = m.items()
        import pickle
        s = pickle.dumps(m)
        x = pickle.loads(s)
        p2 = x.items()
        self.assertEquals(p1, p2)
        self.assertEquals(m.d.keys(), x.d.keys())

if __name__ == '__main__':
    unittest.main()

