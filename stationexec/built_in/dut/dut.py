# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Tool for interfacing with the DUT and tracking DUT status
"""
import re

from stationexec.toolbox.tool import Tool
from stationexec.station.events import StorageEvents, RetrievalEvents, InfoEvents, emit_event
from stationexec.web.handlers import ExecutiveHandler
from stationexec.utilities.config import get_system_config

version = "2.0"
dependencies = []
default_configurations = {}

DEFAULT_SERIAL_NUMBER = 'test' # get_system_config().get('default_dut_serial', 'test')

def dev_mode(func):
    def wrapper_function(dut, *args, **kwargs):
        if not dut.dev:
            return func(dut, *args, **kwargs)
        else:
            return
    
    return wrapper_function

class Dut(Tool):
    """ Setup tool with configuration arguments """

    def __init__(self, **kwargs):
        super(Dut, self).__init__(**kwargs)

        self._serial_number = None
        self.test_count = 0
        
        self.dev = kwargs.get('dev')
        if self.dev:
            self._serial_number = DEFAULT_SERIAL_NUMBER
        self.id_patterns = kwargs.pop("id_patterns")

        # Use the end of sequence event to update DUT routing
        self.listen_for_event(StorageEvents.ON_SEQUENCE_END, self.on_sequence_end)
        self.listen_for_event(InfoEvents.USER_LOGGED_OUT, self.on_user_log_out)

    def initialize(self):
        """ Prepare tool for operation """
        pass
    
    @dev_mode
    def verify_status(self):
        """ Check that tool is online; attempt to repair if not. Called every 5 seconds. """
        self.update_ui()
        return True if self._serial_number else False

    def shutdown(self):
        """ Cleanup tool for program shutdown """
        pass

    def on_ui_command(self, command, **kwargs):
        """ Command received from UI """
        pass

    def get_endpoints(self):
        """ Setup tool API """
        endpoints = [
            ("/tool/dut/data", DataHandler, {"tool": self})
        ]
        return endpoints

    def update_ui(self):
        if self._serial_number is False:
            serial_number = "Invalid serial number"
        else:
            serial_number = str(self._serial_number)

        self.value_to_ui(f"{self.tool_id}_serial_number", serial_number)
        self.value_to_ui(f"{self.tool_id}_test_count", str(self.test_count))

    def reset_data(self):
        self._serial_number = None
        self.test_count = 0
        
        emit_event(
            InfoEvents.DUT_SERIAL_NUMBER_UPDATE,
            data_dict={
                'serial_number': self._serial_number,
                'test_count': self.test_count
            }
        )

    @dev_mode
    def on_sequence_end(self, data, evt=None):
        if len(data) == 0:
            return

        self.reset_data()
        self.update_ui()
        
    @dev_mode
    def on_user_log_out(self, **event_data):
        self.reset_data()
    
    @property
    def serial_number(self):
        return self._serial_number
        
    @serial_number.setter
    def serial_number(self, serial_number):
        self.reset_data()

        if not self.validate_serial_number(serial_number):            
            self._serial_number = False
            return

        # Add DUT to database if serial number does not already exist
        exisiting_dut_data = self.get_dut(serial_number)
        if exisiting_dut_data:
            self.test_count = exisiting_dut_data.get('test_count')
        else:
            self.add_dut(serial_number)

        self._serial_number = serial_number
        
        emit_event(
            InfoEvents.DUT_SERIAL_NUMBER_UPDATE,
            data_dict={
                'serial_number': self._serial_number,
                'test_count': self.test_count
            }
        )

    def get_dut(self, serial_number):
        return emit_event(RetrievalEvents.GET_DUT_DATA, data_dict={ "serial_number": serial_number })

    def add_dut(self, serial_number):
        emit_event(StorageEvents.ON_ADD_DUT, data_dict={ "serial_number": serial_number })

    def validate_serial_number(self, serial_number):
        if self.dev:
            return True
        for pattern in self.id_patterns:
            match = re.fullmatch(pattern, serial_number)
            if match:
                return True

        return False

class DataHandler(ExecutiveHandler):
    def initialize(self, **kwargs):
        self.tool = kwargs["tool"]

    def get(self):
        self.write({
            "serial_number": self.tool.serial_number,
            "test_count": self.tool.test_count
        })

    def post(self):
        serial_number = self.json_args.get('serialNumber')
        self.tool.serial_number = serial_number
        
        self.write({ "serial_number": self.tool.serial_number })
