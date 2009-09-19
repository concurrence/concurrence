# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence.timer import Timeout
from concurrence.database.mysql import ProxyProtocol, PacketReader, PACKET_READ_RESULT, CLIENT_STATES, SERVER_STATES

class Proxy(object):

    #errors
    EOF_READ = -1
    EOF_WRITE = -2
    
    #direction
    CLIENT_TO_SERVER = 1
    SERVER_TO_CLIENT = 2
    
    def __init__(self, clientStream, serverStream, buffer, initState):
        self.clientStream = clientStream
        self.serverStream = serverStream
        self.readStream = self.clientStream
        self.writeStream = self.serverStream
        self.direction = self.CLIENT_TO_SERVER        
        self.protocol = ProxyProtocol(initState)
        self.reader = PacketReader()
        self.buffer = buffer
        self.remaining = 0
        
    def close(self):
        self.clientStream = None
        self.serverStream = None
        self.readStream = None
        self.writeStream = None
        self.protocol = None
        self.reader = None
        self.buffer = None
        
    def reset(self, state):
        self.protocol.reset(state)
        
    def readFromStream(self):
        #read some data from stream into buffer
        if self.remaining:
            #some leftover partially read packet from previous read, put it in front of buffer
            self.buffer.limit = self.buffer.position + self.remaining
            self.buffer.compact()
        else:
            #normal clear, position = 0, limit = capacity
            self.buffer.clear()
        #read data from socket
        return self.readStream.read(self.buffer, Timeout.current())
    
    def writeToStream(self):
        #forward data to receiving socket
        self.buffer.flip()
        while self.buffer.remaining:
            if not self.writeStream.write(self.buffer, Timeout.current()):
                return False
        return True                   
        
    def next(self, readResult, newState, prevState):
        return 0
    
    def cycle(self, readProtocol):
        
        if not self.readFromStream():
            return self.EOF_READ

        #inspect data read according to protocol
        n = 0
        self.buffer.flip()
        while True:                
            readResult, newState, prevState = readProtocol(self.reader, self.buffer)
            #make note of any remaining data (half read packets),
            # we use buffer.compact to put remainder in front next time around
            self.remaining = self.buffer.remaining
            #take action depending on state transition
            n = self.next(readResult, newState, prevState)
            if n != 0:
                break
            if not (readResult & PACKET_READ_RESULT.MORE):
                break

        if n == 0:
            #write data trough to write stream
            if not self.writeToStream():
                return self.EOF_WRITE
        
        return n
    
    def run(self):
        while True:
            state = self.protocol.state
            if state in SERVER_STATES:
                self.direction = self.SERVER_TO_CLIENT
                self.readStream = self.serverStream
                self.writeStream = self.clientStream
                n = self.cycle(self.protocol.readServer)
            elif state in CLIENT_STATES:
                self.direction = self.CLIENT_TO_SERVER
                self.readStream = self.clientStream
                self.writeStream = self.serverStream
                n = self.cycle(self.protocol.readClient)
            else:
                assert False, "Unknown state %s" % state
            if n < 0:
                return n 
