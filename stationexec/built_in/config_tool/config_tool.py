# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

# @nolint
"""
Config Tool Tool
"""
from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.web.handlers import ExecutiveHandler
from stationexec.utilities import config
import os
import simplejson

version = "0.1"
dependencies = ["simplejson"]
default_configurations = {
    "data_location": "test_config.json"
}


class ConfigTool(Tool):
    def __init__(self, **kwargs):
        """ Setup tool with configuration arguments """
        super(ConfigTool, self).__init__(**kwargs)
        self.default_dir = os.path.dirname(config.get_all_paths()["config_file"])
        self.data_loc = kwargs.get("data_location", "test_config.json")
        if not os.path.isabs(self.data_loc):
            # put it in the default folder
            self.data_loc = os.path.join(self.default_dir, self.data_loc)

        # check to see if path is valid...
        # dirname = os.path.dirname(self.data_loc)
        # fname = self.data_loc[len(dirname):]


    def initialize(self):
        """ Prepare tool for operation """
        log.info(f"Checking path {self.data_loc}...")
        if not os.path.exists(os.path.dirname(self.data_loc)):
            try:
                os.mkdir(os.path.dirname(self.data_loc))
            except Exception as e:
                log.exception(f"Error in dir {self.data_loc} path.", e)
                log.info(f"Using Default path {self.default_dir}")
                self.data_loc = self.default_dir

    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        self.value_to_ui(f"{self.tool_id}_config_file", self.data_loc)

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        if command == "save":
            self.ui_log("Saving all settings")
            self.save_config_file(kwargs)
        elif command == "new":
            key = kwargs.get("name")
            value = kwargs.get("value")
            self.ui_log("Adding new setting")
            self.set_config(key, value)

    def read_config_file(self):
        data = {}
        if os.path.exists(self.data_loc):
            with open(self.data_loc, "r+", encoding="utf-8") as file:
                data = simplejson.load(file)
        return data

    def get_config(self, keyword):
        data = self.read_config_file()
        return data.get(keyword, None)

    def set_config(self, keyword, value):
        data = self.read_config_file()
        data[keyword] = value
        self.save_config_file(data)

    def save_config_file(self, data):
        with open(self.data_loc, "w+", encoding="utf-8") as file:
            simplejson.dump(data, file, indent=4)

    def get_endpoints(self):
        endpoints = [
            (f"/tool/{self.tool_id}/data", DataHandler, {"tool": self})
        ]

        return endpoints


class DataHandler(ExecutiveHandler):
    tool = None  # Type: ConfigTool

    def initialize(self, **kwargs):
        self.tool = kwargs.get("tool")

    def get(self):
        data = self.tool.read_config_file()
        log.info(f"Sending data: {data}")
        self.write(simplejson.dumps(data))
        self.finish()
        return
