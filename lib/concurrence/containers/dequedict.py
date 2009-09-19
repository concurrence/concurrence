# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

class node: pass

class DequeDict(object):
    """dequedict data structure, e.g. a combination of
    a deque and a map collection
    the deque is based on a circular doubly linked list"""
    def __init__(self, i = []):
        self.l = node() #sentinel node for doubly linked list
        self.l.next = self.l
        self.l.prev = self.l
        self.l.key = None
        self.l.value = None
        self.d = {} #key->n
        if i: self.extend(i)

    def extend(self, l):
        """appends values from sequence l to the end of the list"""
        for key, value in l: self.append(key, value)
        
    def append(self, key, value):
        """adds (key, value) to the end of the list"""
        n = node()
        n.key = key
        n.value = value
        #add n to end of list
        self.l.prev.next = n
        n.prev = self.l.prev        
        n.next = self.l
        self.l.prev = n
        #add n to the map
        self.d[key] = n
        
    def appendleft(self, key, value):
        """adds (key, value) to the head of the list"""
        n = node()
        n.key = key
        n.value = value
        #add n to front of list
        self.l.next.prev = n
        n.next = self.l.next        
        n.prev = self.l
        self.l.next = n
        #add n to the map
        self.d[key] = n
        
    def pop(self):
        """removes entry from back of the list and returns (key, value)"""
        n = self.l.prev
        n.prev.next = self.l
        self.l.prev = n.prev
        del self.d[n.key]
        return (n.key, n.value)

    def popleft(self):
        """removes entry from front of the list and returns (key, value)"""
        n = self.l.next
        n.next.prev = self.l
        self.l.next = n.next
        del self.d[n.key]
        return (n.key, n.value)
    
    def iteritemsright(self):
        """a generator that yields items (key, value) from the list, rightmost first"""
        n = self.l.prev
        while n != self.l:
            yield (n.key, n.value)
            n = n.prev
            
    def iteritems(self):
        """a generator that yields items (key, value) from the list, leftmost first"""
        n = self.l.next
        while n != self.l:
            yield (n.key, n.value)
            n = n.next

    def iterkeys(self):
        """a generator that yields keys from the list, leftmost first"""
        for key, _ in self.iteritems():
            yield key

    def itervalues(self):
        """a generator that yields values from the list, leftmost first"""
        for _, value in self.iteritems():
            yield value

    def iterkeysright(self):
        """a generator that yields keys from the list, rightmost first"""
        for key, _ in self.iteritemsright():
            yield key
            
    def movehead(self, key):
        """moves item identified by key to the head of the list"""
        #remove from old position in list
        n = self.d[key]
        n.next.prev = n.prev
        n.prev.next = n.next
        #put in front position of list
        self.l.next.prev = n
        n.next = self.l.next        
        n.prev = self.l
        self.l.next = n
        
    def keys(self):
        return list(self.iterkeys())
    
    def values(self):
        return list(self.itervalues())
    
    def items(self):
        return list(self.iteritems())
    
    def removeall(self, key):
        if key in self: del self[key]
            
    def __getitem__(self, key):
        #TODO key == -1
        return self.d[key].value

    def __delitem__(self, key):
        """removes item with given key"""
        n = self.d[key]
        n.next.prev = n.prev
        n.prev.next = n.next
        del self.d[key]

    def __iter__(self):
        return self.iterkeys()
    
    def __contains__(self, key):
        return key in self.d
    
    def __len__(self):
        return len(self.d)
    
    def __nonzero__(self):
        return bool(self.d)
    
    def __getstate__(self):
        #convert doubly linked list into simple
        #array otherwise pickle will give maxrecursiondepth exeeded problems
        state = self.__dict__.copy()
        state['l'] = list(self.iteritems()) #simple list of tuples (key, value)
        del state['d'] #can be rebuild from array
        return state
    
    def __setstate__(self, state):
        self.__init__(state['l'])

    def __repr__(self):
        return 'dequedict([%s])' % ','.join(['(%s, %s)' % (repr(key), repr(value)) for key, value in self.iteritems()])
    
