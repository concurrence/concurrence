.. Messages.

Messages
========

The basic unit of *execution* in the Concurrence framework is the :class:`~concurrence.core.Tasklet`.

The basic unit of *communication* between tasks is the :class:`~concurrence.core.Message`.

A message is defined like this::

	class MSG_XXX(Message): pass

.. note::
    By convention, Messages should have UPPERCASE names that start with `MSG_` .

Every Tasklet has a :attr:`~concurrence.core.Tasklet.mailbox` where it receives messages from other tasks.

A Tasklet receives and processes pending messages using the following pattern::
	
    for msg, args, kwargs in Tasklet.receive():
        if msg.match(MSG_XXX):
            ... 
        elif msg.match(MSG_YYY):
            ...
        else:
            ...

The Tasklet will call the :func:`~concurrence.core.Tasklet.receive` iterator in order to receive any pending messages. 
If there are no pending messages, the Tasklet will block until a message arrives. Each message is accompanied by a tuple *args* of positional
arguments and a dictionary *kwargs* of named arguments, both of which may be empty.
The Tasklet will then determine what to do by matching the *msg* using the :func:`~concurrence.core.Message.match` method.

An example of using messages to communicate between tasks:
	
.. literalinclude:: ../examples/message.py

In this example the ``main`` task starts a new task ``printer`` that forever listens for messages using the :func:`~concurrence.core.Tasklet.receive` iterator.

The main task then sends 2 messages to the printer task, which will respond by printing the appropriate message to the console.

.. note::
	Messages by default are 'asynchronous' e.g., the sender does not wait for the receiver task to finish processing it.  
	There is also support for 'synchronous' messages by using the :func:`~concurrence.core.Message.call` method of the Message class. 
	In that case, the *receiver* will have to :func:`~concurrence.core.Message.reply` to 
	the incoming message and the *caller* will block until the reply has been received.
	   

	

	
