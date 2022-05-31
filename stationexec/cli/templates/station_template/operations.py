# Copyright 2004-present Facebook. All Rights Reserved.

import time

from stationexec.sequencer.operation import Operation, require_tools, OperationState


version = "0.1"


@require_tools("example_tool", "example_tool_2")
class One(Operation):
    def operation_action(self):
        self.example_tool_2.printit()
        time.sleep(1)


class Two(Operation):
    def operation_action(self):
        time.sleep(1)
        self.save_result("important_value", {"a": 1, "b": 2})
        self.save_result("important_value2", 14)


class Three(Operation):
    def operation_action(self):
        time.sleep(1)
        self.save_result("upper_bound", 14)


class Four(Operation):
    def operation_action(self):
        time.sleep(1)
        pass


class Five(Operation):
    def operation_action(self):
        time.sleep(1)
        self.save_result("center_value", 13)
        self.save_result("choice", True)
        self.save_result("image_storage", "0123456789ABCDEF")
        self.save_result("text_data", "It's go time")


class Six(Operation):
    def operation_action(self):
        time.sleep(1)


class Seven(Operation):
    def operation_action(self):
        time.sleep(1)


class Eight(Operation):
    def operation_action(self):
        time.sleep(1)
        self.save_result("result_value", 11)
        self.save_result("data_value", "text")


class Nine(Operation):
    def operation_action(self):
        time.sleep(1)
        self.ui_log("{0}: loop iteration {1}".format(self.get_id(),
                                                     self.get_loop_iteration()))
        if self.get_loop_iteration() > 1:
            self.save_result("index", 9)
        else:
            self.save_result("index", 12)


class Ten(Operation):
    def operation_action(self):
        time.sleep(1)
