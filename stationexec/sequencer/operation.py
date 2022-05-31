# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
This class defines routines common to all sequence operations. An Operation
is a part of a Sequence of operations needed to perform a step in the building
of a device. The operations are all performed on one station.
"""

from stationexec.logger import log
from stationexec.sequencer.operationstates import OperationState
from stationexec.station.events import emit_event, InfoEvents
from stationexec.utilities.exceptions import AbortException


def require_tools(*tools):
    def decorator(cls):
        cls._required_tools = tools
        return cls

    return decorator


class Operation(object):
    """
    An Operation is the base class of all operations in a station's sequence of steps needed to
    perform a function, and it defines all the common, default routines.
    """
    _required_tools = []  # type: list

    def __init__(self, operation_id):
        """
        Create object.

        :param str operation_id: the name of the class, a unique internal id for referring to
            this operation
        """
        # When True, process should shut down quickly
        self._shutdown = False
        # Unique ID for this operation, matching the class name
        self._operation_id = operation_id
        # Run status of this operation
        self._status = OperationState.IDLE
        # dict of results generated
        self._results = {}

        # If running in n-up configuration, which 'n' is this operation (is None if not n-up)
        self.n_pos = None

        self._loop_iteration = None  # type: int
        self.runtimedata = None  # type: dict

    def get_id(self):
        """
        Get the unique id/class of this operation

        :return: the id
        :rtype: str
        """
        return self._operation_id

    def prepare(self):
        """
        Override this method to perform any operations necessary before running this operation.

        :return: `~.OperationState.ERROR`, `~.OperationState.COMPLETED`,
            or `~.OperationState.REQUEUE`.
        :rtype: `OperationState`
        """
        pass

    def operation_action(self):
        """
        Override this method with the actions to perform for this operation.

        If self.is_shutdown() becomes true, this method should cleanly exit as soon
        as possible.

        This method should save results by calling `self.save_result() <.save_result()>`. If the
        method does not create a result for every item in expected_results,
        then the operation will automatically fail.

        :return: `~.OperationState.COMPLETED`, `~.OperationState.ERROR`,
            or `~.OperationState.REQUEUE`
        :rtype: `.OperationState`
        """
        pass

    def run(self):
        """
        DO NOT OVERRIDE THIS METHOD!

        Called by the Sequencer to invoke this operation. Checks that all results were supplied.
        Frees any tool requested but not released.

        `.initialize()` must be called before calling this method.

        :return: `~.OperationState.COMPLETED`, `~.OperationState.ERROR`, `~.OperationState.REQUEUE`,
            or `~.OperationState.ABORTED`
        :rtype: `.OperationState`
        """
        # Reset for a new run
        self._shutdown = False

        log.debug(2, "running operation {0}".format(self.get_id()))
        self.set_status(OperationState.RUNNING)

        # Wrap it, in case user code is bad
        try:
            rc = self.operation_action()
        except AbortException:
            # Operation was asked to shut down while executing
            rc = OperationState.ABORTED
            self.save_result("_error_message", "Operation was asked to abort",
                             res_type='text/plain')
            log.debug(2, "Operation '{0}' completed aborting".format(self.get_id()))
        except Exception as e:
            rc = OperationState.ERROR
            self.save_result("_error_message",
                             "Operation had an exception ({0}): {1}"
                             .format(e.__class__.__name__, e), res_type='text/plain')
            log.exception("Operation '{0}' failed with exception".format(self.get_id()), e)

        if rc is None:
            rc = OperationState.COMPLETED
        self.set_status(rc)

    def shutdown(self):
        """
        Ask the Operation to shut down and stop running. How quickly it does
        so depends on the implementation.
        """
        log.debug(2, "'{0}' asked to shut down".format(self.get_id()))
        self._shutdown = True

    def is_shutdown(self):
        """ Returns True if this operation was asked to shutdown(). """
        return True if self._shutdown else False

    def cleanup(self):
        """
        Override this method to perform any cleanup actions once the
        sequence has stopped running. Returns nothing. Check `self.is_shutdown() <.is_shutdown>`
        to determine if `.shutdown()` was called. Check `self.get_status() <.get_status>` for
        the main return status.
        """
        pass

    def set_status(self, status):
        """
        Set the current status of this operation.

        :param OperationState status: the current status
        """
        self._status = status

    def get_status(self):
        """
        Return the current operation status.

        :return: operation's status
        :rtype: OperationState
        """
        return self._status

    def save_result(self, name, value, res_type="numeric", identifier=None, store=True, description=None):
        """
        Save a result from this operation.

        Optional named argument 'type' can specify a type for the value, which can override the
        expected type. Defaults to 'numeric' for results stored without pre-definition

        :param str name: the name of the value to store
        :param object value: the value data to store
        :param str res_type: optional type if not defined in json file
        :param str identifier: optional tag (like for a serial number)
        :param bool store: (default True) save result in db if true; save only for duration of sequence if false
            runtime stored values only
        :param str description: (default None) provide description for runtime stored value
        """
        if name is None:
            raise Exception("Attempting to store value with no name in operation '{0}'".format(self.get_id()))
        if value is None:
            raise Exception("Attempting to store invalid value of 'None' in operation '{0}'".format(self.get_id()))
        if name not in self._results:
            self._results[name] = {}
        self._results[name]["value"] = value
        self._results[name]["type"] = res_type
        self._results[name]["identifier"] = identifier
        self._results[name]["store"] = store
        self._results[name]["description"] = description
        self.ui_log("Saving Result '{0}'".format(name))

    def get_results(self):
        """
        Return a dictionary of the results from this operation, indexed by the result name.
        These results are only considered valid if the operation was run and completed
        without errors. This dictionary only contains names and a dictionary containing the
        raw data in the 'value' key, and an optional type in the 'type' key, but not the
        extended type information or value information from the Operations.json file.

        :return: operation results
        :rtype: dict(str, dict)
        """
        return self._results

    def get_runtime_data(self):
        return self.runtimedata.copy()

    def ui_log(self, message):
        """
        Write a message on the front page log

        :param message:
        """
        emit_event(InfoEvents.MESSAGE_UPDATE, {
            "source": "operation.{0}".format(self.get_id()),
            "message": message
        })

    def value_to_ui(self, target, value):
        """
        Update a value on the
        :param target:
        :param value:
        :return:
        """
        emit_event(InfoEvents.OBJECT_UPDATE, {
            "source": "operation.{0}".format(self.get_id()),
            "target": target,
            "value": value
        })

    def get_loop_iteration(self):
        """ If this is a node in a loop, return the current loop iteration count, else None """
        return self._loop_iteration
