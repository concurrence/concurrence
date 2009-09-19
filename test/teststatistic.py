from __future__ import with_statement

from concurrence import unittest, Tasklet
from concurrence.statistic import StatisticExtra, Statistic

class TestStatistic(unittest.TestCase):
    
    
    def testStatisticExtra(self):
    
        timer = StatisticExtra(g = 0.1) #low g for fast convergence
        
        for i in range(10):
            with timer.time():
                Tasklet.sleep(0.1)

        self.assertEquals(10, timer.count)
        self.assertAlmostEqual(0.1, timer.avg, places = 1)
        
        timer = StatisticExtra(g = 0.1) #low g for fast convergence
        for i in range(11):
            with timer.time():
                Tasklet.sleep(0.2)

        self.assertEquals(11, timer.count)
        self.assertAlmostEqual(0.2, timer.avg, places = 1)
        
        
    def testStatistic(self):
        
        stat = Statistic(0)
        
        self.assertEquals(0, stat.count)
        stat += 1
        self.assertEquals(1, stat.count)
        stat -= 1
        self.assertEquals(0, stat.count)
        
if __name__ == '__main__':
    unittest.main()
    
