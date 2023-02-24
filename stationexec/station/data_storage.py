# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""

The DataStorage object serves as an abstraction layer for the storage and retrieval of data.

Sources
-------
Each event registration requires a source - an identifier that lets DataStorage know what is
handling the events. Sources for event handling (storage and retrieval) can be a) tools b)
anything else.

To specify a tool, register the handler when the tool object is created and use the tool_id as the
source. When an event triggers, DataStorage can check out this tool to handle the event to not
interfere with any other processes that may be needing that same tool

For all other sources (anything that is not a tool), set the source to None. This lets DataStorage
know that the handler method may be called at any time.

Storage
-------
The storage set of events refer to key times in stationexec operation where something occurs that
should be saved.

Events
^^^^^^
To register a handler for a storage event, call `register_for_storage_event` with a source
(defined above), the specific event (see the StorageEvents enum), and a method that will be
performing the action. Storage events can have an unlimited number of handlers. Registration is
only allowed before the storage worker is launched in `initialize`.

A storage event is triggered by a call to `trigger_storage_event` with the event enum and a dict
containing all data that could be material to the event in question. Storage event triggers will
come from stationexec when the appropriate event happens. The sections below on the Work Queue
and the Storage Worker describe in detail how these events are
processed.

Members of enum `StorageEvents`:

* ON_SEQUENCE_START
* ON_SEQUENCE_END
* ON_OPERATION_START
* ON_OPERATION_END
* ON_RESULT_STORE
* ON_DATA_STORE
* ON_REGISTER_STATION
* ON_UPDATE_STATION
* ON_LOG_DATA
* ON_MAINTENANCE_EVENT


Work Queue
^^^^^^^^^^
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
^^^^^^^^^^^^^^
The Storage Worker is a thread that will periodically process events in the work queue. It is
launched in the `initialize` method of DataStorage. Every 'write_period' seconds, the worker will
attempt to execute storage events for each data source. The configurable period of the worker
loop is set with the 'write_period' value when creating the DataStorage object.

If the source of a handler is a tool, the worker will check the tool out (otherwise it can process
the event directly). The worker will attempt loop through all outstanding data storage events for
that source, calling the handler method with the data. If a storage method raises an exception,
that object is placed back into the queue to be processed later (in the case that the tool is
offline or in use).

Retrieval
---------
The retrieve set of events refer to key times in stationexec operation where previously saved
data must be retrieved for analysis, viewing, or processing.

Events
^^^^^^
To register a handler for a retrieve event, call `register_for_retrieval_event` with a source
(defined above), the specific event (see the RetrievalEvents enum), and a method that will be
performing the action. Retrieve events can have only one handler. If multiple handlers register
for a storage event, they overwrite the previous event - only the last handler registered for an
event is used. Registration is only allowed before DataStorage `initialize` is called.

A retrieval event is triggered by a call to `trigger_retrieval_event` with the event enum and a
dict containing all data that could be material to the event in question. Retrieve event
triggers will come from stationexec when the data is needed.

Members of enum `RetrievalEvents`:

* GET_OPERATION_AVERAGE_DURATION
* GET_STATION_DATA
* GET_LOG_DATA
* GET_MAINTENANCE_DATA


How This Works in StationExec
-----------------------------
StationExec provides a default tool/set of tools that register for all storage and retrieval
events. Without configuration, this stores to and retrieves data from local SQLite database(s).
With configuration, this data can be stored to and retrieved from a local/remote MySQL database.

To extend the behavior by storing to secondary data stores, simply register additional storage
handlers for tools that handle your particular storage case (different schema, different
database, not a database, HTTP endpoint, text file, etc.)

The default solution can be removed with configurations to make way for a full custom solution.
View the 'Event Requirements' section below to ensure that you provide at least all of the
necessary handlers.

Event Requirements
------------------
There are two requirements for events on developers who are using DataStorage.

**First** - the following retrieve event(s) must always have a handler:

* GET_STATION_DATA

It does not matter if this is the default or a developer-provided handler.

**Second** - if a retrieve event is implemented, there are corresponding storage events that
become required in service of the retrieves. These must be handled by the same source that
handles the retrieves.

+--------------------------------+-------------------------+
| **Retrieve**                   | **Store**               |
+--------------------------------+-------------------------+
| GET_STATION_DATA               | ON_REGISTER_STATION     |
|                                | ON_UPDATE_STATION       |
+--------------------------------+-------------------------+
| GET_OPERATION_AVERAGE_DURATION | ON_OPERATION_START      |
|                                | ON_OPERATION_END        |
+--------------------------------+-------------------------+
| GET_LOG_DATA                   | ON_LOG_DATA             |
+--------------------------------+-------------------------+
| GET_MAINTENANCE_DATA           | ON_MAINTENANCE_EVENT    |
+--------------------------------+-------------------------+

These requirements are enforced in the `_handler_audit` method, which will raise an exception
with error messages describing which events are in violation of the rules.

"""

import os
import threading
import time
from functools import partial

import simplejson
from stationexec.logger import log
from stationexec.station.events import (
    _set_storage_callbacks,
    emit_event_non_blocking,
    ActionEvents,
    RetrievalEvents,
    StorageEvents,
    InfoEvents,
)
from stationexec.utilities.config import get_all_paths
from stationexec.utilities.exceptions import (
    ToolInUseException,
    ToolNotExistsException,
    ToolUnavailableException,
)
from stationexec.utilities.time import to_timestamp, to_datetime, get_utc_now

_STORAGE_FILE = "queue.json"


class StorageShutdown(Exception):
    # Time to shut the storage worker down
    pass


class DataStorage(object):
    def __init__(self, write_period=10):
        self._write_period = write_period

        self._storage_events = {}
        self._retrieval_events = {}  # type: dict(str, tuple)
        self._storage_queue = {}
        self._worker = None
        self._is_shutdown = False
        self._is_initialized = False

        self._checkout_tool_storage = None
        self._checkout_tool_retrieval = None
        self._return_tool_storage = None
        self._return_tool_retrieval = None

        self._cache_path = os.path.join(get_all_paths()["data_folder"], _STORAGE_FILE)
        # self._cache_path = _STORAGE_FILE

        # Initialize storage event lists to empty
        for event in list(StorageEvents):
            self._storage_events[event] = []
        # Retrieval events have single (or no) handlers - initialize to None
        for event in list(RetrievalEvents):
            self._retrieval_events[event] = None

        _set_storage_callbacks(
            self.register_event, self.unregister_event, self.trigger_event
        )

    def initialize(self):
        """ Make sure required events are covered, load old data, and start worker thread """
        if self._checkout_tool_storage is None or self._return_tool_storage is None:
            return Exception("Required tool handlers not set in DataStorage")

        # Ensure required handlers exist before starting
        self._handler_audit()

        # Check if there is any leftover data from previous runs
        self._load_queue_from_file()

        # Must wait to run this until the end of initializations, after all handlers
        # have been registered
        self._worker = threading.Thread(
            name="storage_worker", target=self._storage_worker
        )
        self._worker.start()

        self._is_initialized = True

    def set_tool_management(self, checkout_tool, return_tool):
        """ Set callbacks for managing tools - called after toolbox is enabled """
        if self._checkout_tool_storage is None:
            self._checkout_tool_storage = partial(checkout_tool, "datastorage:storage")
            self._checkout_tool_retrieval = partial(
                checkout_tool, "datastorage:retrieval"
            )
        if self._return_tool_storage is None:
            self._return_tool_storage = partial(return_tool, "datastorage:storage")
            self._return_tool_retrieval = partial(return_tool, "datastorage:retrieval")

    def shutdown(self):
        """ Cleanup """
        self._is_shutdown = True

    def _handler_audit(self):
        """
        Check that the events and event pairs necessary for operation of stationexec are handled
        :return: None
        """
        missing_required_handlers = []

        def check_requirement(retrieve):
            """ Check that required retrieve event has a defined handler """
            if self._retrieval_events[retrieve] is None:
                missing_required_handlers.append("- '{0}'".format(retrieve))

        def check_required_pair(retrieve, store):
            """
            Check that a defined retrieve function has the required storage event also covered
            :param RetrievalEvents retrieve:
            :param StorageEvents store:
            :return: None
            """
            ret = self._retrieval_events[retrieve]  # type: tuple
            if ret is not None:
                src, _evt, _meth = ret
                found_retrieve_tool = False
                for handler in self._storage_events[store]:
                    if handler[0] == src:
                        found_retrieve_tool = True
                if found_retrieve_tool is False:
                    missing_required_handlers.append(
                        "- '{0}' (Required by '{2}' from source '{1}')".format(
                            store, src, retrieve
                        )
                    )

        # Retrieve functionality that is required for operation
        check_requirement(RetrievalEvents.GET_STATION_DATA_LOCAL)
        
        # If a retrieve function is specified, the corresponding storage function
        # must be also (with the same source)
        # Station
        check_required_pair(
            RetrievalEvents.GET_STATION_DATA, StorageEvents.ON_REGISTER_STATION
        )
        check_required_pair(
            RetrievalEvents.GET_STATION_DATA, StorageEvents.ON_UPDATE_STATION
        )
        check_required_pair(
            RetrievalEvents.GET_STATION_DATA_LOCAL, StorageEvents.ON_REGISTER_STATION_LOCAL
        )
        # Sequence
        check_required_pair(
            RetrievalEvents.GET_OPERATION_AVERAGE_DURATION,
            StorageEvents.ON_OPERATION_START,
        )
        check_required_pair(
            RetrievalEvents.GET_OPERATION_AVERAGE_DURATION,
            StorageEvents.ON_OPERATION_END,
        )
        # Log
        check_required_pair(RetrievalEvents.GET_LOG_DATA, StorageEvents.ON_LOG_DATA)
        # Maintenance
        check_required_pair(
            RetrievalEvents.GET_MAINTENANCE_DATA, StorageEvents.ON_MAINTENANCE_EVENT
        )

        if len(missing_required_handlers) != 0:
            raise Exception(
                "Missing required data handlers:\n{0}".format(
                    "\n".join(missing_required_handlers)
                )
            )

    def register_event(self, source, event, method):
        if isinstance(event, StorageEvents):
            self._register_for_storage_event(source, event, method)
        elif isinstance(event, RetrievalEvents):
            self._register_for_retrieval_event(source, event, method)

    def unregister_event(self, source, event, method):
        if isinstance(event, StorageEvents):
            self._storage_events[event].remove((source, event, method))
        elif isinstance(event, RetrievalEvents):
            self._retrieval_events[event] = None

    def trigger_event(self, event, data):
        if isinstance(event, StorageEvents):
            return self._trigger_storage_event(event, data)
        elif isinstance(event, RetrievalEvents):
            return self._trigger_retrieval_event(event, data)
        else:
            return None

    def _register_for_storage_event(self, source, event, method):
        """
        Register a method to handle an event for data storage.

        :param str source: tool.tool_id for a tool or any string non-tool sources (will be ignored)
        :param StorageEvents event: identifier for the event that the method will handle
        :param method: handle to the method that will be called when the event fires
        :return:
        """
        assert isinstance(event, StorageEvents)
        log.debug(
            3,
            "Registering data storage handler {0}.{1}".format(source, method.__name__),
        )
        self._storage_events[event].append((source, event, method))

    def _register_for_retrieval_event(self, source, event, method):
        """
        Register a method to handle an event for data retrieval.

        Data retrieval events support 0 or 1 handlers. Registrations for an event beyond the first
        handler will overwrite the previous handler.

        :param str source: tool.tool_id for a tool or any string non-tool sources (will be ignored)
        :param StorageEvents event: identifier for the event that the method will handle
        :param method: handle to the method that will be called when the event fires
        :return:
        """
        assert isinstance(event, RetrievalEvents)
        if self._retrieval_events[event] is not None:
            log.debug(
                1,
                "Overwriting existing data retrieval handler for {0}. Changing from "
                "{1}.{2} to {3}.{4}".format(
                    event.name,
                    self._retrieval_events[event][0],
                    self._retrieval_events[event][2].__name__,
                    source,
                    method.__name__,
                ),
            )
        self._retrieval_events[event] = source, event, method

    def _trigger_storage_event(self, event, data):
        """
        Cause the specified storage event to fire. Event data is placed on to a queue and
        processed asynchronously by the worker thread.

        :param StorageEvents event: identifier for the event that will trigger
        :param dict data: all data that the handler may need to process the event
        :return: None
        """
        assert isinstance(event, StorageEvents)
        assert type(data) is dict
        for storage in self._storage_events[event]:
            source, evt, method = storage

            # Queues are organized by sources to streamline tool accesses
            if source not in self._storage_queue:
                self._storage_queue[source] = {}
            if method not in self._storage_queue[source]:
                self._storage_queue[source][method] = []

            # Place data and timestamp into write queue
            self._storage_queue[source][method].append(
                (source, evt, method, simplejson.dumps(data), get_utc_now())
            )

    def _trigger_retrieval_event(self, event, data):
        """
        Cause the specified retrieval event to fire, which calls the registered event handler
        (if it exists). Event is processed immediately and data is returned to the caller

        :param RetrievalEvents event: identifier for the event that will trigger
        :param dict data: all data that the handler may need to process the event
        :return: Data retrieved from the handler
        """
        assert isinstance(event, RetrievalEvents)
        assert type(data) is dict
        if event not in self._retrieval_events:
            return None

        ret = None
        retrieval = self._retrieval_events[event]  # type: tuple
        if retrieval is not None:
            tool_ref = None
            source, evt, method = retrieval
            data["source"] = source
            data["event"] = evt

            # If this source is a tool, check it out to prevent other processes from accessing it.
            # Since the event has a method tied to it, we will not use the tool object that we
            # checkout, but checking it out will lock it to this process for the duration.
            # Source = None indicates a non-tool based storage method and will not need a tool
            # checkout
            if source.startswith("tool."):
                # Source is a tool - checkout the tool to prevent other processes from using it
                # and allow all exceptions to bubble out
                _, tool_id = source.split(".", 1)
                if self._checkout_tool_retrieval is not None:
                    # TODO Increase robustness (wait longer? log failed attempts? show number of attempts,
                    #  who has the tool already, etc
                    tool_ref = self._checkout_tool_retry_exp(tool_id, 5)
                else:
                    return None

            try:
                ret = method(**data)
            except Exception as e:
                log.exception(
                    "Exception while processing retrieval method '{0}' for "
                    "event '{1}".format(evt, str(method)),
                    e,
                )

            # If a tool was checked out earlier, return it now
            if tool_ref is not None:
                try:
                    self._return_tool_retrieval(tool_ref)
                except Exception as e:
                    log.exception("Unable to return tool in trigger retrieval event", e)

            return ret

    def _checkout_tool_retry_exp(self, tool_id, num_retries):
        assert num_retries >= 0

        delays = [0.25 * (2 ** x) for x in range(num_retries)]

        for idx, n in enumerate(delays):
            try:
                return self._checkout_tool_retrieval(tool_id)
            except (ToolInUseException, ToolUnavailableException):
                if self._is_shutdown:
                    # Shutting down - return value is unimportant
                    return None
                if idx >= num_retries - 1:
                    raise
                time.sleep(n)

    def _load_queue_from_file(self):
        """
        Load queue data from file and populate storage_queue with data storage requests from
        previous runs
        :return: None
        """
        if os.path.exists(self._cache_path):
            # Print the size of the file loaded to the log to track in case it grows
            # rather than shrinks
            log.debug(
                3,
                "Loading previous data queue file - size: {0} bytes".format(
                    os.path.getsize(self._cache_path)
                ),
            )
            with open(self._cache_path, "r") as f:
                queue_data = f.readlines()
            # Read was successful - delete file
            os.remove(self._cache_path)
        else:
            log.debug(5, "No previous data queue file found to read from")
            return

        def rehydrate(chunk):
            """ Turn JSON string into valid queue data """
            obj = simplejson.loads(chunk)
            source = (
                None
                if (obj["source"] == 'null' or obj["source"] == 'None')
                else obj["source"]
            )
            event = StorageEvents[obj["event"]]

            method = None
            method_name = obj["method"]
            # Search through currently registered events for the same source as this object
            # and try to find a handler method with the same name as this one from the same
            # source. If found, assign that callback to this queue item
            for evt in self._storage_events[event]:
                if evt[0] == source and evt[2].__name__ == method_name:
                    method = evt[2]
            if method is None:
                raise Exception(
                    "Unable to find active method to assign to previous data queue "
                    "item. Cannot locate {0}.{1}".format(source, method_name)
                )

            data_blob = obj["data"]
            storage_time = to_datetime(obj["created"])
            return source, event, method, data_blob, storage_time

        for data in queue_data:
            try:
                queue_entry = rehydrate(data)
            except Exception as e:
                log.exception(
                    "Failed to load object from previous run storage queue", e
                )
                continue
            else:
                data_source = queue_entry[0]
                method = queue_entry[2]
                if data_source not in self._storage_queue:
                    self._storage_queue[data_source] = {}
                if method not in self._storage_queue[data_source]:
                    self._storage_queue[data_source][method] = []
                self._storage_queue[data_source][method].append(queue_entry)

    def _dump_queue_to_file(self):
        """
        Process items still remaining in storage queue and write them out to file for
        processing next time
        :return:
        """

        def dehydrate(chk):
            """ Turn queue data into JSON string """
            src, event, mthd, data, storage_time = chk
            obj = {
                "source": src,
                "event": event.name,
                "method": mthd.__name__,
                "data": data,
                "created": to_timestamp(storage_time),
            }
            return simplejson.dumps(obj)

        for source in self._storage_queue.keys():
            to_delete = []
            for method in self._storage_queue[source].keys():
                for chunk in self._storage_queue[source][method]:
                    with open(self._cache_path, "a") as f:
                        f.write("{0}\n".format(dehydrate(chunk)))
                to_delete.append((source, method))
            for del_source, del_method in to_delete:
                # Remove processed data from the queue
                del self._storage_queue[del_source][del_method]

    def _sleep(self):
        """ Sleep for looping with checks for shutdown signal to aid in quick shutdown """
        period = float(self._write_period) / 0.5
        for _idx in range(int(period)):
            if self._is_shutdown:
                raise StorageShutdown("Shutdown requested")
            time.sleep(0.5)

    def _storage_worker(self):
        """ Launched as a thread inside "initialize". Will run until self._is_shutdown is True """
        # from timeit import default_timer

        try:
            while not self._is_shutdown:
                did_write_data = False
                storage_sources = list(self._storage_queue.keys())
                for source in storage_sources:
                    if self._is_shutdown:
                        break

                    if len(self._storage_queue[source]) == 0:
                        # Queue is empty - no need to process
                        continue

                    try:
                        tool_ref = self._get_tool(source)
                    except (ToolInUseException, ToolUnavailableException):
                        # Tool cannot be reserved now - try again on the next loop iteration
                        log.debug(
                            4,
                            "Data storage source '{0}' is unavailable; will try "
                            "again later".format(source),
                        )
                        continue

                    # Source is now reserved (if applicable)
                    # Attempt to process all items in the queue for this source
                    methods = list(self._storage_queue[source].keys())
                    for method in methods:
                        if self._is_shutdown:
                            break

                        try:
                            stored_records = self._store_records(source, method)
                            did_write_data = True
                        except Exception as e:
                            # Something didn't work - exit and try again later
                            log.exception(
                                "Exception while processing data in storage worker", e
                            )
                            continue

                        records = self._storage_queue[source][method]

                        for record in stored_records:
                            records.remove(record)

                        if len(records) == 0:
                            del self._storage_queue[source][method]
                            continue

                    # If a tool was checked out earlier, return it now
                    self._ret_tool(tool_ref)

                # Writing finished for now - rest for a while
                if did_write_data:
                    emit_event_non_blocking(InfoEvents.STORAGE_COMPLETE, {})
                self._sleep()

        except StorageShutdown:
            # Shutdown received while sleeping - part of a clean shutdown
            pass
        except Exception as e:
            log.exception("Unexpected storage worker exception", e)
            emit_event_non_blocking(ActionEvents.SHUTDOWN, {})
        finally:
            # On exit, always save all outstanding data to be processed in the next session
            self._dump_queue_to_file()

    def _get_tool(self, source):
        # If this source is a tool, check it out to prevent other processes from
        # accessing it. Since the event has a method tied to it, we will not use the
        # tool object that we checkout, but checking it out will lock it to this
        # process for the duration. Source = None indicates a non-tool based storage
        # method and will not need a tool checkout
        tool_ref = None
        if source.startswith("tool."):
            # Source is a tool - checkout the tool to prevent other processes
            # from using it
            _, tool_id = source.split(".", 1)
            try:
                tool_ref = self._checkout_tool_storage(tool_id)
            except ToolNotExistsException:
                if self._is_shutdown:
                    # Tried to checkout a tool after toolbox shutdown - time to exit
                    raise StorageShutdown
                else:
                    # Toolbox doesn't have the tool we asked for
                    raise

        return tool_ref

    def _ret_tool(self, tool_ref):
        if tool_ref is not None:
            try:
                self._return_tool_storage(tool_ref)
            except Exception as e:
                log.exception("Unable to return tool in storage worker", e)

    def _store_records(self, source, method):
        """ Store all records that share the same source and call-back method (but perhaps different events) """
        formatted_records = {}
        stored_records = []

        for record in self._storage_queue[source][method]:
            _src, event, _method, json_data, storage_time = record
            if event not in formatted_records:
                formatted_records[event] = []

            data = simplejson.loads(json_data)
            data["created"] = storage_time
            data["_event"] = event
            data["_source"] = source

            formatted_records[event].append(data)
            stored_records.append(record)
        for evt in formatted_records.keys():
            method(data=formatted_records[evt], evt=evt)

        return stored_records

if __name__ == "__main__":

    def checkout_tool(source):
        print("Checking out tool '{0}'".format(source))
        return 'tool'

    def ret_tool(tool_obj):
        print("Returning tool '{0}'".format(tool_obj))

    def valid_worker(data):
        print("Working on {0}".format(data))
        return 1

    def invalid_worker(data):
        raise Exception("Sorry this doesn't work: {0}".format(data))

    db = DataStorage(3)

    db.register_event('tool_1', StorageEvents.ON_SEQUENCE_START, valid_worker)
    db.register_event('tool_2', StorageEvents.ON_SEQUENCE_START, valid_worker)
    db.register_event(None, StorageEvents.ON_SEQUENCE_START, valid_worker)
    db.register_event('tool_1', RetrievalEvents.GET_STATION_DATA, valid_worker)
    db.register_event('tool_2', RetrievalEvents.GET_STATION_DATA, valid_worker)
    db.register_event(None, RetrievalEvents.GET_STATION_DATA, valid_worker)

    db.initialize(checkout_tool, ret_tool)
    return_value = db.trigger_event(
        RetrievalEvents.GET_STATION_DATA, {"data": "Please get station data"}
    )
    db.trigger_event(
        StorageEvents.ON_UPDATE_STATION, {"data": "Please get station data"}
    )
    db.trigger_event(
        StorageEvents.ON_SEQUENCE_START, {"data": "Please get station data"}
    )

    time.sleep(4)
    db.shutdown()
