# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import time

def gamma_filter(prev, v, gamma = 0.95):
    return (gamma * prev) + ((1.0 - gamma) * v)
    
class Statistic(object):
    def __init__(self, v, g = 0.90):
        self._start_v = v
        self._v = v
        self._g = g
        self._lastV = None
        self._deltaV = None
        
    def reset(self):
        self._lastV = None
        self._deltaV = None
        
    @property    
    def count(self):
        return self._v
    
    def set_count(self, count):
        self._v = count

    def __add__(self, o):
        self._v += o
        return self

    def __sub__(self, o):
        self._v -= o
        return self
        
    @property
    def delta(self):
        """count/s"""
        return self._deltaV
    
    def __str__(self):
        return "#%d;%3.3f/s" % (self._v, self._deltaV or 0.0) 
    
    def __json__(self):
        return {'v': self._v, 'dv': self._deltaV or None}
        
    def update(self, elapsed = 0.0):
        """update the statistic delta's according to the elapsed period of time"""
        if self._lastV and elapsed:
            newDeltaV = (self._v - self._lastV) / elapsed
            if self._deltaV:
                self._deltaV = gamma_filter(self._deltaV, newDeltaV, self._g)
            else:
                self._deltaV = newDeltaV
        self._lastV = self._v
        
    @classmethod
    def find(cls, o):
        """find all statistics in o"""
        if isinstance(o, cls):
            yield o
        elif type(o) == dict:
            for v in o.values():
                for s in cls.find(v):
                    yield s
        elif type(o) == list:
            for v in o:
                for s in cls.find(v):
                    yield s
        else:
            pass

    @classmethod
    def updateall(cls, o, elapsed = 0.0):
        """finds all statistics in o and calls their update methods"""
        if elapsed > 0.0:
            for s in cls.find(o):
                s.update(elapsed)
        return o
            
    @classmethod
    def resetall(cls, o):
        """finds all statistics in o and calls their reset methods"""
        for s in cls.find(o):
            s.reset()

class _Time(object):
    def __init__(self, statistic):
        self._statistic = statistic
        
    def __enter__(self):
        self._start_time = time.time()
         
    def __exit__(self, type, value, traceback):        
        end_time = time.time()
        self._statistic += 1
        self._statistic.update_avg(end_time - self._start_time)

#TODO better name
class StatisticExtra(Statistic):
    def __init__(self, g = 0.90):
        Statistic.__init__(self, 0, g)
        self._avg = 0.0
        self._max = None
        self._min = None
    
    def reset(self):
        Statistic.reset(self)
        self._avg = 0.0
        self._max = None
        self._min = None
        
    def __str__(self):
        return "#%d;%3.3f/s;avg:%3.3f;min:%3.3f;max:%3.3f" % \
                (self.count, self.delta or 0.0, self._avg, 
                 -0.0 if self._min is None else self._min,
                 -0.0 if self._max is None else self._max) 

    def __json__(self):
        return {'v': self.count, 'dv': self.delta or None, 'avg': self._avg,
                'min': self._min, 'max': self._max}
    
    @property        
    def avg(self):
        return self._avg
    
    def update_avg(self, avg):
        self._avg = gamma_filter(self._avg, avg, self._g)
        if self._max is None or avg > self._max:
            self._max = avg
        if self._min is None or avg < self._min:
            self._min = avg
        
    def time(self):
        return _Time(self)
    
class StatisticMinMax(Statistic):
    def __init__(self, g = 0.90):
        Statistic.__init__(self, 0, g)
        self._max = None
        self._min = None

    def update_min_max(self):
        if self._max is None or self._v > self._max:
            self._max = self._v
        if self._min is None or self._v < self._min:
            self._min = self._v

    def set_count(self, count):
        self._v = count
        self.update_min_max()

    def __add__(self, o):
        self._v += o
        self.update_min_max()
        return self

    def __sub__(self, o):
        self._v -= o
        self.update_min_max()
        return self

    def update(self, elapsed = 0.0):
        pass
    
    def reset(self):
        self._max = None
        self._min = None
    
    def __str__(self):
        return "#%d;min:%d;max:%d" % \
                (self.count, 
                 -0.0 if self._min is None else self._min,
                 -0.0 if self._max is None else self._max) 

    def __json__(self):
        return {'v': self.count, 'min': self._min, 'max': self._max}

