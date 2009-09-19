from concurrence import unittest, Tasklet

class TestTest(unittest.TestCase):
    def testTimeout(self):
        try:
            Tasklet.sleep(4)
            self.fail('expected timeout')
        except TaskletExit:
            pass #caused by timeout
        
if __name__ == '__main__':
    unittest.main(timeout = 2)
