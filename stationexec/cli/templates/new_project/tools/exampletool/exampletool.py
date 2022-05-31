# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Example tool class exhibiting all functionality of the base tool class
  and demonstrating how to create a tool that inherits from Tool.
"""
import simplejson

from stationexec.logger import log
from stationexec.toolbox.tool import Tool

version = "1.0"
dependencies = []
default_configurations = {
}


class Exampletool(Tool):
    def __init__(self, **kwargs):
        """ Setup tool with configuration arguments """
        super(Exampletool, self).__init__(**kwargs)

    def initialize(self):
        """ Prepare tool for operation """
        pass

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        if self.is_online:
            return False

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        if command == "action1":
            log.info("Performing Action 1")
            self.do_action_1()
            self.value_to_ui("settable", 14)
            self.ui_log("Set value to 14")
        elif command == "action2":
            log.info("Performing Action 2")
            self.do_action_2()
            self.ui_log("Did action 2")
        elif command == "action3":
            log.info("Performing Action 3")
            self.ui_log(simplejson.dumps(kwargs))
            self.ui_log("Did action 3")

    def do_action_1(self):
        log.info("Action 1 Begin")

    def do_action_2(self):
        log.info("Action 2 Begin")
