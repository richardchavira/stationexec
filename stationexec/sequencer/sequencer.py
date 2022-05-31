# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
This class contains the `.Sequencer` implementation used to calculate and run a sequence
of `.Operation` on a `.Station`.
"""

import os
import signal
import threading
import time
from collections import deque
from typing import Optional

import simplejson
from stationexec.logger import log
from stationexec.sequencer.operationstates import OperationState
from stationexec.sequencer.sequence import Sequence
from stationexec.station.events import emit_event, InfoEvents, StorageEvents
from stationexec.utilities.shutdown import signal_list

_LOOP_WAIT_TIME_SEC = 0.5
_MINIMUM_REQUEUE_WAIT_SECONDS = 1.5


class Sequencer(object):
    """The Operation sequencer"""
    # Sequence timeouts
    _SEQUENCE_TIMEOUT_SECONDS = 3600
    _OPERATION_TIMEOUT_SECONDS = 600
    # Internal debug flag
    _debug = False  # type: bool
    # The thread handle
    _pmain = None  # type: threading.Thread
    # Active sequence object
    active_sequence = None  # type: Sequence
    # UUID for the station
    station_id = None

    def __init__(self, get_cfg):
        """
        Initialize the Sequencer.

        :param get_cfg:
        """
        self._SEQUENCE_TIMEOUT_SECONDS = get_cfg("_SEQUENCE_TIMEOUT_SECONDS", 3600)
        self._OPERATION_TIMEOUT_SECONDS = get_cfg("_OPERATION_TIMEOUT_SECONDS", 600)

        self._sequence_queue = deque()
        self._recent_sequences = deque(maxlen=10)

        self._debug = get_cfg("debug", False)
        # Max task parallelism on this station
        self.parallelism = get_cfg("threads", 10)

        # list of operation ids waiting to run, ordered as in sequences.json
        self._waiting = []
        # list of operation ids ready to run (all dependencies completed), in order found ready
        self._ready = []
        # list of running operation ids, in order they were run
        self._running = []
        # list of completed operation ids
        self._done = []

        # If true, Sequencer should stop any currently running operations, then remain ready
        self._stop_requested = False
        # If true, all threads should shut down and Sequencer should itself stop
        self._shutdown_requested = False
        # Internal flag: are we preparing to start a sequence? So we don't accept a 2nd request.
        self._starting = False
        # Internal flag: are we actively running a sequence?
        self._active = False
        # How many sequences have we run since booting up
        self.run_count = 0
        self._iteration = 0

    def _update_ui(self):
        """ Tell the UI that some status has changed in the `.Sequencer` """
        data = simplejson.dumps(self.active_sequence.get_status())
        emit_event(InfoEvents.SEQUENCE_UPDATE, {
            "source": "sequencer",
            "data": data
        })

    def get_status(self):
        if self.active_sequence is not None:
            return self.active_sequence.get_status()
        elif len(self._recent_sequences) > 0:
            return self._recent_sequences[-1].get_status()
        else:
            return {}

    def get_sequence_history(self):
        history = []
        if self.active_sequence is not None:
            history.append(self.active_sequence.get_status())
        for seq in self._recent_sequences:
            history.append(seq.get_status())
        return history

    def initialize(self):
        """
        Initialize the Sequencer by launching the execution thread that will

        :raise InvalidAttribute: if ``operations.json`` file has an error
        """
        log.info("Sequencer Initialization")

        # Remove main thread signal handlers before we make a launch the run
        disabled_sig_handler = {}
        for sig_id in signal_list():
            disabled_sig_handler[sig_id] = signal.getsignal(sig_id)
            signal.signal(sig_id, signal.SIG_DFL)

        self._pmain = threading.Thread(target=self._execution_thread, args=())
        self._pmain.daemon = True
        self._pmain.start()

        # Restore signal handlers on this, the main thread, on this,
        # the day my daughter is to be married
        for sig_id in disabled_sig_handler:
            signal.signal(sig_id, disabled_sig_handler[sig_id])

    def _execution_thread(self):
        """ Run a sequence of operations. """
        while not self._shutdown_requested:
            if not self._sequence_queue:
                time.sleep(_LOOP_WAIT_TIME_SEC)
                continue

            self.active_sequence = self._sequence_queue.popleft()
            try:
                self._execute()
            except Exception as e:
                log.exception("Exception in sequence execution", e)

    def _execute(self):
        self.active_sequence.sequence_starting()

        self._active = True
        self._starting = True
        self._shutdown_requested = False
        self._stop_requested = False
        self.run_count += 1

        # Emit message indicating start of sequence run
        status = self.active_sequence.get_status()
        status["station"] = self.station_id
        emit_event(StorageEvents.ON_SEQUENCE_START, status)
        emit_event(InfoEvents.SEQUENCE_STARTED, status)
        emit_event(InfoEvents.MESSAGE_UPDATE, {
            "source": "sequencer",
            "message": "Started running sequence: {0}".format(self.active_sequence.uuid)
        })

        log.info("Running sequence {0}, threads={1}, pid={2}"
                 .format(self.active_sequence.uuid, self.parallelism, os.getpid()))

        # Initialize all the operation state lists
        self._waiting = []
        self._ready = []
        self._running = []
        self._done = []

        # Wrap sequence execution in try/except to catch any unexpected exceptions
        # and still call cleanup methods at the end.
        try:
            # Initially, put all operations ids into the waiting list
            self._waiting.extend(self.active_sequence.get_operation_names(
                sort_by_priority=True))

            # Until all waiting and ready list are empty, find jobs with satisfied dependencies
            # and move them to the read list, and run jobs in the ready list up to the max
            # parallelism this station supports. Once run, move the operation to the done list.
            # If the operation requests it, leave the operation on the ready list and try
            # another, for cases of external data or unavailable tool.
            self._iteration = 0
            while self._ready or self._waiting or self._running:
                # Ensure sequence terminates if it exceeds max run time
                duration = self.active_sequence.get_duration_ms() / 1000.0
                if duration > self._SEQUENCE_TIMEOUT_SECONDS:
                    raise Exception("Sequencer timeout - sequence ran longer than {0} seconds"
                                    .format(self._SEQUENCE_TIMEOUT_SECONDS))

                time.sleep(_LOOP_WAIT_TIME_SEC)
                if self._shutdown_requested or self._stop_requested:
                    break

                self._iteration += 1

                self._find_operations_ready_to_run()
                self._run_ready_operations()
                self._handle_completed_operations()

                # Only ask for ui refresh once per iteration
                self._update_ui()
                log.debug(2, "QWaiting : {0}".format(
                    ", ".join(str(x) for x in self._waiting)))
                log.debug(2, "QReady   : {0}".format(
                    ", ".join(str(x) for x in self._ready)))
                log.debug(2, "QRunning : {0}".format(
                    ", ".join(str(x) for x in self._running)))
                log.debug(2, "QDone    : {0}".format(
                    ", ".join(str(x) for x in self._done)))

            if self._shutdown_requested or self._stop_requested:
                log.warning("Sequence aborted after {0} iterations".format(self._iteration))
            else:
                log.debug(2, "Sequence completed after {0} iterations".format(self._iteration))

        # End Sequence Run
        except Exception as e:
            log.exception("Uncaught exception in sequence", e)
            self.active_sequence.set_exit_reason(e)

        # Wrap cleanup code to ensure that any unexpected exceptions are cleaned up
        try:
            # Make sure nobody is left running, regardless of whether we exited the loop
            # cleanly, or were asked to shutdown now.
            attempts = 0
            max_requests_before_terminate = 10
            while len(self._running) > 0:
                inactive = self.active_sequence.shutdown_operations(
                    self._running, nice=attempts < max_requests_before_terminate)
                attempts += 1
                for operation_id in inactive:
                    log.debug(2, "Operation '{0}' has stopped".format(operation_id))
                    self._running.remove(operation_id)
                    self._operation_done(operation_id)
                time.sleep(_LOOP_WAIT_TIME_SEC)

            # Anyone not done is now marked as aborted.
            self.active_sequence.abort_if_not_complete_or_error(self._waiting + self._ready)

        # End Sequence Cleanup
        except Exception as e:
            log.exception("Uncaught exception in sequence cleanup", e)
            self.active_sequence.set_exit_reason(e)

        self._active = False
        self._starting = False
        self.active_sequence.sequence_ending()

        status = self.active_sequence.get_status()
        status["station"] = self.station_id,
        emit_event(StorageEvents.ON_SEQUENCE_END, status)
        emit_event(InfoEvents.SEQUENCE_FINISHED, status)
        emit_event(InfoEvents.MESSAGE_UPDATE, {
            "source": "sequencer",
            "message": "Finished running sequence: {0}".format(self.active_sequence.uuid)
        })

        self._update_ui()
        log.info("Sequence {0} done after {1:.2f}s, thread pid {2} finished".
                 format(self.active_sequence.uuid,
                        self.active_sequence.get_duration_ms() / 1000.0,
                        os.getpid()))

        self._recent_sequences.append(self.active_sequence)
        self.active_sequence = None

    def stop(self, reason, clear_queue=False):
        # type: (str, Optional[bool]) -> None
        """
        Stop any running sequence of operations.

        :param str reason: explanation of why the stop is happening
        :param bool clear_queue: [optional] if true, all sequences on the queue will be cleared
                                 while stopping the current sequence. Otherwise, the next
                                 sequence on the queue will run.
        """
        log.warning("Sequence stop requested: {0}".format(reason))

        if clear_queue:
            if len(self._sequence_queue) > 0:
                log.warning("'{0}' items cleared out of the sequence queue"
                            .format(len(self._sequence_queue)))
            self._sequence_queue = deque()

        self.active_sequence.set_exit_reason(reason)
        if self._active or self._starting:
            self._stop_requested = True

    def shutdown(self):
        """
        Stop sequencer cleanup resources
        """
        log.warning("Sequencer shutting down")

        # Clear the sequence queue
        self._sequence_queue = deque()

        if self._active or self._starting:
            self._stop_requested = True
        self._shutdown_requested = True

        self._pmain.join()

    def run(self, sequence_object):
        """
        Start a `.Thread` to run the loaded sequence from the beginning. Call `.stop()` to stop
        the sequence early.

        :param Sequence sequence_object:
        """
        # TODO Have an endpoint to view the queue (if more than 1 item in queue)
        # TODO what about viewing a sequence? Now that there is no standard always loaded but a
        #  queue, can we have a 'set-active-sequence' or a 'view-sequence' method so that the
        #  sequencer get status command will return drawable data

        if self._shutdown_requested:
            log.error("Cannot start Sequencer since in shutdown mode")
            return

        position_in_queue = len(self._sequence_queue) + 1
        self._sequence_queue.append(sequence_object)
        return position_in_queue

    def set_active_sequence(self, sequence_object):
        """
        On load, set the default sequence as active to show the graphic.
        On start, another sequence will be loaded into the queue and set as active

        Intended to only be called at program load
        """
        if not self._active:
            self.active_sequence = sequence_object

    def _find_operations_ready_to_run(self):
        """
        Find any operations that can now be run and move them to the ready queue.

        :return: True if UI should be refreshed
        :rtype: bool
        """
        for operation_id in list(self._waiting):
            if self.active_sequence.all_dependencies_completed(operation_id, self._done):
                log.debug(2, "Moving operation {0} to ready queue on iteration {1}".
                          format(operation_id, self._iteration))
                self._ready.append(operation_id)
                self._waiting.remove(operation_id)

    def _run_ready_operations(self):
        """
        Determine if there are operations we can run because they are in the ready
        queue and we are not yet running the maximum number of processes. If an operation
        was requeued, wait some small amount of time before trying again to avoid
        needlessly executing prepare() code.

        Call the Operation's prepare() method before executing the main body.

        :return: True if UI should be refreshed
        :rtype: bool
        """
        found_runnable = True

        # Process loops before running
        loop_ops = self.active_sequence.pre_run_check_loop_conditions(self._ready)
        if loop_ops:
            # If pre-condition loop is finished, move all loop member operations
            #  to the done queue (leaving status information intact for all)
            for member_op_id in loop_ops:
                self._done.append(member_op_id)
                if member_op_id in self._ready:
                    self._ready.remove(member_op_id)
                if member_op_id in self._waiting:
                    self._waiting.remove(member_op_id)

        # keep trying while we found one, and we have not exceeded parallelism
        while len(self._running) < self.parallelism and found_runnable:
            if self._shutdown_requested or self._stop_requested:
                break

            found_runnable = False
            for operation_id in self.active_sequence.sort_list_by_priority(self._ready):
                if len(self._running) >= self.parallelism:
                    break

                if self._shutdown_requested or self._stop_requested:
                    break

                if not self.active_sequence.has_requeue_time_elapsed(operation_id,
                                                                     _MINIMUM_REQUEUE_WAIT_SECONDS):
                    continue

                if not self.active_sequence.evaluate_conditional_operation(operation_id):
                    # Condition returned false - do not run the operation
                    self._done.append(operation_id)
                    self._ready.remove(operation_id)
                    # Set the operation status as skipped and log to database
                    self.active_sequence.set_operation_status(operation_id, OperationState.SKIPPED)
                    status = self.active_sequence.get_op_status(operation_id)
                    emit_event(StorageEvents.ON_OPERATION_START, status)
                    # Alert UI that operation was skipped due to condition
                    emit_event(InfoEvents.MESSAGE_UPDATE, {
                        "source": "sequencer",
                        "message": "Skipped conditional operation: {0}".format(operation_id)
                    })
                    # Cleanup operation
                    status = self.active_sequence.get_op_status(operation_id)
                    emit_event(StorageEvents.ON_OPERATION_END, status)
                    continue

                # Run prepare for this operation, check if it asks for requeue or has an error.
                log.debug(2, "Preparing operation {0} with priority {2} on iteration {1}"
                          .format(operation_id, self._iteration,
                                  self.active_sequence.get_op_priority(operation_id)))
                try:
                    prc = self.active_sequence.prepare_op(operation_id)
                except Exception as e:
                    log.warning("exception while preparing operation {0}: {1}".format(
                        operation_id, str(e)))
                    self.stop("exception while preparing operation {0}: {1}".format(
                        operation_id, str(e)))
                    break

                if prc == OperationState.REQUEUE:
                    log.debug(3, "RE-QUEUING operation '{0}' on iteration {1}".format(
                        operation_id, self._iteration))
                    continue
                if prc == OperationState.ERROR:
                    log.debug(3, "Operation '{0}' FAILED to prepare on iteration {1}".
                              format(operation_id, self._iteration))
                    self.stop("Operation '{0}' FAILED to prepare on iteration {1}".
                              format(operation_id, self._iteration))
                    break

                log.debug(2, "Running operation '{0}' with priority {2} on iteration {1}".
                          format(operation_id, self._iteration,
                                 self.active_sequence.get_op_priority(operation_id)))

                self._running.append(operation_id)
                self._ready.remove(operation_id)
                found_runnable = True

                op_info = self.active_sequence.get_op_status(operation_id)
                emit_event(StorageEvents.ON_OPERATION_START, op_info)

                self.active_sequence.launch_op(operation_id)

    def _handle_completed_operations(self):
        """
        Determine if any running operations are now completed. For still running operations.
        check if a UI refresh is warranted

        :return: True if UI needs refresh
        :rtype: bool
        """
        # copy the list, because we're changing it in the loop
        for operation_id in list(self._running):
            if self.active_sequence.is_op_alive(operation_id):
                # Operation timeout - kill operation if it has been running too long
                duration = self.active_sequence.get_op_duration_ms(operation_id) / 1000.0
                if duration > self._OPERATION_TIMEOUT_SECONDS:
                    self.active_sequence.shutdown_operations([operation_id], nice=True)
            else:
                # Only non-alive processes get to here
                self._running.remove(operation_id)

                # Cleanup and store results
                try:
                    operation_rc = self._operation_done(operation_id)
                except Exception as e:
                    log.warning("exception while finishing operation '{0}': {1}".
                                format(operation_id, str(e)))
                    self.stop("exception while finishing operation '{0}': {1}".
                              format(operation_id, str(e)))
                    continue

                if operation_rc is OperationState.COMPLETED:
                    self._done.append(operation_id)
                    log.debug(3, "COMPLETED: '{0}' on iteration {1}".format(
                        operation_id, str(self._iteration)))

                    # Process loops after run
                    loop_ops = self.active_sequence.post_run_check_loop_conditions(self._done)
                    if loop_ops:
                        # If post-condition check passes, move all loop member operations
                        #  to the waiting queue
                        for member_op_id in loop_ops:
                            self._waiting.append(member_op_id)
                            if member_op_id in self._done:
                                self._done.remove(member_op_id)

                elif operation_rc is OperationState.REQUEUE:
                    self._waiting.append(operation_id)
                    log.debug(3, "REQUEUE: {0} on iteration {1}".format(
                        operation_id, self._iteration))
                elif operation_rc is OperationState.ERROR:
                    log.warning("OPERATION ERROR: {0} on iteration {1}".format(
                        operation_id, self._iteration))
                    self.stop("OPERATION ERROR: {0} on iteration {1}".format(
                        operation_id, self._iteration))
                else:
                    log.error("UNKNOWN rc {0} from operation {1} on iteration {2}".
                              format(operation_rc, operation_id, self._iteration))
                    self.stop("UNKNOWN rc {0} from operation {1} on iteration {2}".
                              format(operation_rc, operation_id, self._iteration))

    def _operation_done(self, operation_id):
        # Cleanup
        try:
            self.active_sequence.cleanup_op(operation_id)
        except Exception as e:
            emit_event(InfoEvents.MESSAGE_UPDATE, {
                "source": "sequencer",
                "message": "Exception while finishing operation '{0}': {1}".format(operation_id, e)
            })
            raise e

        # Store results in database
        results = self.active_sequence.get_op_result_data(operation_id)
        for result in results:
            result["operation"] = self.active_sequence.get_op_uuid(operation_id)
            emit_event(StorageEvents.ON_RESULT_STORE, result)
        storage_data = self.active_sequence.get_op_storage_data(operation_id)
        for data in storage_data:
            data["operation"] = self.active_sequence.get_op_uuid(operation_id)
            emit_event(StorageEvents.ON_DATA_STORE, data)

        # Notify that operation has completed execution
        status = self.active_sequence.get_op_status(operation_id)
        emit_event(StorageEvents.ON_OPERATION_END, status)

        # Stop if operation has any results that failed and is configured to stop (will continue by default)
        if not status["passing"]:
            if status["info"]["abort_on_result_failure"]:
                self.stop("RESULT FAILURE in '{0}' - configured to stop on failure".format(operation_id))

        # Return run status of operation
        return self.active_sequence.get_op_run_status(operation_id)

    def is_active(self):
        return self._active
