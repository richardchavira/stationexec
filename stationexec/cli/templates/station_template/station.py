# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1
import webbrowser

from stationexec.logger import log
from stationexec.station.events import emit_event, InfoEvents
from stationexec.toolbox.toolbox import get_tools

version = "0.1"
dependencies = []

get_cfg = None


def initialize(register, _get_cfg):
    """ Setup station and register for events """
    global get_cfg
    get_cfg = _get_cfg
    register(InfoEvents.SERVER_STARTED, on_startup)


def on_ui_command(command, **data):
    if command == "test_examples":
        test_examples()


def on_startup(**data):
    webbrowser.open("http://localhost:8888", new=2)


@get_tools("example_tool", "example_tool_2")
def test_examples(tools):
    tools.example_tool.do_action_1()
    tools.example_tool_2.printit()
