# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

# @nolint
"""
{{tool_name}} Tool
"""
from stationexec.logger import log
from stationexec.toolbox.tool import Tool

version = "0.1"
dependencies = []
default_configurations = {
}


class {{tool_class}}(Tool):
    def __init__(self, **kwargs):
        """ Setup tool with configuration arguments """
        super({{tool_class}}, self).__init__(**kwargs)

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
        pass
