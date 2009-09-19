# Copyright (C) 2009, Hyves (Startphone Ltd.)
#
# This module is part of the Concurrence Framework and is released under
# the New BSD License: http://www.opensource.org/licenses/bsd-license.php

import logging
logging.basicConfig(level = logging.ERROR)
#logging.basicConfig(level = logging.DEBUG)

import sys
import time

from optparse import OptionParser

from concurrence import Tasklet, dispatch, quit
from concurrence.database.mysql import client
from concurrence.database.mysql.client import Connection
from concurrence.database.pool import Pool

def parse_options():
    
    parser = OptionParser(usage="%prog [options]", version="%prog 1.0", prog="queryblaster")
    parser.add_option("-u", type="string", default="root", dest="user", metavar="USERNAME", help="")
    parser.add_option("-p", type="string", default='', dest="passwd", metavar="PASSWORD", help="")
    parser.add_option("--host", type="string", default='localhost', dest="host", metavar="HOST", help="")
    parser.add_option("--database", type="string", default='', dest="db", metavar="DATABASE", help="")
    parser.add_option("--port", type="int", default=3306, dest="port", metavar="PORT", help="")
    parser.add_option("--sessions", type="int", default=1, dest="sessions", metavar="SESSIONS", help="number of simultanious connections")
    parser.add_option("--qpc", type="int", default=1, dest="queries_per_connection", metavar="QPC", help="queries per session")
    parser.add_option("--count", type="int", default=1, dest="query_count", metavar="QUERY_COUNT", help="total query count (accross all sessions)") 
    parser.add_option("--query", type="string", default="select 1", dest="query", metavar="QUERY", help="the query (default = select 1)")
    parser.add_option("--use_pool", type="int", default=0, dest="use_pool", metavar="NR_CONNECTIONS", help="use pooling = int, nr of connections in pool")
       
    (options, _) = parser.parse_args()
    return options

class Session(object):
    def __init__(self, options):
        self.options = options
    
    def get_connection(self):
        if self.options.use_pool:
            _, cnn = self.options.pool.connect()
            return cnn
        else:
            cnn = Connection()
            cnn.connect(**self.options.dbargs)
            return cnn

    def end_connection(self, cnn):
        if cnn is None:
            return
        if self.options.use_pool:
            return self.options.pool.disconnect(cnn)
        else:
            if cnn.is_connected():
                cnn.close()
        
    def run(self):
        query_count = 0
        try:
            while True:
                cnn = None
                try:
                    cnn = self.get_connection()
                    for i in range(self.options.queries_per_connection):
                        if self.options.query_count > 0:
                            self.options.query_count -= 1
                            rs = cnn.query(self.options.query)
                            list(rs) #reads out result set
                            rs.close()
                            query_count += 1
                        else:
                            return query_count
                finally:
                    self.end_connection(cnn)
        except Exception:   
            logging.exception("in session")
            raise
        
def main():

    options = parse_options()

    options.dbargs = {'host': options.host, 
                      'port': options.port, 
                      'user': options.user, 
                      'passwd': options.passwd, 
                      'db': options.db}
        
    if options.use_pool:
        options.pool = Pool(client, options.dbargs, options.use_pool)
    
    for i in range(options.sessions):
        session = Session(options)
        Tasklet.new(session.run)()

    try:
        query_count = options.query_count
        start = time.time()
        query_count_done = sum(Tasklet.join_children())
        end = time.time()
        print end - start, query_count_done, query_count_done / (end - start)
    except Exception:
        logging.exception("must be an error in one of the sessions")
    
    quit()
    
if __name__ == '__main__':
    dispatch(main)