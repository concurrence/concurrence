
import time

from concurrence import dispatch, Tasklet, TimeoutError, unittest
from concurrence.containers.deque import Deque

class TestDeque(unittest.TestCase):
    def testNonBlock(self):
        d = Deque()
        d.append(10)
        d.append(20)
        self.assertEqual(10, d.popleft())
        self.assertEqual(20, d.popleft())

        d = Deque()
        d.append(10)
        d.append(20)
        self.assertEqual(20, d.pop())
        self.assertEqual(10, d.pop())
        
    def testBlock(self):
        d = Deque()
        Tasklet.later(1.0, d.append)(20)
        s = time.time()
        #should block on pop
        self.assertEquals(20, d.pop(True))
        e = time.time()
        self.assertTrue((e - s) > 1.0)
        
    def testBlock2(self):
        d = Deque()
        Tasklet.later(0.5, d.append)(10)
        Tasklet.later(1.0, d.append)(20)
        Tasklet.sleep(1.5)
        s = time.time()
        #should not block
        self.assertEquals(20, d.pop(True))
        self.assertEquals(10, d.pop(True))
        e = time.time()
        self.assertAlmostEqual(0.0, (e - s), places = 1)
        
    def testBlockTimeout(self):
        d = Deque()
        s = time.time()
        try:
            d.pop(True, 2.0)
            self.fail("expected timeout")
        except TimeoutError:
            pass
        e = time.time()
        self.assertAlmostEqual(2.0, (e - s), places = 1)
        
if __name__ == '__main__':
    unittest.main(timeout = 10.0)
