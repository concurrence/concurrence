# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

#TODO supporting closing a halfread resultset (e.g. automatically read and discard rest)

from concurrence import TimeoutError
from concurrence.io import Buffer 
from concurrence.io.socket import Socket 
from concurrence.timer import Timeout
from concurrence.database.mysql import BufferedPacketReader, BufferedPacketWriter, PACKET_READ_RESULT, CAPS, COMMAND 

import logging
import time

try:
    #python 2.6
    import hashlib
    SHA = hashlib.sha1
except ImportError:
    #python 2.5
    import sha
    SHA = sha.new

#import time
class ClientError(Exception):
    @classmethod
    def from_error_packet(cls, packet, skip = 8):
        packet.skip(skip)
        return cls(packet.read_bytes(packet.remaining))
    
class ClientLoginError(ClientError): pass
class ClientCommandError(ClientError): pass
class ClientProgrammingError(ClientError): pass 
    
class ResultSet(object):
    """Represents the current resultset being read from a Connection.
    The resultset implements an iterator over rows. A Resultset must
    be iterated entirely and closed explicitly."""
    STATE_INIT = 0
    STATE_OPEN = 1
    STATE_EOF = 2
    STATE_CLOSED = 3
    
    def __init__(self, connection, field_count):
        self.state = self.STATE_INIT
        
        self.connection = connection
        
        self.fields = connection.reader.read_fields(field_count)
        
        self.state = self.STATE_OPEN
        
    def __iter__(self):
        assert self.state == self.STATE_OPEN, "cannot iterate a resultset when it is not open"
        
        for row in self.connection.reader.read_rows(self.fields):
            yield row

        self.state = self.STATE_EOF
        
    def close(self, connection_close = False):  
        """Closes the current resultset. Make sure you have iterated over all rows before closing it!"""
        #print 'close on ResultSet', id(self.connection)
        if self.state != self.STATE_EOF and not connection_close:
            raise ClientProgrammingError("you can only close a resultset when it was read entirely!")
        connection = self.connection
        del self.connection
        del self.fields
        connection._close_current_resultset(self)
        self.state = self.STATE_CLOSED
            
class Connection(object):
    """Represents a single connection to a MySQL Database host."""
    STATE_ERROR = -1
    STATE_INIT = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2
    STATE_CLOSING = 3
    STATE_CLOSED = 4
    
    def __init__(self):
        self.state = self.STATE_INIT
        self.buffer = Buffer(1024 * 16)        
        self.socket = None
        self.reader = None
        self.writer = None        
        self._time_command = False #whether to keep timing stats on a cmd
        self._command_time = -1
        self._incommand = False
        self.current_resultset = None

    def _scramble(self, password, seed):
        """taken from java jdbc driver, scrambles the password using the given seed
        according to the mysql login protocol"""
        stage1 = SHA(password).digest()
        stage2 = SHA(stage1).digest()
        md = SHA()
        md.update(seed)
        md.update(stage2)
        #i love python :-):
        return ''.join(map(chr, [x ^ ord(stage1[i]) for i, x in enumerate(map(ord, md.digest()))])) 
        
    def _handshake(self, user, password, database):
        """performs the mysql login handshake"""
        
        #init buffer for reading (both pos and lim = 0)
        self.buffer.clear()
        self.buffer.flip()
        
        #read server welcome
        packet = self.reader.read_packet()
        
        self.protocol_version = packet.read_byte() #normally this would be 10 (0xa)
        
        if self.protocol_version == 0xff:
            #error on initial greeting, possibly too many connection error
            raise ClientLoginError.from_error_packet(packet, skip = 2)
        elif self.protocol_version == 0xa:
            pass #expected
        else:
            assert False, "Unexpected protocol version %02x" % self.protocol_version

        self.server_version = packet.read_bytes_until(0)
        
        packet.skip(4) #thread_id
        scramble_buff = packet.read_bytes(8)
        packet.skip(1) #filler
        server_caps = packet.read_short()
        #CAPS.dbg(server_caps)
        
        if not server_caps & CAPS.PROTOCOL_41:
            assert False, "<4.1 auth not supported"
        
        server_language = packet.read_byte()
        server_status = packet.read_short()
        packet.skip(13) #filler
        if packet.remaining: 
            scramble_buff += packet.read_bytes_until(0)
        else:
            assert False, "<4.1 auth not supported"

        client_caps = server_caps 
        
        #always turn off compression
        client_caps &= ~CAPS.COMPRESS
        
        if not server_caps & CAPS.CONNECT_WITH_DB and database:
            assert False, "initial db given but not supported by server"
        if server_caps & CAPS.CONNECT_WITH_DB and not database:
            client_caps &= ~CAPS.CONNECT_WITH_DB

        #build and write our answer to the initial handshake packet
        self.writer.clear()
        self.writer.start()
        self.writer.write_int(client_caps)
        self.writer.write_int(1024 * 1024 * 32) #16mb max packet
        self.writer.write_byte(server_language)
        self.writer.write_bytes('\0' * 23) #filler
        self.writer.write_bytes(user + '\0')
        
        if password:
            self.writer.write_byte(20)
            self.writer.write_bytes(self._scramble(password, scramble_buff))
        else:
            self.writer.write_byte(0)
            
        if database: 
            self.writer.write_bytes(database + '\0')
        
        self.writer.finish(1)
        self.writer.flush()
           
        #read final answer from server
        self.buffer.flip()
        packet = self.reader.read_packet()
        result = packet.read_byte()
        if result == 0xff:
            raise ClientLoginError.from_error_packet(packet)
        elif result == 0xfe:
            assert False, "old password handshake not implemented"
    
    def _close_current_resultset(self, resultset):
        assert resultset == self.current_resultset
        self.current_resultset = None
        
    def _send_command(self, cmd, cmd_text):
        """sends a command with the given text"""
        #self.log.debug('cmd %s %s', cmd, cmd_text)
        
        #note: we are not using normal writer.start/finish here, because the cmd
        #could not fit in buffer, causing flushes in write_string, in that case 'finish' would
        #not be able to go back to the header of the packet to write the length in that case
        self.writer.clear()
        self.writer.write_header(len(cmd_text) + 1 + 4, 0) #1 is len of cmd, 4 is len of header, 0 is packet number
        self.writer.write_byte(cmd)
        self.writer.write_bytes(cmd_text)
        self.writer.flush()

    def _close(self):
        #self.log.debug("close mysql client %s", id(self))
        try:
            self.state = self.STATE_CLOSING
            if self.current_resultset: 
                self.current_resultset.close(True)
            self.socket.close()
            self.state = self.STATE_CLOSED
        except:
            self.state = self.STATE_ERROR
            raise
        
    def connect(self, host = "localhost", port = 3306, user = "", passwd = "", db = "", autocommit = None, charset = None):
        """connects to the given host and port with user and passwd"""
        #self.log.debug("connect mysql client %s %s %s %s %s", id(self), host, port, user, passwd)
        try:
            #print 'connect', host, user, passwd, db
            #parse addresses of form str <host:port>
            if type(host) == str:
                if host[0] == '/': #assume unix domain socket
                    addr = host 
                elif ':' in host:
                    host, port = host.split(':')
                    port = int(port)
                    addr = (host, port)
                else:
                    addr = (host, port)

            assert self.state == self.STATE_INIT, "make sure connection is not already connected or closed"

            self.state = self.STATE_CONNECTING
            self.socket = Socket.connect(addr, timeout = Timeout.current())
            self.reader = BufferedPacketReader(self.socket, self.buffer)
            self.writer = BufferedPacketWriter(self.socket, self.buffer)
            self._handshake(user, passwd, db)
            #handshake complete client can now send commands
            self.state = self.STATE_CONNECTED
            
            if autocommit == False:
                self.set_autocommit(False)
            elif autocommit == True:
                self.set_autocommit(True)
            else:
                pass #whatever is the default of the db (ON in the case of mysql)

            if charset is not None:
                self.set_charset(charset)
            
            return self
        except TimeoutError:
            self.state = self.STATE_INIT
            raise
        except ClientLoginError:
            self.state = self.STATE_INIT
            raise
        except:
            self.state = self.STATE_ERROR
            raise

    def close(self):
        """close this connection"""
        assert self.is_connected(), "make sure connection is connected before closing"
        if self._incommand != False: assert False, "cannot close while still in a command"
        self._close()
        
    def command(self, cmd, cmd_text):
        """sends a COM_XXX command with the given text and possibly return a resultset (select)"""
        #print 'command', cmd, repr(cmd_text), type(cmd_text)        
        assert type(cmd_text) == str #as opposed to unicode
        assert self.is_connected(), "make sure connection is connected before query"
        if self._incommand != False: assert False, "overlapped commands not supported"
        if self.current_resultset: assert False, "overlapped commands not supported, pls read prev resultset and close it"
        try:
            self._incommand = True
            if self._time_command:
                start_time = time.time()
            self._send_command(cmd, cmd_text)
            #read result, expect 1 of OK, ERROR or result set header
            self.buffer.flip()
            packet = self.reader.read_packet()
            result = packet.read_byte()
            #print 'res', result
            if self._time_command:
                end_time = time.time()
                self._command_time = end_time - start_time			
            if result == 0x00:
                #OK, return (affected rows, last row id)
                rowcount = self.reader.read_length_coded_binary()
                lastrowid = self.reader.read_length_coded_binary()
                return (rowcount, lastrowid)
            elif result == 0xff:
                raise ClientCommandError.from_error_packet(packet)
            else: #result set
                self.current_resultset = ResultSet(self, result) 
                return self.current_resultset
        finally:
            self._incommand = False 
        
    def is_connected(self):
        return self.state == self.STATE_CONNECTED
    
    def query(self, cmd_text):
        """Sends a COM_QUERY command with the given text and return a resultset (select)"""
        return self.command(COMMAND.QUERY, cmd_text)
    
    def init_db(self, cmd_text):
        """Sends a COM_INIT command with the given text"""
        return self.command(COMMAND.INITDB, cmd_text)
    
    def set_autocommit(self, commit):
        """Sets autocommit setting for this connection. True = on, False = off"""
        self.command(COMMAND.QUERY, "SET AUTOCOMMIT = %s" % ('1' if commit else '0'))
        
    def commit(self):
        """Commits this connection"""
        self.command(COMMAND.QUERY, "COMMIT")
        
    def rollback(self):
        """Issues a rollback on this connection"""
        self.command(COMMAND.QUERY, "ROLLBACK")
        
    def set_charset(self, charset):
        """Sets the charset for this connections (used to decode string fields into unicode strings)"""
        self.reader.reader.encoding = charset
    
    def set_time_command(self, time_command):
        self._time_command = time_command
        
    def get_command_time(self):
        return self._command_time
    
Connection.log = logging.getLogger(Connection.__name__)

def connect(*args, **kwargs):
    return Connection().connect(*args, **kwargs)

