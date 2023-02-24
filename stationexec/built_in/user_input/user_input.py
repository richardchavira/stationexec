import uuid

from stationexec.toolbox.tool import Tool
from stationexec.station.events import InfoEvents, emit_event
from stationexec.web.handlers import ExecutiveHandler

from .version import version as tool_version


version = tool_version

default_configurations: dict = {}


class UserInput(Tool):
    def __init__(self, **kwargs):
        super(UserInput, self).__init__(**kwargs)

        self.user_input = None

    def initialize(self):
        """Prepare tool for operation"""
        pass

    def verify_status(self):
        pass

    def shutdown(self):
        """Cleanup tool for program shutdown"""
        pass

    def get_input(self, input_schema: dict) -> dict:
        input_schema['uuid'] = uuid.uuid1().hex

        emit_event(InfoEvents.USER_INPUT_REQUEST, data_dict=input_schema)        
        
        while self.user_input is None:
            pass
        
        user_input = self.user_input
        self.user_input = None

        return user_input

    def get_endpoints(self):
        """ Setup tool API """
        endpoints = [
            (f'/tool/{self.tool_id}/input-data', UserInputHandler, {"tool": self}),
        ]
        return endpoints

    def on_ui_command(self, command, **kwargs):
        """Command received from UI"""
        if command == "TEST":
            input_data = {
                "input_1": {
                    "type": "radio",
                    "label": "Choose One",
                    "choices": ["Choice A", "Choice B"]
                },
                "input_2": {
                    "type": "text",
                    "label": "Type Here",
                },
                "input_3": {
                    "type": "checkbox",
                    "label": "Check the Box"
                },
                "message": "Operation One"
            }

            results = self.get_input(input_data)

            for parameter_name, parameter_result in results.items():
                self.ui_log(f'{parameter_name}: {parameter_result}')

class UserInputHandler(ExecutiveHandler):
    """
    This endpoint recieves data from UI inputs
    """

    def initialize(self, **kwargs):
        self.tool = kwargs["tool"]

    def get(self):
        self.write({ })

    def post(self):
        self.tool.user_input = self.json_args
