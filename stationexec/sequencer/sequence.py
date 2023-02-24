# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import time
from collections import defaultdict
from enum import Enum
from uuid import UUID

from stationexec.sequencer.loop import Loop
from stationexec.sequencer.opdata import OpData
from stationexec.sequencer.operationstates import OperationState
from stationexec.sequencer.utilities import (
    flatten_2d_list,
    find_graph_entry_exit,
    graph_to_path_matrix,
    named_method_on_list,
    reduce_graph,
    SequenceLoop,
    unique_list,
)
from stationexec.utilities.error_codes import ErrorCode
from stationexec.utilities.uuidstr import get_uuid
from stationexec.utilities.exceptions import MissingResult
from stationexec.utilities.library_info import get_installed_library_versions
from stationexec.logger import log
from stationexec.logger.logger import Logger
from stationexec.station.events import emit_event, InfoEvents

class SequenceStatus(Enum):
    IDLE = 0
    RUNNING = 1
    COMPLETED = 2
    ABORTED = 3


class Sequence(object):
    def __init__(
        self,
        op_config_data,
        tool_checkout,
        system_configs,
        n_up=1,
        avg_operation_runtimes=None,
        runtimedata=None,
    ):
        self.uuid = get_uuid()  # type: UUID
        self.is_initialized = False
        self.version = "0.0"

        self._tool_checkout_methods = tool_checkout
        self._system_configs = system_configs
        self._runtimedata = runtimedata
        self.avg_runtimes = (
            avg_operation_runtimes if avg_operation_runtimes is not None else {}
        )
        self._n_up = n_up if n_up >= 1 else 1
        self._operations_matrix = None
        self._running_status = SequenceStatus.IDLE
        self._exit_reason = ""

        self._error_reports = []
        self._entry_nodes = []
        self._exit_nodes = []
        self._libraries = get_installed_library_versions()
        self._operations = {}
        self._loops = {}
        self._storage_cache = defaultdict(dict)

        self.start_time = 0
        self.end_time = 0

        # TODO Add a quick proof-read step to validate operations.json file
        # 1. Ensure valid json
        # 2. Ensure all json keys in file have an analog to known keys (no extras; no misspelled)
        # 3. Ensure all values are the correct types - numeric, string, list, dict, etc
        #   Operand, conditional, config type matching (if possible)
        #   For sure for basics of structure - like "follows" needs a list,
        #   some defs are dicts + lists
        # 4. Last is validation of logical consistency

        self._load(op_config_data)

        # TODO Improve sequence error reporting to the user
        # Do something with error reports here - goal is to have everything that goes wrong
        # in parsing and verifying sequence reported into the _error_reports list and to be
        # able to build a useful report to the user to allow them to fix their file.
        # Potentially have some tags for the different errors and be able to highlight
        # visually in the file where the issues are found (using something like codemirror)
        if len(self._error_reports) > 0:
            raise Exception(
                "\nIssue(s) found in sequence setup:\n - {0}\n".format(
                    "\n - ".join(self._error_reports)
                )
            )

    def __str__(self):
        return "<Sequence id='{0}'>".format(self.uuid)

    def __repr__(self):
        return "<Sequence id='{0}'>".format(self.uuid)

    def _report_error(self, report):
        self._error_reports.append(report)

    def _load(self, op_config_data):
        # Build a list of operations that are configured for n_up
        n_up_operations = []
        for op_info in op_config_data:
            if "loop" in op_info:
                for op in op_info["operations"]:
                    if "n_up" in op:
                        n_up_operations.append(op)
            else:
                if "n_up" in op_info:
                    n_up_operations.append(op_info["operation"])

        # Load in file and check that the basic syntax/construction is valid
        for op_info in op_config_data:
            if "loop" in op_info:
                self._load_loop(op_info, n_up_operations)
            else:
                self._load_operation(op_info, n_up_operations)

        # Add average runtime info to operations
        self._for_all_operations("set_avg_duration", self.avg_runtimes)

        # Make required adjustments to dependencies to cleanup graph
        self._adjust_dependencies()

        # Verify dependency operations exist
        operation_dependencies = flatten_2d_list(
            self._for_all_operations("get_dependency_list")
        )
        loop_dependencies = flatten_2d_list(self._for_all_loops("get_dependency_list"))
        all_dependencies = unique_list(operation_dependencies + loop_dependencies)
        active_operations = self.get_operation_names()
        missing_operations = [
            op for op in all_dependencies if op not in active_operations
        ]
        if len(missing_operations) != 0:
            self._report_error(
                "Missing operations marked as dependencies in sequence: {0}".format(
                    ", ".join(missing_operations)
                )
            )

        # Create the data store/cache to track results from operations that items in the loop
        # depend on
        cache_data = flatten_2d_list(self._for_all_operations("get_external_data"))
        cache_data.extend(flatten_2d_list(self._for_all_loops("get_external_data")))
        for operation, data_key in cache_data:
            self._storage_cache[operation][data_key] = None

        # Check for ops that require data from conditional ops or loops - warn
        external_dependencies = [d[0] for d in cache_data]
        conditional_deps = [
            op
            for op, obj in self._operations.items()
            if obj.is_conditional and op in external_dependencies
        ]
        if len(conditional_deps) != 0:
            self._report_error(
                "Items in sequence depend on the following conditional operation(s) "
                "for data: {0}".format(", ".join(conditional_deps))
            )

        # Check if dependencies store all of the required values
        missing_results = []
        stored_results = {
            key: value.get_result_names() for key, value in self._operations.items()
        }
        for op, results in stored_results.items():
            for result in self._storage_cache[op]:
                if result not in results:
                    missing_results.append(str((op, result)))
        if len(missing_results) != 0:
            self._report_error(
                "Missing required result(s) in operations: {0}".format(
                    ", ".join(missing_results)
                )
            )

        if len(self._error_reports) > 0:
            return

        self._adjust_priority()

    def _load_operation(self, op_info, n_up_operations):
        """ """

        def _store_op(n_pos=0):
            op = OpData(
                op_info,
                self._system_configs,
                self._tool_checkout_methods,
                self._report_error,
                self._runtimedata,
                n_pos=n_pos,
                n_up=self._n_up,
                n_up_operations=n_up_operations,
            )
            # Update the operations map
            if op.id in self._operations:
                # Check for duplicates
                self._report_error(
                    "Duplicate operation defined: '{0}'".format(
                        self._operations[-1].operation_id
                    )
                )
            self._operations[op.id] = op

        # Create operation object
        if op_info.get("n_up", False):
            for n in range(self._n_up):
                _store_op(n)
        else:
            _store_op()

    def _load_loop(self, op_info, n_up_operations):
        loop = Loop(op_info, self._report_error, self._system_configs)
        self._loops[loop.uuid] = loop
        for loop_op in op_info["operations"]:
            self._load_operation(loop_op, n_up_operations)

    def _adjust_priority(self):
        # Calculate priorities
        min_op_time = min(self._for_all_operations("get_avg_duration"))
        # Add priority to operations that take longer to complete so that they will be chosen
        # first. Add an amount equal to the ratio of the duration of the operation verses the
        # duration of the slowest operation.
        for op in self._operations.values():
            op.set_priority(op.priority + int(op.get_avg_duration() / min_op_time))

        def _increase_priority(op_id, seen_list):
            """
            Recursively increase the priority of the named operation, and operations
            it is dependent on
            """
            self._operations[op_id].set_priority(self._operations[op_id].priority + 1)
            for dependency_id in self._operations[op_id].get_dependency_list():
                if dependency_id not in seen_list:
                    seen_list.append(dependency_id)
                    _increase_priority(dependency_id, seen_list)

        # Find the critical path, and give items on it a higher priority than other tasks,
        # by giving +1 higher priority to things that have dependent tasks.
        for dependency_list in self._for_all_operations("get_dependency_list"):
            for dep_id in dependency_list:
                seen = []
                _increase_priority(dep_id, seen)

    def _adjust_dependencies(self):
        # Loop dependency hoisting
        # Ensure that 1) loop operations only have dependencies on other loop operations and 2)
        # all dependencies that come before the loop must be moved to the entry nodes (and not on
        # other internal loop nodes
        for _id, loop_data in self._loops.items():
            loop_operations = loop_data.get_operations()
            ops = {
                key: list(value.dependencies)
                for key, value in self._operations.items()
                if key in loop_operations
            }

            def internal_only(_deps):
                return [dep for dep in _deps if dep in loop_operations]

            def external_only(_deps):
                return [dep for dep in _deps if dep not in loop_operations]

            # Get map of loop operation dependencies that are on other operations within this loop
            clean_internal = {key: internal_only(value) for key, value in ops.items()}
            all_internal = unique_list(flatten_2d_list(clean_internal.values()))

            # Get map of loop operation dependencies that are only on operations external to the
            # loop. These will all be applied to the entry operation nodes
            clean_external = {key: external_only(value) for key, value in ops.items()}
            all_external = unique_list(flatten_2d_list(clean_external.values()))

            # The operations with zero internal dependencies are the entry operations
            for opname, dependencies in clean_internal.items():
                if len(dependencies) == 0:
                    loop_data.entry_nodes.append(opname)
            if len(loop_data.entry_nodes) == 0:
                self._report_error("Unable to find any starting nodes for loop")

            # Apply all external dependencies to the entry nodes
            for op in loop_data.entry_nodes:
                clean_internal[op] = all_external

            # Exit nodes are nodes that no other internal nodes depend on
            loop_data.exit_nodes = [
                op for op in loop_operations if op not in all_internal
            ]
            if len(loop_data.exit_nodes) == 0:
                self._report_error("Unable to find any exit nodes for loop")

            # Set the clean_internal w/ edited entry nodes + exit nodes as the new dependencies for
            # the loop operations. Other than the entry nodes, all loop nodes only depend on each
            # other now.
            for op, deps in clean_internal.items():
                self._operations[op].dependencies = list(deps)

        # Adjust dependencies for operations after loops
        for _id, loop_data in self._loops.items():
            # Walk through all non-loop operations and ensure that if they depend on anything
            # internal to a loop, it must only be loop exit nodes
            loop_ops = loop_data.get_operations()
            for op in self.get_operation_names():
                if op in loop_ops:
                    continue
                deps = list(self._operations[op].get_dependency_list())
                edited = False
                for operation in loop_ops:
                    if operation in deps:
                        deps.remove(operation)
                        edited = True
                if edited:
                    deps.extend(loop_data.get_exit_nodes())
                    self._operations[op].dependencies = list(deps)

        # Optimize operation dependencies to minimize duplicate paths
        ops = {
            key: value.get_dependency_list() for key, value in self._operations.items()
        }
        try:
            matrix = graph_to_path_matrix(ops)
            new_ops = reduce_graph(ops, matrix)
        except SequenceLoop as e:
            self._report_error(str(e))
        except KeyError as e:
            self._report_error("Unexpected key found in graph reduction: {0}".format(e))
        else:
            for op, deps in new_ops.items():
                self._operations[op].dependencies = list(deps)
            self._entry_nodes, self._exit_nodes = find_graph_entry_exit(matrix)

        # If an exit node is a member of a loop, remove it from the exit nodes group - it will be
        # visually grouped with its loop instead of the exit group
        loop_members = flatten_2d_list(self._for_all_loops("get_operations"))
        to_remove = []
        for node in self._exit_nodes:
            if node in loop_members:
                to_remove.append(node)
        for node in to_remove:
            self._exit_nodes.remove(node)

    def _update_storage_cache(self, operation_id, results):
        if operation_id not in self._storage_cache:
            return

        for result in results:
            value, key = result
            if key in self._storage_cache[operation_id]:
                self._storage_cache[operation_id][key] = value

    def _operation_refresh(self, operation_ids):
        """ Refresh operation back to initial state before looping again """
        for operation_id in operation_ids:
            self._operations[operation_id].refresh()

    # ---------- Sequence -----------

    def sequence_starting(self):
        self._running_status = SequenceStatus.RUNNING
        self.start_time = time.time()

    def sequence_ending(self):
        if self._running_status != SequenceStatus.ABORTED:
            self._running_status = SequenceStatus.COMPLETED
        self.end_time = time.time()

    def get_duration_ms(self):
        if self.end_time == 0:
            # Operation is still running
            return int((time.time() - self.start_time) * 1000)
        else:
            return int((self.end_time - self.start_time) * 1000)

    def get_status(self):
        status = {
            "uuid": self.uuid,
            "start_time": self.start_time,
            "duration_ms": self.get_duration_ms(),
            "passing": self.did_pass(),
            "runcode": self._running_status.name,
            "loops": self._for_all_loops("get_status"),
            "library_versions": self._libraries,
            "operations": self._for_all_operations("get_status"),
            "runtimedata": self.get_runtime_data(),
            "version": self.version,
            "entrynodes": self._entry_nodes,
            "exitnodes": self._exit_nodes,
            "info": {},
        }
        if self._exit_reason != "":
            status["info"]["exit_reason"] = self._exit_reason
        return status

    def did_pass(self):
        passing = self._for_all_operations("did_pass", self._storage_cache)
        return False not in passing and self._running_status is SequenceStatus.COMPLETED

    def set_exit_reason(self, reason):
        self._exit_reason = str(reason)

    # ---------- All/Many Operations -----------

    def initialize(self, operation_code):
        try:
            self.version = operation_code.version
        except AttributeError:
            self.version = "0.0"
        self._for_all_operations("initialize", operation_code)
        self.is_initialized = True

    def set_runtime_data(self, runtimedata):
        self._for_all_operations("set_runtime_data", runtimedata)

    def get_runtime_data(self):
        return dict(self._runtimedata)

    def shutdown_operations(self, operations, nice=True):
        """ Request shutdown of operations in list and return list of terminated operations """
        self._running_status = SequenceStatus.ABORTED
        self._for_operations_by_name(operations, "shutdown", nice)
        still_alive = zip(
            operations, self._for_operations_by_name(operations, "process_is_alive")
        )
        return [op for op, alive in still_alive if not alive]

    def abort_if_not_complete_or_error(self, operations):
        """ Set status of all operations in list to abort if they are not complete or in error """
        for op in operations:
            self._running_status = SequenceStatus.ABORTED
            status = self.get_op_run_status(op)
            if (
                status is not OperationState.COMPLETED
                and status is not OperationState.ERROR
            ):
                self._operations[op].set_run_status(OperationState.ABORTED)

    def get_required_tools(self):
        all_required_tools = self._for_all_operations("get_object_tools")
        return [tool for _list in all_required_tools for tool in _list]

    def get_operation_names(self, sort_by_priority=False):
        """ Return all operation ids - sorted by priority if desired """
        if sort_by_priority:
            return self.sort_list_by_priority(self._for_all_operations("get_name"))
        else:
            return self._for_all_operations("get_name")

    def sort_list_by_priority(self, operation_list):
        """ Sort the incoming list of operations by priority - greatest to smallest """
        return sorted(
            list(operation_list),
            reverse=True,
            key=lambda x: self._operations[x].get_priority(),
        )

    def _for_all_operations(self, method, *args):
        """
        Perform a named method on all member operations with list of args and return result list
        """
        return named_method_on_list(self._operations.values(), method, *args)

    def _for_operations_by_name(self, operations, method, *args):
        """ Perform a named method on named operations with list of args and return result list """
        operation_objects = [
            self._operations[opid] for opid in self._operations if opid in operations
        ]
        return named_method_on_list(operation_objects, method, *args)

    # ---------- Individual Operations -----------

    def get_op_uuid(self, operation_id):
        return self._operations[operation_id].uuid

    def get_op_status(self, operation_id):
        self._operations[operation_id].did_pass(self._storage_cache)
        status = self._operations[operation_id].get_status()
        status["sequence"] = self.uuid
        return status
        
    def get_op_result_data(self, operation_id):
        # Evaluate all pass/fail results in operation
        self._operations[operation_id].update_external_data(self._storage_cache)
        return self._operations[operation_id].get_result_data()

    def get_op_storage_data(self, operation_id):
        return self._operations[operation_id].get_storage_data()

    def evaluate_conditional_operation(self, operation_id):
        """ True if operation should be run, False if not """
        return self._operations[operation_id].evaluate(self._storage_cache)

    def prepare_op(self, operation_id):
        """ Prepare operation to run and return its run status """
        return self._operations[operation_id].prepare(self._storage_cache)

    def launch_op(self, operation_id):
        """ Start thread of operation main process """
        return self._operations[operation_id].launch()

    def cleanup_op(self, operation_id):
        try:
            self._operations[operation_id].cleanup()
        except MissingResult as e:
            log.warning(
                "Operation '{0}' completed without saving required results: '{1}'".format(operation_id, ", ".join(e.field))
            )
            emit_event(
                InfoEvents.MESSAGE_UPDATE,
                {
                    "source": "sequence",
                    "message": "Operation '{0}' completed without saving required results: '{1}'".format(operation_id, ", ".join(e.field))
                }
            )
        self._update_storage_cache(
            operation_id, self._operations[operation_id].get_result_values()
        )

    def get_op_run_status(self, operation_id):
        return self._operations[operation_id].get_run_status()

    def get_op_priority(self, operation_id):
        """ Return priority value of operation_id """
        return self._operations[operation_id].get_priority()

    def get_op_duration_ms(self, operation_id):
        """ Return duration of operation_id in milliseconds """
        return self._operations[operation_id].get_duration_ms()

    def is_op_alive(self, operation_id):
        return self._operations[operation_id].process_is_alive()

    def set_operation_status(self, operation_id, status):
        return self._operations[operation_id].set_run_status(status)

    def store_op_error_code(self, operation_id, error_code: ErrorCode):
        self._operations[operation_id].store_error_code(error_code)

    def has_requeue_time_elapsed(self, operation_id, min_requeue_time):
        """ Check if the operation requeue time is greater than the minimum """
        requeue_time = self._operations[operation_id].requeue_time
        if requeue_time is None:
            return True

        if time.time() - requeue_time < min_requeue_time:
            # Requeue time has not yet elapsed
            return False
        else:
            self._operations[operation_id].requeue_time = None
            return True

    def all_dependencies_completed(self, operation_id, done_list):
        """
        For a given operation, check if all its dependencies are in the done_list

        :param str operation_id: the operation name to check
        :param list done_list: list of completed operations
        :return: True if all dependencies are finished
        :rtype: bool
        """
        satisfied = True
        for dependency in self._operations[operation_id].get_dependency_list():
            if dependency not in done_list:
                satisfied = False
        return satisfied

    # ---------- Loops -----------

    def _for_all_loops(self, method, *args):
        """ Perform a named method on all member loops with list of args and return result list """
        return named_method_on_list(self._loops.values(), method, *args)

    def pre_run_check_loop_conditions(self, ready_list):
        """
        Evaluate loops and return list of all operations in ready list to be moved to done list
        """
        ops = flatten_2d_list(
            self._for_all_loops("is_loop_start", ready_list, self._storage_cache)
        )

        # Increment loop iteration counter so all operations can know which iteration
        # of the loop they are running on
        for loop in self._loops.values():
            self._for_operations_by_name(
                loop.get_operations(), "set_loop_iteration", loop.evaluations
            )

        return ops

    def post_run_check_loop_conditions(self, done_list):
        """
        Evaluate loops and return list of all operations in done list to be moved back to
        waiting list
        """
        ops = flatten_2d_list(
            self._for_all_loops("is_loop_end", done_list, self._storage_cache)
        )

        # Refresh operations before they are run again in loop
        self._operation_refresh(ops)

        # Increment loop iteration counter so all operations can know which iteration
        # of the loop they are running on
        for loop in self._loops.values():
            self._for_operations_by_name(
                loop.get_operations(), "set_loop_iteration", loop.evaluations
            )

        return ops
