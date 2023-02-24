# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Example tool class exhibiting all functionality of the base tool class
  and demonstrating how to create a tool that inherits from Tool.
"""
from time import sleep

from stationexec.toolbox.tool import Tool

version = "1.0"
dependencies = []
default_configurations = {}


class Exampletool2(Tool):
    """ Setup tool with configuration arguments """

    def __init__(self, **kwargs):
        super(Exampletool2, self).__init__(**kwargs)

    def initialize(self):
        """ Prepare tool for operation """
        pass

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        pass

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        raise NotImplementedError

    def printit(self, arg1=0, arg2="b"):
        """ Simple method in the example tool to print hello world. """
        sleep(3)
        self.ui_log("Hello World! {0} {1}".format(arg1, arg2))
