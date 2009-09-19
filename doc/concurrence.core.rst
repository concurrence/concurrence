:mod:`concurrence.core` -- The concurrence core module
======================================================

.. module:: concurrence.core
   :platform: Unix
   :synopsis: Provides the basic abstractions of the Concurrence Framework.
.. moduleauthor:: Henk Punt <henk@hyves.nl>

.. autofunction:: dispatch
.. autofunction:: quit
 
.. autoclass:: Tasklet
   :members:
   
.. autoclass:: Channel
   :members:

.. autoclass:: Message
   :members:

.. autoclass:: Mailbox
   :members: pop, popleft, append, appendleft
   
   
.. autoexception:: JoinError

.. autoexception:: TimeoutError


