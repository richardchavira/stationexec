# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from stationexec.logger import log
from stationexec.sequencer.utilities import evaluate_conditional, parse_conditional_reference, parse_data_reference
from stationexec.utilities.uuidstr import get_uuid


class Loop(object):
    def __init__(self, loop, report_error, system_configs, n_up=1, n_up_operations=None):
        self._report_error = report_error
        if "operations" not in loop:
            raise Exception("Loop defined with no operations")

        self.uuid = get_uuid()
        self._operations = [op["operation"] for op in loop["operations"]]
        self._external_data = []

        self.dependencies = []
        if n_up_operations is None:
            n_up_operations = []

        self.entry_nodes = []
        self.exit_nodes = []
        self.evaluations = 0

        self.operand1 = None
        self.operand2 = None
        self.condition = None
        self.type = None
        # Special variable used in for loop so that the target iteration value will not change
        self._condition_cache = None

        # for all loops and conditions, treat a None condition as a value - probably a False.
        # a for loop is a pre-check - if the condition is None, never run it
        # for a for loop, cache the value the first time, don't allow the loop counter target to
        # change while running

        try:
            self.type, ref_string = loop["loop"].split(" ", 1)
        except ValueError:
            self._report_error("Loop condition not formed correctly: {0}".format(loop["loop"]))
            return

        if self.type == "repeat":
            try:
                ref = parse_data_reference("condition", ref_string, system_configs)
            except KeyError as e:
                self._report_error(
                    "'repeat' loop missing _config data in reference '{0}': key error {1}".format(ref_string, e))
            else:
                self.condition = ref["value"]
                self._external_data.append(ref)
        elif self.type in ["while", "dowhile"]:
            try:
                self.condition, op1, op2, op3 = parse_conditional_reference(
                    ref_string, system_configs)
            except KeyError as e:
                self._report_error(
                    "'{2}' loop missing _config data in reference '{0}': key error {1}".format(ref_string, e, self.type))
            else:
                self.operand1 = op1["value"]
                self.operand2 = op2["value"]
                self.operand3 = op3["value"]
                self._external_data.append(op1)
                self._external_data.append(op2)
                self._external_data.append(op3)
        else:
            self._report_error("Unknown loop type configured: {0}".format(self.type))

        if n_up > 1:
            loop_ops = self.get_operations()
            for opid in n_up_operations:
                if opid in loop_ops:
                    loop_ops.remove(opid)
                    # Add all of the n_up operation instances to the dependencies
                    for n in range(n_up):
                        loop_ops.append("{0}__{1}".format(opid, n))
            self._operations = loop_ops

            for data in self._external_data:
                if data["source"] in n_up_operations:
                    # One of the operands comes from an n_up operation, but since there are
                    # multiple of those, this is not allowed as it is not specified which of the
                    # multiple to make the decision on
                    self._report_error("Loop referencing data in an n_up operation - unclear "
                                       "which value to choose")
        else:
            # Not in n_up mode - Clean up operation references in case there is reference to a
            # specific n_up operation name
            for key in self._external_data:
                if key["source"] not in ["_config", "_constant"]:
                    key["source"] = key["source"].split("__")[0]

        self.dependencies = [key["source"] for key in self._external_data
                             if key["source"] not in ["_config", "_constant"]]

    def _status_string(self):
        message = ""
        if self.type == "repeat":
            if self.condition is None:
                message = "0/0"
            else:
                message = "{0}/{1}".format(self.evaluations, self.condition)
        elif self.type == "while":
            if self.operand1 is None or self.operand2 is None:
                message = "while"
            else:
                message = "while {0} {1} {2}".format(self.operand1, self.condition, self.operand2)
        elif self.type == "dowhile":
            if self.operand1 is None or self.operand2 is None:
                message = "do while"
            else:
                message = "do while {0} {1} {2}".format(self.operand1, self.condition,
                                                        self.operand2)

        return "<Loop status='{0}' type='{1}' members='{2}'>".format(message, self.type,
                                                                     ",".join(self._operations))

    def __str__(self):
        return self._status_string()

    def __repr__(self):
        return self._status_string()

    def get_status(self):
        return {
            "type": self.type,
            "condition": self.condition,
            "operand1": self.operand1,
            "operand2": self.operand2,
            "members": self.get_operations(),
            "entrynodes": self.entry_nodes,
            "exitnodes": self.exit_nodes
        }

    def is_loop_start(self, op_start_list, storage_cache):
        # Are any of the items in the incoming ready-to-run list entry nodes for this loop?
        found_entry_node = False
        for op in self.entry_nodes:
            if op in op_start_list:
                found_entry_node = True

        # If so, evaluate. If condition is True, do nothing and let loop proceed. If False, return
        # list of all ops to be moved to done.
        if found_entry_node:
            if not self._evaluate_loop(storage_cache, "start"):
                # Condition is False - return all member ops to be moved to done
                return self.get_operations()
        return []

    def is_loop_end(self, op_done_list, storage_cache):
        # Are all of the loop's exit nodes represented in the incoming done list?
        found_unfinished_exit_node = False
        for op in self.exit_nodes:
            if op not in op_done_list:
                found_unfinished_exit_node = True

        # If so, evaluate. If condition is true, return list of all ops to be moved back to
        # waiting list. If false, do nothing. Loop is done.
        if not found_unfinished_exit_node:
            # All exit nodes were in the done list
            if self._evaluate_loop(storage_cache, "end"):
                # Condition is True - return all member ops to be moved to waiting
                return self.get_operations()
        return []

    def _evaluate_loop(self, storage_cache, when):
        """

        :param storage_cache:
        :return: True when condition is met to continue, False when condition is not met -
                  stop looping
        :rtype: bool
        """
        self.update_external_data(storage_cache)

        evaluation = False
        if self.type == "repeat":
            if self._condition_cache is None:
                self._condition_cache = self.condition

            if self._condition_cache is None:
                # No value available to evaluate against - return False to say the loop is finished
                # Do not run
                evaluation = False
            elif self.evaluations >= self._condition_cache:
                # The number of evaluations of the condition (equivalent to the number of for
                # loops run) has met the preset condition - return False to indicate the loop
                # is finished
                evaluation = False
            else:
                # The loop still has more iterations to go
                evaluation = True
            if when == "start":
                self.evaluations += 1
        elif self.type == "while" or (self.type == "dowhile" and when == "end"):
            conditionals_valid = True
            # Ensure that the conditional values are valid for comparison - int, float, bool
            for op, op_name in zip([self.operand1, self.operand2, self.operand3],
                                   ["operand1", "operand2", "operand3"]):
                if op is None:
                    continue
                if type(op) not in [int, float, bool]:
                    conditionals_valid = False
                    log.error("Unsupported operand type in conditional operation: '{0}' '{1}'"
                              .format(op_name, type(op)))
            if conditionals_valid:
                evaluation = evaluate_conditional(self.condition, self.operand1, self.operand2,
                                                  self.operand3)
            else:
                evaluation = False

            if self.type == "while" and when == "start":
                self.evaluations += 1
            if self.type == "dowhile" and when == "end":
                self.evaluations += 1
        elif self.type == "dowhile" and when == "start":
            evaluation = True

        return evaluation

    def get_dependency_list(self):
        return list(self.dependencies)

    def get_operations(self):
        return list(self._operations)

    def get_external_data(self):
        public_external_data = []
        for key in self._external_data:
            if key["source"] not in ["_config", "_constant"]:
                public_external_data.append((key["source"], key["external_key"]))
        return public_external_data

    def get_entry_nodes(self):
        return list(self.entry_nodes)

    def get_exit_nodes(self):
        return list(self.exit_nodes)

    def update_external_data(self, storage_cache):
        for item in self._external_data:
            if item["source"] in storage_cache:
                item["value"] = storage_cache[item["source"]].get(item["external_key"])

        # Set the storage cache data parameters into the loop
        for val in self._external_data:
            key = val["local_key"]
            value = val["value"]
            if key.startswith("_data::"):
                key = key.split("::", 1)[1]
            setattr(self, key, value)
