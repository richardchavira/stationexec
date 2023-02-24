# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

# @nolint
"""
{{tool_name}} Async Tool
"""
from stationexec.logger import log
from stationexec.toolbox.asynctoolbase import AsyncToolBase

version = "0.1"
dependencies = ["pyserial"]
default_configurations = {
}


class {{tool_class}}(AsyncToolBase):
    def __init__(self, **kwargs):
        """
        Setup asynctool based tool

        If your message delimiter is not one of \r, \n, or \r\n, then pass in an argument
        delimiter='\0' with your correct delimiting sequence to the super call

        :param dict kwargs: All leftover args from call; passed to parent class
        """
        super({{tool_class}}, self).__init__(message_processor=self.message_processor,
                                             **kwargs)

    def on_ui_command(self, command, **kwargs):
        """
        Called when a POST is received at '/tool/command' targeted at this tool. This method
        should map the incoming 'command' argument and **kwargs to a tool method

        :param str command: Value of command passed in from UI
        :param dict kwargs: Contains named arguments from UI

        :return:
        """
        pass

    def message_processor(self, messages):
        """
        Optional method called with new data when it is received

        :param list messages:
        :return:
        """
        for message in messages:
            log.debug(5, message)

    def action1(self):
        log.info("Action 1 is Starting")
        self.send("command_to_send\n")

    def action2(self):
        resp = self.send_receive("command_2\n")
        log.info("Received response: {0}".format(resp))
