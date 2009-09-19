from concurrence import dispatch, unittest
from concurrence.containers.reque import ReorderQueue

class TestReorderQueue(unittest.TestCase):
    def testRequeue(self):
        
        reque = ReorderQueue()
        
        for request in range(10):
            reque.start(request)

        for request, response in reque.finish(1, 'a'):
            self.fail("did not expect any finished request, response")
            
        for request, response in reque.finish(2, 'b'):
            self.fail("did not expect any finished request, response")

        for request, response in reque.finish(3, 'c'):
            self.fail("did not expect any finished request, response")

        finished = []
        for request, response in reque.finish(0, 'zero'):
            finished.append((request, response))
        
        self.assertEquals([(0, 'zero'), (1, 'a'), (2, 'b'), (3, 'c')], finished)
        
        finished = []
        for request, response in reque.finish(4, 'd'):
            finished.append((request, response))
        
        self.assertEquals([(4, 'd')], finished)
        
if __name__ == '__main__':
    unittest.main(timeout = 10.0)
