.. Examples

Examples
===========

A collection examples on how to use the Concurrence Framework

A Simple Chat Server
--------------------

In an example of how Tasks and Messages are typically used together.
This example implements a simple multi-user chat server:

.. literalinclude:: ../examples/chat.py
	:linenos:
	
You can start it with ``stackless chat.py`` and then start 1 or more sessions using ``telnet localhost 9010``. 
If you type some message in one session, it will be multi-cast to all other currently connected sessions.
A quick overview of the code:

	* First a new tcp 'server' is started. 
	* For each incoming connection a new client task is created that will execute the 'handle' function.
	* The client task will in turn start 2 child tasks; 'reader' and 'writer' that are responsible for reading and writing lines from/to the corresponding client.
	* The client task then will enter a 'receive' loop and repond to messages until it receives the quit message.
 	* Coorperation between the tasks is handled by the 3 messages defined at the top
	* Incoming lines are read by 'reader', it messages the client_task, which in turn multi-casts the line to all other connected client_tasks. 
 	 
	
  
