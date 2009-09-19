.. Tasklet documentation.

Tasklets
========

The basic unit of execution in the Concurrence Framework is the :class:`~concurrence.core.Tasklet`.
The full source documentation for tasklets can be found in :mod:`concurrence.core`. Examples
are documented below

Starting a new task
-------------------


You can start a new task by calling :func:`~concurrence.core.Tasklet.new`::

	from concurrence import dispatch, Tasklet
	
	def greeting(msg):
	    print msg
	
	def start():
	    
	    Tasklet.new(greeting)("Hello")
	    Tasklet.new(greeting)("World")
	    
	    print 'start done.'
	
	if __name__ == '__main__':
	    dispatch(start)  


This should print the following to the console::

	start done.
	Hello
	World

This output is explained as follows:

The dispatcher will create a new task for the start function. The start function
will itself create 2 new tasks based on the greeting function.
The :func:`~concurrence.core.Tasklet.new` call is not blocking, so the start function will print that it is done and will exit (its task 
will also be finished at this point). 
Then the dispatcher will scheduled the 2 newly created tasks and run them. Each of them will display their
greetings in turn.

Modifying the example a bit, we can show that the 2 greeters really are two seperate execution units.
This example also introduces the :func:`~concurrence.core.Tasklet.sleep` function.
The sleep function will block the execution of the calling task for the given amount of seconds::

	from concurrence import dispatch, Tasklet
	
	def greeting(msg):
	    while True:
	        print msg
	        Tasklet.sleep(1)
	
	def start():
	    
	    Tasklet.new(greeting)("Hello")
	    Tasklet.new(greeting)("World")
	
	if __name__ == '__main__':
	    dispatch(start)  

This example will alternately show ``Hello`` and ``World`` indefinitly as the 2 tasks themselves do not return
from the ``greeting`` function.
 
Waiting for a task
------------------
Sometimes you will want to halt the current task and wait for 1 or more subtasks to finish and return
their result(s). This can be done using the :func:`~concurrence.core.Tasklet.join` function::

	from concurrence import dispatch, Tasklet
	
	def sum(a, b):
	    #... potentially long calculation, involving calls to databases etc...
	    return a + b
	
	def start():
	    
	    t1 = Tasklet.new(sum)(10, 20)
	    t2 = Tasklet.new(sum)(30, 40)
	    
	    res1 = Tasklet.join(t1)
	    res2 = Tasklet.join(t2)
	    
	    print res1
	    print res2
	
	if __name__ == '__main__':
	    dispatch(start)
	      
In this example 2 subtasks are created by ``start``. 

The start task will then block and wait for each subtask
to finish by *joining* the subtasks using `Tasklet.join` 

The result of the join is the return value of the subtask function.

There are 2 convenient variations for joining tasks: 
    * :func:`~concurrence.core.Tasklet.join_all` which takes a lists of tasks to join
    * :func:`~concurrence.core.Tasklet.join_children` which joins all the children of the current task.

Loop, Interval, Later
---------------------

The functions:

    * :func:`~concurrence.core.Tasklet.loop`
    * :func:`~concurrence.core.Tasklet.interval`
    * :func:`~concurrence.core.Tasklet.later`

Are provided to run a task in a loop, at a specified interval or at a later
time respectively::

	from concurrence import dispatch, Tasklet
	
	def hello(msg):
	    print msg
	    tasklet.sleep(0.5)
	    
	def greeting(msg):
	    print msg
	
	def start():
	    
	    Tasklet.loop(hello)("Hello World")
	    Tasklet.interval(1.0, greeting)("Hi There!")
	    Tasklet.later(5.0, greeting)("Nice to see You!")
    
	if __name__ == '__main__':
	    dispatch(start)  

The current task
----------------

The current task can be retrieved by calling :func:`~concurrence.core.Tasklet.current`. 

This function returns the task of the caller::

	from concurrence import dispatch, Tasklet
	
	def greeting(msg):
	    print Tasklet.current(), msg
	
	def start():
	    
	    Tasklet.interval(1.0, greeting)("Task 1")
	    Tasklet.interval(1.0, greeting)("Task 2")
	    
	if __name__ == '__main__':
	    dispatch(start)  

Task tree and Task names
------------------------

Every task maintains a reference to the task that created it (its parent Task).
You can get the parent with the :func:`~concurrence.core.Tasklet.parent` method.

Every task also maintains a list of subtasks (:func:`~concurrence.core.Tasklet.children`) that it has spawned. 
When a child exits, it is removed from its parents list of children.

Thus a tree of tasks is maintained that can be traversed using the :func:`~concurrence.core.Tasklet.tree` method.

A task can optionally be given a name by passing it to the :func:`~concurrence.core.Tasklet.new` method::

	from concurrence import dispatch, Tasklet
	
	def greeting(msg):
	    print msg
	    Tasklet.sleep(2)
	    print 'done'
	
	def start():
	
	    Tasklet.new(greeting, name = 'task1')("Hello")
	    Tasklet.new(greeting, name = 'task2')("World")
	    Tasklet.new(greeting, name = 'task3')("Hi There")
	
	    while True:
	        Tasklet.sleep(1.0)
	        #print a nice tree of tasks and their subtasks
	        for task, level in Tasklet.current().tree():
	            print "\t" * level, task.name            
	        
	if __name__ == '__main__':
	    dispatch(start)  


	    
