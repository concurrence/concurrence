# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import sys
import os

import _mysql

PROXY_STATE = _mysql.PROXY_STATE
PACKET_READ_RESULT = _mysql.PACKET_READ_RESULT
SERVER_STATES = _mysql.SERVER_STATES
CLIENT_STATES = _mysql.CLIENT_STATES
READ_RESULT_STATES = _mysql.READ_RESULT_STATES
AUTH_RESULT_STATES = _mysql.AUTH_RESULT_STATES
COMMAND = _mysql.COMMAND

PacketReader = _mysql.PacketReader
PacketReadError = _mysql.PacketReadError
ProxyProtocol = _mysql.ProxyProtocol

from concurrence.io.buffered import BufferedWriter, BufferedReader
from concurrence.timer import Timeout
from concurrence.io import IOStream

class COMMAND:
    QUIT = 0x01
    INITDB = 0x02
    QUERY = 0x03
    LIST = 0x04
    PING = 0x0e
    
class CAPS(object):
    LONG_PASSWORD =   1   # new more secure passwords 
    FOUND_ROWS = 2    #Found instead of affected rows
    LONG_FLAG = 4    #Get all column flags */
    CONNECT_WITH_DB = 8  # One can specify db on connect */
    NO_SCHEMA = 16  #  /* Don't allow database.table.column */
    COMPRESS =       32    # Can use compression protocol */
    ODBC     =   64    # Odbc client */
    LOCAL_FILES =   128    # Can use LOAD DATA LOCAL */
    IGNORE_SPACE=    256    # Ignore spaces before '(' */
    PROTOCOL_41 =   512    # New 4.1 protocol */
    INTERACTIVE =   1024    # This is an interactive client */
    SSL         =     2048   #Switch to SSL after handshake */
    IGNORE_SIGPIPE =  4096    # IGNORE sigpipes */
    TRANSACTIONS  =  8192    # Client knows about transactions */
    RESERVED     =    16384   # Old flag for 4.1 protocol  */
    SECURE_CONNECTION = 32768  # New 4.1 authentication */
    MULTI_STATEMENTS= 65536   # Enable/disable multi-stmt support */
    MULTI_RESULTS   = 131072  # Enable/disable multi-results */

    __ALL__ = {LONG_PASSWORD: 'CLIENT_LONG_PASSWORD', 
               FOUND_ROWS: 'CLIENT_FOUND_ROWS',
               LONG_FLAG: 'CLIENT_LONG_FLAG',
               CONNECT_WITH_DB: 'CLIENT_CONNECT_WITH_DB',
               NO_SCHEMA: 'CLIENT_NO_SCHEMA',
               COMPRESS: 'CLIENT_COMPRESS',
               ODBC: 'CLIENT_ODBC',
               LOCAL_FILES: 'CLIENT_LOCAL_FILES',
               IGNORE_SPACE: 'CLIENT_IGNORE_SPACE',
               PROTOCOL_41: 'CLIENT_PROTOCOL_41',
               INTERACTIVE: 'CLIENT_INTERACTIVE',
               SSL: 'CLIENT_SSL',
               IGNORE_SIGPIPE: 'CLIENT_IGNORE_SIGPIPE',
               TRANSACTIONS: 'CLIENT_TRANSACTIONS',
               RESERVED: 'CLIENT_RESERVED',
               SECURE_CONNECTION: 'CLIENT_SECURE_CONNECTION',
               MULTI_STATEMENTS: 'CLIENT_MULTI_STATEMENTS',
               MULTI_RESULTS: 'CLIENT_MULTI_RESULTS'}
 
    @classmethod
    def dbg(cls, caps):
        for value, name in cls.__ALL__.items():
            if caps & value:
                print name

def create_scramble_buff():
    import random
    return ''.join([chr(random.randint(0, 255)) for _ in xrange(20)])

        
class BufferedPacketWriter(BufferedWriter):
    #TODO make writers really buffered
    def __init__(self, stream, buffer):
        BufferedWriter.__init__(self, stream, buffer)
        self.ERROR_TEMPLATE = "%s"

    def write_error(self, errno, errmsg):
        self.buffer.write_byte(0xFF) #ERROR
        #ERROR CODE:
        self.buffer.write_byte((errno >> 0) & 0xFF)
        self.buffer.write_byte((errno >> 8) & 0xFF)
        #ERROR MSG:
        self.buffer.write_bytes(self.ERROR_TEMPLATE % errmsg)
        
    def write_ok(self, field_count, affected_rows, insert_id, server_status, warning_count, msg = ''):
        self.buffer.write_byte(field_count)  
        self.buffer.write_byte(affected_rows)
        self.buffer.write_byte(insert_id) 
        self.buffer.write_short(server_status) #server Status
        self.buffer.write_short(warning_count) 
        if msg:
            self.buffer.write_bytes(msg)
      
    def write_greeting(self, scramble_buff, protocol_version, server_version, thread_id, server_caps, server_language, server_status):

        self.buffer.write_byte(protocol_version)
        self.buffer.write_bytes(server_version + '\0')
        self.buffer.write_int(thread_id)
        self.buffer.write_bytes(scramble_buff[:8])
        self.buffer.write_byte(0) #filler
        self.buffer.write_short(server_caps)
        self.buffer.write_byte(server_language)
        self.buffer.write_short(server_status)
        self.buffer.write_bytes('\0' * 13) #filler
        self.buffer.write_bytes(scramble_buff[8:])
        
    def write_header(self, length, packet_number):
        self.buffer.write_int((length - 4) | (packet_number << 24))
        
    def start(self):
        """starts building a packet"""
        self.start_position = self.buffer.position #remember start of header
        self.buffer.skip(4) #reserve room for header
        
    def finish(self, packet_number):
        """finishes packet by going back to start of packet and writing header and packetNumber"""
        position = self.buffer.position
        length = self.buffer.position - self.start_position 
        #print length
        self.buffer.position = self.start_position
        self.write_header(length, packet_number)
        self.buffer.position = position
        
    def write_int(self, i):
        self.buffer.write_int(i)

    def write_lcb(self, b):
        assert b < 128, "TODO larger numbers"
        self.buffer.write_byte(b)
        
    def write_lcs(self, s):
        self.write_lcb(len(s))
        self.buffer.write_bytes(s)
        

class BufferedPacketReader(BufferedReader):
    def __init__(self, stream, buffer):
        BufferedReader.__init__(self, stream, buffer)
        self.stream = stream
        self.buffer = buffer
        self.reader = PacketReader(buffer)

    def read_packets(self):
        reader = self.reader
        
        READ_RESULT_END = PACKET_READ_RESULT.END
        READ_RESULT_MORE = PACKET_READ_RESULT.MORE

        while True:
            read_result = reader.read_packet()
            if read_result & READ_RESULT_END:
                yield reader.packet                    
            if not (read_result & READ_RESULT_MORE):
                self._read_more()
 
    def read_packet(self):
        return self.read_packets().next()

    def read_length_coded_binary(self):
        return self.reader.read_length_coded_binary()
    
    def read_fields(self, field_count):
        
        #generator for rest of result packets
        packets = self.read_packets()
        
        #read field types
        fields = []
        
        reader = self.reader
        i = 0
        while i < field_count:            
            _ = packets.next()
            fields.append(reader.read_field_type())
            i += 1

        #end of field types
        packet = packets.next()
        assert packet.read_byte() == 0xFE, "expected end of fields"
        
        return fields 

    def read_rows(self, fields, row_count = 100):
        reader = self.reader
        
        READ_RESULT_EOF = PACKET_READ_RESULT.EOF
        READ_RESULT_MORE = PACKET_READ_RESULT.MORE

        while True:
            read_result, rows = reader.read_rows(fields, row_count)
            for row in rows:
                yield row
            if read_result & READ_RESULT_EOF:
                break
            if not (read_result & READ_RESULT_MORE):
                self._read_more()

            
