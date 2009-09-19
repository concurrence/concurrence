.. _index:

Concurrence
===========

Concurrence is a framework for creating massively concurrent network applications in Python.

It takes a `Lightweight-tasks-with-message-passing` approach to concurrency. 

The goal of Concurrence is to provide an easier programming model for writing high performance network applications than existing solutions (Multi-threading, Twisted, asyncore etc). 

Concurrence uses `Lightweight tasks` in combination with `libevent <http://monkey.org/~provos/libevent/>`_ to expose a high-level synchronous API to low-level asynchronous IO.

Some features:

  * Lightweight Tasks as the basic unit of execution.
  * Message passing as the basic unit of communication (between tasks).
  * Cooperative scheduling of tasks triggered by IO events and Timeouts.
  * Libevent based, always uses the most optimal asynchronous IO multiplexer for the given platform (epoll on linux, KQueue on BSD/OSX).
  * Fast low-level IO buffers implemented in Pyrex.
  * Socket API.
  * DBAPI 2.0 compatible MySQL driver implementation (native & asynchronous, with optimized protocol support written in Pyrex).
  * HTTP / WSGI Server.
  * HTTP Client.
  * Timeouts. All blocking API's provide a timeout parameter.
  * Remoting. Message passing between tasks in diffent processes.
  
.. note::
	Concurrence requires python support for tasklets and channels. These can be provided by either 'Stackless Python' or 'Python + Greenlets'. The latter is easier to work with as it only requires the greenlets package be installed. Stackless Python runs Concurrence programs a bit faster, but the difference is quite small (10-25%) compared to normal Python + Greenlets.	  

Hello World
----------- 

This example can be found in examples/hello.py.

.. literalinclude:: ../examples/hello.py

The basic unit of execution in Concurrence is the 'Tasklet' or 'task'.

Every concurrence program starts with a `dispatch` loop.

The dispatch loop will run forever. It waits
for events (IO, timers, etc) and (re)schedules tasks in response to those events. 

As a convenience the dispatch function takes a 'callable' parameter and will 
start a new task to execute it. 

In the above example 2 tasks are present, e.g. the 'main' task that runs the
dispatch loop (forever), and an (anonymous) task that will execute the 'hello' function and
then exit.

.. note::
	The program will not exit when the 'hello' function is finished. 
	This is because the main task will continue to run in the dispatch loop. 
	You can stop the program with Ctrl-C.


A Highly Concurrent Greeting
----------------------------
The above example is rather boring. In this section we will introduce a variation
that is designed to show off the capabilities of the Concurrence framework for easily
creating highly concurrent network applications:

.. literalinclude:: ../examples/greeter.py

Somebody who is familiar with Socket programming will probably recognize the function of this little program;

It implements a very minimal webserver that outputs the traditional greeting.
You can start this program and point your webbrowser to ``http://localhost:8080`` to see it.

The ``server`` task first creates a `server socket` on port 8080. Then it will loop forever and ``accept`` connections
coming in trough the socket. When a client connection is accepted, a new task is started to handle it. 
The server task itself will continue and wait for more connections to arrive.

The remarkable thing about this example program is that it is able to serve `many thousands of requests per second
to thousands of concurrently connected clients`::
    
    Benchmark of greeter.py (running with stackless python). 
    In this session it handled about 8300 request per second on 1000 concurrent connections:

	httperf --uri=/test --port=8080 --num-calls=1 --num-conns=100000 --rate=10000
	httperf --client=0/1 --server=localhost --port=8080 --uri=/test --rate=10000 
            --send-buffer=4096 --recv-buffer=16384 --num-conns=100000 --num-calls=1
	
	Total: connections 98506 requests 98506 replies 98506 test-duration 11.815 s
	
	Connection rate: >> 8337.1 << conn/s (0.1 ms/conn, <=1022 concurrent connections)
	...	
	Request rate: >> 8337.1 req/s << (0.1 ms/req)
	Request size [B]: 64.0
	
	Reply rate [replies/s]: min 9707.9 avg 9850.2 max 9992.5 stddev 201.3 (2 samples)
	Reply time [ms]: response 8.0 transfer 0.0
	...


The reason for this is that at it's core this program will use `asynchronous IO` ('non-blocking') instead of
more traditional `blocking IO + threads`. The nice thing about using the Concurrence framework is that the complexity normally associated
with asynchronous IO is not visible to the programmer. Concurrence presents a familiar blocking IO model, 
while at the same time achieving high concurrency and low latency by using asynchronous IO in the background.

.. note::
	This is just a simple example of a http server. Concurrence provides a more feature complete HTTP/1.1 webserver (:class:`~concurrence.http.WSGIServer`)
	that exposes a WSGI Interface for creating web-applications. 

Download & Installation
-----------------------

Installation instructions can be found here: :ref:`install`.

Concurrence is available from the `Python package index (PyPI) <http://pypi.python.org/pypi/concurrence>`_.

Source code & Issues
--------------------

The Concurrence Framework source code and issue tracker are hosted at `Google code <http://concurrence.googlecode.com>`_.


Documentation
-------------

.. toctree::
	:maxdepth: 1
	
	tasklets
	messages
	http
	web
	examples
	install
	api

API Reference
-------------
.. toctree::
	:maxdepth: 1

	concurrence.core
	concurrence.io
	concurrence.timer
	concurrence.http
	concurrence.database.mysql.client
	concurrence.web




  	
