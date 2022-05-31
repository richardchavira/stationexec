# Copyright 2004-present Facebook. All Rights Reserved.

import time

import stationexec
from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.utilities.exceptions import ToolUnavailableException, \
    ToolInUseException


class GetTool(object):
    """
    Context manager for temporarily checking out a tool.
    """

    def __init__(self, toolbox, tool_id, process):
        # type: (stationexec.toolbox.toolbox.ToolBox, str) -> None
        """
        Checkout out the named tool in a context.

        :return: `.Tool` object
        :rtype: Tool
        """
        self.tool_id = tool_id
        self.toolbox = toolbox
        self.tool_obj = None
        self.process = process

    def __enter__(self):
        # type: () -> Tool
        self.tool_obj = self.toolbox.checkout_tool(self.process, self.tool_id)
        return self.tool_obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this always gets called, even if an exception occurs in the context block. it
        # will pass on the exception, unless we return True, so we don't return True.
        if self.tool_obj is not None:
            self.toolbox.return_tool(self.tool_obj, self.process)

        if exc_type == ToolUnavailableException:
            # Tool was offline when requested - do nothing and return
            log.debug(1, "GetTool for '{0}' did not run - tool '{1}' was offline".format(
                self.tool_id, self.process))
            # return True
        elif exc_type == ToolInUseException:
            # Tool was in use by another process when requested - do nothing and return
            log.debug(1, "GetTool for '{0}' did not run - tool '{1}' in use: {2}".format(
                self.tool_id, self.process, exc_tb))
            # return True

        # Allow any exceptions that happened to bubble up to the user
        return False


class GetToolRetry(object):
    """
    Context manager for temporarily checking out a tool.
    """

    def __init__(self, toolbox, tool_id, process, retries=3, wait=3):
        # type: (stationexec.toolbox.toolbox.ToolBox, str, str, int, int) -> None
        """
        Checkout out the named tool in a context.

        :return: `.Tool` object
        :rtype: Tool
        :raises RuntimeError: if times out waiting for tool to be available
        """
        self.tool_id = tool_id
        self.toolbox = toolbox
        self.tool_obj = None
        self.process = process
        self.retries = retries
        self.wait_time = wait

    def __enter__(self):
        # type: () -> Tool
        attempts = 0
        for attempt in range(self.retries):
            try:
                self.tool_obj = self.toolbox.checkout_tool(self.process, self.tool_id)
                return self.tool_obj
            except (ToolUnavailableException, ToolInUseException) as e:
                attempts += 1
                self.tool_obj = None

                if attempts > self.retries:
                    raise RuntimeError("process '{0}' unable to get checkout '{1}' "
                                       "for over {2} seconds: {3}".format(self.process,
                                                                          self.tool_id,
                                                                          self.retries * self.wait_time,
                                                                          e.message))
                time.sleep(self.wait_time)

    def __exit__(self, exc_type, exc_val, exc_tb):
        # this always gets called, even if an exception occurs in the context block. it
        # will pass on the exception, unless we return True, so we don't return True.
        if self.tool_obj is not None:
            self.toolbox.return_tool(self.tool_obj)
