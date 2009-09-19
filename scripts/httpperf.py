#!/usr/bin/env stackless

from concurrence import dispatch, quit, Tasklet, Channel
from concurrence.http.client import HTTPConnection
from concurrence.statistic import gamma_filter
from concurrence.containers.deque import Deque
from optparse import OptionParser

import urlparse
import logging
import time
import sys

def parse_options():
    
    parser = OptionParser(usage="%prog [options]", version="%prog 1.0", prog="httpperf")
    parser.add_option("--url", type="string", default=None, dest="url", metavar="URL", help="the url to fetch")
    parser.add_option("--sessions", type="int", default=1, dest="sessions", metavar="SESSIONS", help="")
    parser.add_option("--requests", type="int", default=-1, dest="requests", metavar="REQUESTS", help="")
    parser.add_option("--count", type="int", default=-1, dest="count", metavar="COUNT", help="")
    parser.add_option("--delay", type="float", default=1, dest="delay", metavar="DELAY", help="")
    parser.add_option("--pipeline", type="int", default=1, dest="pipeline", metavar="PIPELINE", help="")
    parser.add_option("--dump", action="store_true", dest="dump", metavar="DUMP", help="")
    (options, _) = parser.parse_args()
    return options
    
    
class HttpPerf(object):
    def __init__(self, options):
        self.status = {}
        self.request = 0
        self.lastRequest = None
        self.lastTime = None
        self.options = options
        self.dispenser = Channel()
        
    def session_response_reader(self, cnn, pipeline_tokens):
        #TODO use tasklet.loop, must be extended such that you can stop the loop by returning something (or StopIteration?)
        while True:
            response = cnn.receive()

            #read status
            self.count('status', response.status)
            
            connection_header = response.get_header('Connection')
            if connection_header == 'close' and self.options.requests != 1:
                print >> sys.stderr, "WARNING: Server closed connection, no Keep Alive!, please use --requests=1"
                
            
            #this will read the complete response
            if self.options.dump:
                print response.status
                for k, v in response.headers:
                    print "%s: %s" % (k, v)
                for chunk in response:
                    sys.stdout.write(chunk)
                sys.stdout.flush()
                print
            else:
                list(response)
            #print 'resp'
            pipeline_tokens.append(True)
                
    def session(self, host, port, path):
        cnn = None

        pipeline_tokens = Deque()

        for _ in range(self.options.pipeline): # can append take iterator?, or list?
            pipeline_tokens.append(True)

        try:
            cnn = HTTPConnection()
            cnn.connect((host, port))

            Tasklet.new(self.session_response_reader)(cnn, pipeline_tokens)
            
            requests = 0 #no requests in this session
            while True:

                if self.options.requests != -1 and requests >= self.options.requests:
                    break #we are done with this session
                       
                if self.dispenser.receive() is None:
                    return False #we are done globally

                pipeline_tokens.popleft(True)

                #do the request
                cnn.send(cnn.get(path))
                #print response
                  
                requests += 1
                
                self.count('request')
                
        finally:    
            #if response_reader_task is not None:   
            #    response_reader_task.kill()
            if cnn is not None:
                cnn.close() 

        return True

    def sessions(self):
        u = urlparse.urlparse(self.options.url)
        
        if ':' in u.netloc:
            host, port = u.netloc.split(':')
            port = int(port)
        else:
            host, port = u.netloc, 80
    
        path = urlparse.urlunsplit(['', '', u.path, u.query, u.fragment])
        if path == '':
            path = '/'
    
        try:
            while True:
                if not self.session(host, port, path):
                    return
                    
        except TaskletExit:
            raise
        except:
            logging.exception("exception in http session")
        
    def count(self, attr, key = None, inc = 1):
        a = getattr(self, attr)
        if key is None:
            v = a + inc
            setattr(self, attr, v)
            return v
        else:
            if not key in a:
                a[key] = inc
            else:
                a[key] = a[key] + inc
            return a[key]
       
    def show(self):
        now = time.time()
        
        if self.lastTime is not None:
            reqSec = (self.request - self.lastRequest) / (now - self.lastTime)
            reqSec = gamma_filter(self.lastReqSec, reqSec, 0.60)
        else:
            reqSec = 0.0
            
        print >> sys.stderr, self.status, self.request, reqSec
        
        self.lastTime = time.time()
        self.lastRequest = self.request
        self.lastReqSec = reqSec
        
    def dispense(self):
        if self.options.count == -1: 
            #run forever
            while True:
                self.dispenser.send(True)
                if self.options.delay > 0.0:
                    Tasklet.sleep(self.options.delay)
        else:
            #a fixed number of total requests
            for i in range(self.options.count):
                self.dispenser.send(True)
                if self.options.delay > 0.0:
                    Tasklet.sleep(self.options.delay)
            for i in range(self.options.sessions):
                self.dispenser.send(None)
        
    def run(self):
        #show stats every second:
        Tasklet.interval(1.0, self.show, immediate = True)()
        
        #dispenses tokens for doing a request to sessions:
        Tasklet.new(self.dispense)()
        
        #start up sessions, and wait till they are finished
        Tasklet.join_all([Tasklet.new(self.sessions)() for _ in range(self.options.sessions)])
        
        quit()
           
def main():

    options = parse_options()
    
    if not options.url:
        assert False, "provide a url please!"

    perf = HttpPerf(options)
    perf.run()

if __name__ == '__main__':
    dispatch(main)
