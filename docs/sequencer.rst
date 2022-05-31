Sequencer
=========

The `.Sequencer` takes a list of operations to be performed on a
station and, using their dependencies, calculates a priority for each
`.Operation` which it then uses to schedule the sequence of operations
based on the configured threads available on the station.

Each operation is a uniquely named class derived from the `.Operation`
class, and the class name is used as the id of the `.Operation`.  The
sequence specification file for a station, operations.json, specifies
the operation id(s) that each Operation depends on, i.e. requires to
be completed successfully before it can run. This allows us to
calculate a simple relationship between the operations and assign them
a priority of execution based on how many later jobs depend on them,
which allows us to calculate the critical path and attempt to execute
those operations first at each stop.

The `.Sequencer` works using 4 simple lists to hold the state of each
Operation:

- the waiting list, where operations wait until their dependencies have completed
- the ready list, which holds operations that are ready to run because their dependencies have been completed
- the running list, which hold operations currently executing
- the completed list, which holds operations that have finished (successfully or not)

All `.Operation` in the ready list have had all their dependencies
completed, but may be forced to stay in the ready list due to
threading limits of the station or because they are waiting on some
tool, algorithm result, or similar data. For example, one step may
submit data to an algorithm server and return a request id as data,
and the following step may use that request id to query the algormithm
server whether the result is ready yet, returning REQUEUE until the
algorithm result is ready for further processing.

Each `.Operation` has a prepare method which is called just before it
is run, and this method can return either `.OperationState.COMPLETED`
or `.OperationState.REQUEUE`; the latter asks that the operation be
returned to the ready list. This prepare method can be used to ensure
tools, resources, or algorithm results are available.

A running `.Operation` can exit with `.OperationState.COMPLETED`,
`.OperationState.REQUEUE`, or `.OperationState.ERROR`. If exiting with
`REQUEUE <.OperationState.REQUEUE>`, the `.Operation` will be moved
from the running list back to the ready list. If exiting `COMPLETED
<.OperationState.COMPLETED>` or `ERROR <.OperationState.ERROR>`, the
`.Operation` will be moved to the completed list, except that an
`ERROR <.OperationState.ERROR>` will trigger the sequence of
operations to abort, the assumption being that any error exit state
indicates a fatal result was obtained and the sequence of operations
cannot continue.

When the `.Sequencer` begins, it starts by putting all the operation ids
into the waiting list, then it repeatedly iterates over the lists,
doing:

1. For each operation in the waiting list, if all the dependent jobs are in the completed list, then move the operation id to the ready list.
#. While the current count of operations running is less than the station maximum, try to run a operation from the ready list, moving that operation id to the running list. Select operations with the highest priority first.

    a. Run the operation's prepare method, and use the exit code to decide whether to move it to the running list or return it to the ready list.

#. For each operation id in the running list, monitor it to see when it completes. Upon completion, gather operation results and move operation from the running to the completed list.
#. Stop when there are no operation ids in the waiting, ready, or running lists, or when an operation returns ERROR.

stationexec.sequencer.sequencer module
--------------------------------------

.. automodule:: stationexec.sequencer.sequencer
    :members:
    :undoc-members:
    :show-inheritance:

Operation
=========

An `.Operation` is a step within the larger sequence of operations
that a particular station executes. The base class implements support
routins, and the actual station implementation should override the
`~.Operation.operation_action()` method with the operations to
perform.

An Operation may also override the `~.Operation.initialize()`
method, and may override the `~.Operation.prepare()` method to perform
any necessary checks before the operation is run, such checking as
whether an algorithm result is available or a tool is available.

When completed, the `.Sequencer` will call the `~.Operation.cleanup()`
method for the Operation.

When it begins executing, the Operation will be passed the data
specified in the station's ``operations.json`` file. This data can
include references to results from earlier operations by specifying
the earlier result name as ``result:<name of result>``. (Note: This
requires that multiple operations will not generate the same result
name.) The incoming data dict is provided as the first argument to the
`~.Operation.operation_action()` method. The second argument to that
method is the dict of expected results to be generated by this
Operation, for reference. The generated results *will* be checked
against this list by the Sequencer once the Operation completes.

While executing, the Operation should call the
`~.Operation.is_shutdown()` method occasionally to query if the
Sequencer is asking the Operation to shutdown i.e. abort. If
True, the Operation should exit as quickly as is practical, ignoring
results; in this state, the sequence is being stopped and aborted, so
results are not important.

The Operation should save results using the
`~.Operation.save_result()` method, giving the name of the result and
its value. This name must match that specified in the station's
operations.json file, and the Sequencer will verify that all
expected results have been generated by an Operation or else mark
that Operation as failed.

An Operation should use the `~.Operation.checkout_tool()` method to
get direct access to a station tool, and should call
`~.Operation.return_tool()` when the tool is no longer needed, so that
other operations can use the tool. If the developer forgets to return
a tool, the Operation base class will return it at the end of the
operation's run, but developers should remember to return the tool as
soon as possible to make it available quickly to other Operations.

Before exiting, the Operation should call the
`~.Operation.set_status()` method with `.OperationState.COMPLETED` or
`.OperationState.ERROR`. If necessary, the Operation may call it with
`.OperationState.REQUEUE`` before completing its
execution, and the Operation will be requeued by the Sequencer to run
again at a later time.

Work Queue
----------
Storage events are not processed immediately when they are triggered. Since there are no needed
results from a store operation and the operation could be slow, the events are processed
asynchronously. When a storage event is triggered, each registered handler for the event is
placed into a queue to be processed later.

The queue is organized by data source so that, if applicable, multiple storage events from one
source can be processed all at once (especially useful when the source is a tool - only have to
checkout the tool once to process all of the data). The information stored in the queue is as
follows:

* Source - the source that will handle the event
* Event enumeration - which storage event caused this handler to be placed into the queue
* Handling method - the method that will process the event
* JSON formatted string of data - the data that will be processed for storage
* Timestamp of when data was added to queue - this represents the time of the storage event, in case actual storage doesn't take place until some time later


Storage Worker
--------------
The Storage Worker is a thread that will periodically process events in the work queue. It is
launched in the `initialize` method of DataStorage. Every 'write_period' seconds, the worker will
attempt to execute storage events for each data source. The configurable period of the worker
loop is set with the 'write_period' value when creating the DataStorage object.

If the source of a handler is a tool, the worker will check the tool out (otherwise it can process
the event directly). The worker will attempt loop through all outstanding data storage events for
that source, calling the handler method with the data. If a storage method raises an exception,
that object is placed back into the queue to be processed later (in the case that the tool is
offline or in use).


stationexec.sequencer.operation module
--------------------------------------

.. automodule:: stationexec.sequencer.operation
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.handlers module
-------------------------------------

.. automodule:: stationexec.sequencer.handlers
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.loop module
---------------------------------

.. automodule:: stationexec.sequencer.loop
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.opdata module
-----------------------------------

.. automodule:: stationexec.sequencer.opdata
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.operationstates module
--------------------------------------------

.. automodule:: stationexec.sequencer.operationstates
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.result module
-----------------------------------

.. automodule:: stationexec.sequencer.result
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.sequence module
-------------------------------------

.. automodule:: stationexec.sequencer.sequence
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.sequence_factory module
---------------------------------------------

.. automodule:: stationexec.sequencer.sequence_factory
    :members:
    :undoc-members:
    :show-inheritance:

stationexec.sequencer.utilities module
--------------------------------------

.. automodule:: stationexec.sequencer.utilities
    :members:
    :undoc-members:
    :show-inheritance:
