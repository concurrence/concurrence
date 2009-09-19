# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

from concurrence.database.pool import Pool, NullPool

class SqlAlchemyPooledConnection:
    def __init__(self, pool, connection):
        self.pool = pool
        self.connection = connection

    def __getattr__(self, key):
        return getattr(self.connection, key)
        
    def close(self, invalidated = False):
        connection = self.connection
        pool = self.pool
        self.connection = None 
        self.pool = None
        pool.disconnect(connection, close = invalidated)
    
    def is_valid(self):
        return self.connection is not None
    
    def invalidate(self, e):
        self.close(True)
        
class SqlAlchemyPoolAdapter(Pool):
    def connect(self):
        _, connection = Pool.connect(self)
        return SqlAlchemyPooledConnection(self, connection)

    def dispose(self):
        pass
    
    def recreate(self):
        return self
    
class SqlAlchemyNullPoolAdapter(NullPool):
    def connect(self):
        _, connection = NullPool.connect(self)
        return SqlAlchemyPooledConnection(self, connection)

    def dispose(self):
        pass
    
    def recreate(self):
        return self        
