# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import time
from threading import Thread
from enum import IntEnum

from stationexec.logger import log
from stationexec.sequencer.operationstates import OperationState
from stationexec.sequencer.result import Result
from stationexec.sequencer.utilities import evaluate_conditional, flatten_2d_list, named_method_on_list, \
    parse_conditional_reference, parse_data_reference, unique_list
from stationexec.utilities.exceptions import AbortException, MissingResult, ToolUnavailableException, \
    ToolInUseException
from stationexec.utilities.uuidstr import get_uuid
from stationexec.utilities.error_codes import ErrorCode

from stationexec.station.events import emit_event, register_for_event, clear_event_subscribers, InfoEvents, StorageEvents

class OpData(object):
    def __init__(self, op_info, system_configs, tool_checkout, report_error, runtimedata=None,
                 n_pos=0, n_up=1, n_up_operations=None):
        self._report_error = report_error
        self.uuid = get_uuid()

        self.is_n_up = op_info.get("n_up", False) and n_up > 1
        self.n_pos = n_pos
        if self.is_n_up:
            self.id = "{0}__{1}".format(op_info.get("operation"), n_pos)
        else:
            self.id = op_info.get("operation")

        self.description = op_info.get("description", self.id)
        self.checkout_tool, self.return_tool = tool_checkout

        self.dependencies = None
        self._external_data = []
        self.abort_on_result_failure = op_info.get("abort_on_result_failure", False)

        if n_up_operations is None:
            n_up_operations = []

        # Conditional run data
        self.operand1 = None
        self.operand2 = None
        self.operand3 = None
        self.operator = None
        self.is_conditional = "condition" in op_info

        # Object specific data
        self._object = None
        self.priority = 5
        self.process = None
        self.thread_id = None
        self.message = None
        self.runtimedata = runtimedata
        self.start_time = 0
        self.end_time = 0
        self.avg_duration = 1
        self.tool_wait_time = 0
        self.requeue_time = None
        self._checked_out_tools = []
        self._results_passed = False

        self._results = {}

        self._system_configs = system_configs

        # Setup conditional execution for this operation if defined
        if self.is_conditional:
            try:
                self.operator, op1, op2, op3 = parse_conditional_reference(op_info.get("condition"),
                                                                           system_configs)
            except KeyError as e:
                self._report_error(
                    "Operation '{0}' conditional missing _config data: \
                    key error {1}".format(self.id, e))
            else:
                self.operand1 = op1["value"]
                self.operand2 = op2["value"]
                self.operand3 = op3["value"]
                self._external_data.append(op1)
                self._external_data.append(op2)
                self._external_data.append(op3)

        if not isinstance(op_info.get("parameters", {}), dict):
            self._report_error(
                "Operation '{0}' parameters definitions must be a dict of items".format(self.id))
        else:
            for key, value in dict(op_info.get("parameters", {})).items():
                try:
                    ref = parse_data_reference(key, value, system_configs)
                except KeyError as e:
                    self._report_error(
                        "Operation '{0}' missing _config data assigned to '{1}': \
                            key error {2}".format(self.id, key, e))
                else:
                    self._external_data.append(ref)

        # Create placeholders for all pre-configured results/data storage items
        result_dependencies = []
        n_pos = None if not self.is_n_up else n_pos
        if not isinstance(op_info.get("results", []), list):
            self._report_error(
                "Operation '{0}' results definitions must be a list/array of items".format(self.id))
        else:
            for result in list(op_info.get("results", [])):
                self._results[result["id"]] = Result(result, self._report_error,
                                                     description=result.get("description"),
                                                     parent_operation=self.id,
                                                     system_configs=system_configs,
                                                     n_pos=n_pos, n_up=n_up,
                                                     n_up_operations=n_up_operations)
                result_dependencies.extend(self._results[result["id"]].dependencies)

        # Make adjustments to dependencies and external data based on n_up configuration
        if not isinstance(op_info.get("follows", []), list):
            self._report_error(
                "Operation '{0}' follows definitions must be a list/array of items".format(self.id))
            self.dependencies = []
            return
        flow_dependencies = list(op_info.get("follows", []))
        if n_up > 1:
            for opid in n_up_operations:
                if opid in flow_dependencies:
                    flow_dependencies.remove(opid)
                    if self.is_n_up:
                        # If this operation is n_up, use the same n_up tag
                        flow_dependencies.append("{0}__{1}".format(opid, self.id.split("__")[1]))
                    else:
                        # Add all of the n_up operation instances to the dependencies
                        for n in range(n_up):
                            flow_dependencies.append("{0}__{1}".format(opid, n))

            to_remove = []
            for idx, data in enumerate(self._external_data):
                if data["source"] in n_up_operations:
                    to_remove.append(idx)
                    if self.is_n_up:
                        # If this operation is n_up, use the same n_up tag
                        new_data = dict(data)
                        new_data["source"] = "{0}__{1}".format(data["source"],
                                                               self.id.split("__")[1])
                        self._external_data.append(new_data)
                    else:
                        # Single operation depends on data from an n_up operation - no indication
                        # given which one to use
                        self._report_error("Standard operation referencing data in an n_up "
                                           "operation")
            for idx in to_remove:
                del self._external_data[idx]
        else:
            # Not in n_up mode - Clean up operation references in case there is reference to a
            # specific n_up operation name
            flow_dependencies = [op.split("__")[0] for op in flow_dependencies]
            for key in self._external_data:
                if key["source"] not in ["_config", "_constant"]:
                    key["source"] = key["source"].split("__")[0]
        # End n_up configuration

        # Calculate dependencies for this operation at this time
        data_dependencies = [key["source"] for key in self._external_data
                             if key["source"] not in ["_config", "_constant"]]
        self.dependencies = unique_list(flow_dependencies + data_dependencies + result_dependencies)

        # error code event callback
        #if not check_registered_event(self.id, InfoEvents.PASS_ERROR_CODE, self._pass_error_code):  # register here to have a callback for each operation
        clear_event_subscribers(self.id, InfoEvents.PASS_ERROR_CODE)  # register here to have a callback for each operation
        register_for_event(self.id, InfoEvents.PASS_ERROR_CODE, self._pass_error_code)  # register here to have a callback for each operation

    def _status_string(self):
        return "<OpData id='{0}' priority='{1}'>".format(self.id, self.priority)

    def __str__(self):
        return self._status_string()

    def __repr__(self):
        return self._status_string()

    # ---------- Internal -----------

    def initialize(self, operation_code):
        try:
            class_name = self.id.split("__")[0]
            self._object = getattr(operation_code, class_name)(self.id)
        except Exception as e:
            raise Exception("Unable to create operation object '{0}': {1}"
                            .format(self.id, e))

    def refresh(self):
        self.uuid = get_uuid()
        self.process = None
        self.thread_id = None
        self.message = None
        self.start_time = 0
        self.end_time = 0
        self.tool_wait_time = 0
        self.requeue_time = None
        self._checked_out_tools = []

        self.set_run_status(OperationState.IDLE)
        self._object._results = {}

        self._for_all_results("refresh")

    def evaluate(self, storage_cache):
        if self.is_conditional:
            self.update_external_data(storage_cache)
            self.update_object_attributes()
            conditionals_valid = True
            # Ensure that the conditional values are valid for comparison - int, float, bool
            for op, op_name in zip([self.operand1, self.operand2, self.operand3],
                                   ["operand1", "operand2", "operand3"]):
                if op is None:
                    continue
                if type(op) not in [int, float, bool]:
                    conditionals_valid = False
                    log.error("Unsupported operand type in conditional operation {0}: '{1}' '{2}'"
                              .format(self.id, op_name, type(op)))
            if conditionals_valid:
                return evaluate_conditional(self.operator, self.operand1, self.operand2,
                                            self.operand3)
            else:
                return False
        else:
            return True

    def get_status(self):
        return {
            "uuid": self.uuid,
            "opid": self.id,
            "name": self.id.split("__")[0],
            "description": self.description,
            "message": self.message,
            "passing": self._results_passed,
            "avgduration": self.get_avg_duration(),
            "starttime": self.start_time,
            "duration_ms": self.get_duration_ms(),
            "waittime_ms": int(self.tool_wait_time * 1000),
            "exitcode": self.get_run_status(True).value,
            "priority": self.priority,
            "conditional": {} if not self.is_conditional else {
                "operator": self.operator,
                "operand1": self.operand1,
                "operand2": self.operand2,
                "operand3": self.operand3
            },
            "dependencies": self.dependencies,
            "results": self._for_all_results("get_status"),
            "info": {
                "n_up": self.is_n_up,
                "n_pos": None if not self.is_n_up else self.id.split("__")[1],
                "abort_on_result_failure": self.abort_on_result_failure
            }
        }

    def process_is_alive(self):
        if self.process is not None:
            return self.process.is_alive()
        else:
            return False

    def set_priority(self, priority):
        self.priority = priority

    def get_priority(self):
        return self.priority

    def set_runtime_data(self, runtimedata):
        self.runtimedata = runtimedata

    def get_name(self):
        return self.id

    def get_is_n_up(self):
        return self.is_n_up

    def get_avg_duration(self):
        return self.avg_duration

    def set_avg_duration(self, durations):
        """
        Takes list of tuples (opid, duration) and loops to find an opid that matches self.id
        Assign self.avg_duration to that value if it exists. 1 otherwise
        """
        self.avg_duration = 1.0
        for op, duration in durations:
            if self.id.startswith(op):
                self.avg_duration = max(duration, 1.0)
                return

    def get_dependency_list(self):
        return list(self.dependencies)

    def get_external_data(self):
        public_external_data = flatten_2d_list(self._for_all_results("get_external_data"))
        for key in self._external_data:
            if key["source"] not in ["_config", "_constant"]:
                public_external_data.append((key["source"], key["external_key"]))
        return public_external_data

    def get_duration_ms(self):
        """ Calculate the duration of the operation """
        if self.start_time == 0:
            # Operation has not started yet
            return 0
        elif self.end_time == 0:
            # Operation is still running
            return int((time.time() - self.start_time) * 1000)
        else:
            # Operation has completed
            return int((self.end_time - self.start_time - self.tool_wait_time) * 1000)

    def update_external_data(self, storage_cache):
        self._for_all_results("update_external_data", storage_cache)

        for item in self._external_data:
            if item["source"] in storage_cache:
                item["value"] = storage_cache[item["source"]].get(item["external_key"])

    # ---------- Operation Object -----------

    def set_requeue(self):
        self.set_run_status(OperationState.REQUEUE)
        self.requeue_time = time.time()

    def set_error(self, message):
        self.set_run_status(OperationState.ERROR)
        self.message = message

    def prepare(self, storage_cache):
        self.set_run_status(OperationState.IDLE)

        self.set_object_attribute("runtimedata", self.runtimedata)
        self.update_external_data(storage_cache)
        self.update_object_attributes()

        # Checkout required tools for operation
        tools = self.get_object_tools()
        successful_checkout = True
        for tool in tools:
            try:
                self._checked_out_tools.append(self.checkout_tool(self.id, tool))
            except (ToolUnavailableException, ToolInUseException):
                successful_checkout = False
        if not successful_checkout:
            self.return_active_tools()
            self.set_run_status(OperationState.WAITING_ON_TOOL)
            self.requeue_time = time.time()
            return OperationState.REQUEUE

        # Make the tool objects available in the operation object
        # Accessible as self.<tool_name>.<method>
        for tool, obj in zip(tools, self._checked_out_tools):
            self.set_object_attribute(tool, obj)

        try:
            prc = self._object.prepare()
        except Exception as e:
            self.set_error("Exception '{0}' during prepare".format(e))
            raise

        if not prc:
            prc = OperationState.COMPLETED

        if prc == OperationState.REQUEUE:
            self.set_requeue()
        if prc == OperationState.ERROR:
            self.set_error("prepare() reported ERROR")

        if prc != OperationState.COMPLETED:
            # If anything went wrong in cleanup or there is a requeue request
            # return all tools
            self.return_active_tools()

        return prc

    def launch(self):
        self.message = None
        self.set_run_status(OperationState.RUNNING)
        self.process = Thread(name=self.id,
                              target=self._object.run)
        self.start_time = time.time()
        self.process.start()
        self.thread_id = self.process.ident

    def cleanup(self):
        if self.process is not None:
            self.process.join()
            self.process = None
        self.end_time = time.time()

        try:
            self._object.cleanup()
        except Exception as e:
            self.set_error("Exception '{0}' during cleanup".format(e))
            raise

        self.return_active_tools()

        prc = self.get_run_status()

        if not prc:
            prc = OperationState.COMPLETED

        if prc == OperationState.REQUEUE:
            self.set_requeue()
        if prc == OperationState.ERROR:
            self.set_error("Operation run ERROR")

        self._process_results()

    def shutdown(self, nice=True):
        if self._object is not None and self.thread_id is not None:
            if nice:
                self._object.shutdown()
            else:
                import ctypes
                log.info("Terminating process operation '{0}', thread id '{1}'".format(self.id, self.thread_id))
                # Attempt to create an AbortException in the thread itself, which
                # should tell the thread to exit.
                # http://www.aleax.it/Python/os03_threads_interrupt.pdf
                # http://tomerfiliba.com/recipes/Thread2/
                res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(self.thread_id),
                                                                 ctypes.py_object(AbortException))
                if res > 1:  # If return value > 1, undo call, since one already waiting
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(self.thread_id, 0)

    def return_active_tools(self):
        for tool in self._checked_out_tools:
            try:
                self.return_tool(self.id, tool)
            except Exception:
                # Just return the tools any way possible - do not care about exceptions
                pass
        self._checked_out_tools = []

    def get_object_tools(self):
        """
        Check if the object requires any tools for use and return the list if it exists

        :return: List of tools required by the operation object (empty list if none)
        :rtype: list
        """
        try:
            tools = self._object._required_tools
        except AttributeError:
            tools = []
        return tools

    def get_run_status(self, check_passing=False):
        """ Return the current operation object run status """
        exit_status = self._object.get_status()
        if check_passing:
            # Only check for a result failure when getting status as this
            # check isn't important in sequence
            if self._results_passed is False and exit_status == OperationState.COMPLETED:
                # If code is 100 (operation completed) but it did not pass (passing == 0)
                #  then one or more of the results failed - results failure code is 140
                exit_status = OperationState.RESULTFAILURE
        return exit_status

    def set_run_status(self, status):
        """ Update the operation object run status (IDLE, ABORTED, etc) """
        self._object.set_status(status)

    def set_loop_iteration(self, iteration):
        """ Update the loop iteration the operation is in """
        self.set_object_attribute("_loop_iteration", iteration)

    def store_error_code(self, error_code: ErrorCode):
        self._object.store_error_code(error_code)
    
    def _pass_error_code(self, source, **kwargs):
        if source == self.id:
            error_code = kwargs.get("error_code")
            error_code["operation"] = self.uuid
            emit_event(StorageEvents.ON_ERROR_CODE, error_code)
            log.debug(5, "Operation '{0}' storing error code: '{1}'".format(self.id, error_code) )
            
            failure_code = error_code.get('error_code')
            if failure_code:
                # check if codes are IntEnum or int
                if isinstance(failure_code, IntEnum):
                    failure_code = failure_code.name
                
                component_code = error_code.get('component_code')
                if isinstance(component_code, IntEnum):
                    component_code = component_code.name
                
                message = (
                    f"ERROR: {failure_code}, "
                    f"COMPONENT: {component_code}, "
                    f"DEBUG MESSAGE: {error_code.get('debug_message')}"
                )
                
                emit_event(
                    InfoEvents.ALERT_UPDATE,
                    {
                        "source": f'operation.{source}',
                        "message": message
                    }
                )

    def update_object_attributes(self):
        # Set n-up position of operation if operation is n-up
        if self.is_n_up:
            self.set_object_attribute("n_pos", self.n_pos)

        # Set the storage cache data parameters into the operation
        for val in self._external_data:
            key = val["local_key"]
            value = val["value"]
            if key.startswith("_data::"):
                key = key.split("::", 1)[1]
                setattr(self, key, value)
            else:
                self.set_object_attribute(key, value)

    def set_object_attribute(self, key, value):
        """
        Set an attribute in the operation object for easy access during a test

        Members of the operation object are protected against overwriting

        :param key:
        :param value:
        """
        if self._object is None:
            raise Exception("Sequence operation object not yet created")

        if key in ["_results", "_shutdown", "_status", "cleanup", "get_id", "get_results",
                   "get_status", "is_shutdown", "operation_action", "prepare", "run",
                   "save_result", "set_status", "shutdown", "ui_log"] or key.startswith("__"):
            raise Exception("Attempting to set protected object attribute: {0}".format(key))

        setattr(self._object, key, value)

    # ---------- Results -----------

    def _process_results(self):
        """ """
        expected_results = self.get_result_names()

        # Get results from object
        results = self._object.get_results()
        saved_results = results.keys()
        for name, result in results.items():
            if name in expected_results:
                self._results[name].store_result(result)
            else:
                result["id"] = name
                self._results[name] = Result(result, self._report_error,
                                             parent_operation=self.id,
                                             system_configs=self._system_configs)
                self._results[name].store_result(result)

        missing_results = []
        for name in expected_results:
            if name not in saved_results:
                missing_results.append(name)
        if len(missing_results) != 0:
            raise MissingResult("Required result(s) not saved in not saved in operation '{0}': "
                            "{1}".format(self.id, ", ".join(missing_results)), missing_results)

    def get_result_values(self):
        return self._for_all_results("get_value")

    def get_result_data(self):
        return [result.get_status() for result in self._results.values() if result.is_result]

    def get_storage_data(self):
        return [result.get_status() for result in self._results.values()
                if not result.is_result and result.do_store]

    def get_result_names(self):
        """ Return the names of all of the known results """
        return self._for_all_results("get_name")

    def did_pass(self, storage_cache, pass_skipped_conditional=True):
        if pass_skipped_conditional:
            # if a conditional operation whose condition evaluates to False
            # (operation to be skipped) then pass operation
            if self.is_conditional and not self.evaluate(storage_cache):
                self._results_passed = True
                return True

        passing = []
        for _result, res_obj in self._results.items():
            if res_obj.is_result:
                # Only check for passing values of true results (all non-results return True for
                # passing, which is not interesting here
                passing.append(res_obj.did_pass(storage_cache))
        if len(passing) == 0:
            # If there are no true results for this operation, regardless of whether the
            # operation ran or not, count it as a pass for the sequencer
            self._results_passed = True
            return True
        else:
            # This operation passed if there are no failing results AND if the operation completed
            run_status = self.get_run_status()
            self._results_passed = ((False not in passing)
                                    and (run_status == OperationState.COMPLETED))
            return self._results_passed

    def _for_all_results(self, method, *args):
        return named_method_on_list(self._results.values(), method, *args)
