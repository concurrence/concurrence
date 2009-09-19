# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from __future__ import with_statement

import logging
import time

from concurrence import TimeoutError, Channel, Tasklet
from concurrence.containers import Deque
from concurrence.timer import Timeout
from concurrence.statistic import Statistic, StatisticExtra


class BasePool(object):
    def __init__(self, connector, dbargs, connect_timeout):
        self._connector = connector
        self._dbargs = dbargs
        self._connect_timeout = connect_timeout

        self._connections = set() #the whole set of connections
        self._connecting = 0 #the number of connection currently being made
        
        self._new_connection_timer_statistic = StatisticExtra()
        self._close_connection_timer_statistic = StatisticExtra()        
        self._failed_connect = Statistic(0)

    @property
    def connection_count(self):
        return len(self._connections) + self._connecting

    def _new(self):
        """creates a new connection with the given arguments"""
        self.log.debug("new connection")
        with self._new_connection_timer_statistic.time():        
            self._connecting += 1
            try:
                connection = self._connector.connect(**self._dbargs)
            except Exception:
                self._failed_connect += 1
                raise
            finally:
                self._connecting -= 1
            
            connection._pool = self
            connection._created_time = time.time()
            self._connections.add(connection)
        
        self.log.debug("new connection created, in pool: %s", self)
        return connection
        
    def _close(self, connection):
        """close given connection and remove it from the pool"""
        assert hasattr(connection, '_pool'), "this connection did not come from a pool"
        assert connection._pool == self, "this connection did not come from this pool"
        self.log.debug("closing connection")

        #update close connection stats
        self._close_connection_timer_statistic += 1
        self._close_connection_timer_statistic.update_avg(time.time() - connection._created_time)
        
        self._connections.remove(connection)
        del connection._pool
        
        try:
            connection.close()
            self.log.debug("connection closed: %s", self)
        except Exception:
            self.log.exception("%s: error while closing connection", self)
            raise
        
    def __statistics__(self):
        return {} #can be overridden by subclass to provide detailed stats

    def _safe_dbargs(self):
        """create a nice unique string identifying this pool with the dbargs, in a safe way (e.g. without showing password"""
        return ';'.join(['%s' % self._dbargs.get(k, '') for k in ['host', 'port', 'db', 'user']])

    def __str__(self):
        return "<pool: %s>" % self._safe_dbargs()
    
    @property
    def name(self):
        return self._safe_dbargs()

            
class Pool(BasePool):
    log = logging.getLogger('Pool')
    
    def __init__(self, connector, dbargs, max_connections = 10, connect_timeout = -1, max_connection_age = None,
                 max_connection_age_reaper_interval = 60):
        super(Pool, self).__init__(connector, dbargs, connect_timeout)
        
        self._max_connections = max_connections
        self._max_connection_age = max_connection_age
        
        #some statistics        
        self._queue_wait_timer_statistic = StatisticExtra()
        self._queue_wait_tasks_statistic = StatisticExtra()        
        
        self._pool = Deque() #the pool of available idle connections
                
        #watch for server disconnects on idle connections:
        self._idle_disconnect_channel = Channel()
        self._idle_disconnect_reaper_task = Tasklet.loop(self._idle_disconnect_reaper, daemon = True)()
        
        #check for old connections
        if self._max_connection_age is not None:
            self._old_connection_reaper_task = Tasklet.interval(max_connection_age_reaper_interval, 
                                                                self._old_connection_reaper, daemon = True)()
        
    def __statistics__(self):
        return {'connections': {'total': self.connection_count, 
                                'connection_failed': self._failed_connect,
                                'connection_new': self._new_connection_timer_statistic,
                                'connection_close': self._close_connection_timer_statistic,
                                'queue_wait_time': self._queue_wait_timer_statistic,
                                'queue_wait_task': self._queue_wait_tasks_statistic}}
        
    @property
    def idle_connection_count(self):
        return len(self._pool)
    
    def _idle_disconnect_reaper(self):
        """waits for readability events in the idle_disconnect_channel
        this signals a EOF from the database, so we can remove the connection 
        from the pool"""
        readable = self._idle_disconnect_channel.receive()
        #now we now which fd became readable, figure out which connection it was
        disconnected_connection = None
        for connection in self._pool:
            if connection.socket.readable == readable:
                disconnected_connection = connection
        if disconnected_connection is None:
            self.log.error("%s: received disconnected event, but could not find corresponding connection!", self)
        else:
            self._close(disconnected_connection)
            self.log.warn("%s: connection disconnected by database server while idle.", self)

    def _old_connection_reaper(self):
        """checks all connections in the pool for their age
        if too old and idle, gets closed immediatly
        if too old and in use, gets closed on next disconnect"""
        now = time.time()
        close_connections = [] #to prevent concurrent modification in loop:
        for connection in self._connections:
            age = now - connection._created_time
            if age > self._max_connection_age:
                close_connections.append(connection)
                
        for connection in close_connections:
            if connection in self._pool: #it is idle, close now
                self.log.debug("%s: closing idle connection with old age", self)
                self._close(connection)
            else:
                self.log.debug("%s: will close busy connection with old age on next disconnect", self)
                connection.__close__ = True #not idle, will be closed on next disconnect
                
    def _get_connection_from_pool(self):
        self.log.debug("get conn from pool")
        return self._pool.pop(True, Timeout.current())
        
    def _return_connection_to_pool(self, connection):
        """when connection becomes readable while in the idle pool,
        this signals a server disconnect"""
        self.log.debug("return conn to pool")
        connection.socket.readable.notify(self._idle_disconnect_channel)
        self._pool.append(connection)
        
    def connect(self):
        """get a connection from the pool, will wait for maxWaitTime for connection to become
        available, or will create a new connection if connectioncount < max_connections"""
        with Timeout.push(self._connect_timeout):
            if (not self._pool) and (self.connection_count < self._max_connections):
                #none available, but still allowed to create new connection
                try:                    
                    return (True, self._new())
                except TaskletExit:
                    raise #server exiting
                except TimeoutError:
                    raise
                except:
                    self.log.exception("%s: could not create new connection for pool", self)
                    #we will continue from here waiting for idle connection
    
            #if we are here, either connection is available, not available but no more connections are allowed,
            #or there was some exception creating a new connection        
            self.log.debug("waiting for connection")
            with self._queue_wait_timer_statistic.time():
                #keep track off the amount of other tasks waiting for a connection
                balance = self._pool.channel.balance
                waiters = -balance if balance < 0 else 0
                self._queue_wait_tasks_statistic.set_count(waiters)
                self._queue_wait_tasks_statistic.update_avg(waiters)
                connection = self._get_connection_from_pool()
                self.log.debug("got connection")
                return (False, connection)
    
    def _close(self, connection):
        """close given connection and remove it from the pool"""
        #if it is currently in the pool, remove it
        if connection in self._pool:
            self._pool.remove(connection)   
        #close it
        super(Pool, self)._close(connection)
    
    def disconnect(self, connection, close = False):
        """return connection to pool. if close is given, it is closed and removed instead"""
        assert hasattr(connection, '_pool'), "this connection did not come from a pool"
        assert connection._pool == self, "this connection did not come from this pool"
        
        if hasattr(connection, '__close__'): #set by old age reaper
            self.log.debug("close on old age")
            close = True
        
        if close:
            #close connection and remove from pool
            self._close(connection)
            return True
        else:
            #return the connection to idle queue
            self._return_connection_to_pool(connection)                        
            self.log.debug("returning connection to pool %s", self)
            return False


class NullPool(BasePool):
    log = logging.getLogger('NullPool')
    
    def __init__(self, connector, dbargs, connect_timeout = -1):
        super(NullPool, self).__init__(connector, dbargs, connect_timeout)

    def __statistics__(self):
        return {'connections': {'total': self.connection_count, 
                                'connection_failed': self._failed_connect,
                                'connection_new': self._new_connection_timer_statistic,
                                'connection_close': self._close_connection_timer_statistic}}
        
    def connect(self):
        self.log.debug("connect: %s", self)
        with Timeout.push(self._connect_timeout):
            return (True, self._new())

    def disconnect(self, connection, close = True):
        self._close(connection)
            
