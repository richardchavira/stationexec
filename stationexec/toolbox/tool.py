# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
Base class for all tools. Items inheriting will be loaded and
interacted with via tool/toolbox.py.

The \**kwargs that will be passed in when the class is created will contain
all identifying and configuration data from tool_manifest.json. Name the
arguments to __init__ accordingly.

The following items must be implemented in a derived class (otherwise the base
class will throw a NotImplementedError exception):

    * initialize
    * verify_status
    * shutdown
    * on_ui_command

These methods will all be called by tool/toolbox.py to setup and interact with
the tool.
"""

import threading

from stationexec.logger import log
from stationexec.station.events import InfoEvents
from stationexec.utilities.exceptions import ToolUnavailableException, ToolInUseException


class Tool(object):
    """Tool base class that all tools will inherit from"""

    def __init__(self, tool_type, name, tool_id, version, **kwargs):
        """
        Initialize a Tool object.

        :param str tool_type: name of tool driver
        :param str name: display name of tool
        :param str tool_id: unique identifier for tool
        :param str version
        :param dict kwargs: dictionary containing all values required for initializing tool
        """
        self.tool_type = tool_type
        self.name = name
        self.tool_id = tool_id
        self.debug = kwargs["debug"]
        self.dev = kwargs["dev"]
        self.version = version

        self._access_lock = threading.Lock()
        self._status = None
        self._manual_status_change = False
        self.is_shutting_down = False
        self.checked_out_by = "None"

        self._tool_status_changed = kwargs.get("_tool_status_changed")  
        self._register_for_event = kwargs.get("_register_for_event") 
        self._emit_event = kwargs.get("_emit_event") 

        self.is_online = False
        self.set_offline(manual=False)

    def initialize(self):
        """
        Perform all actions required to set tool up completely for use.

        :return: None
        """
        raise NotImplementedError

    def verify_status(self):
        """
        Periodically called (default 5 seconds) to determine if tool is online and healthy.
        Use as a space to fix the tool if things have gone awry.

        :return: None
        """
        raise NotImplementedError

    def shutdown(self):
        """
        Perform all actions required to clean up and close tool.

        :return: None
        """
        raise NotImplementedError

    def on_ui_command(self, command, **kwargs):
        """
        Handle a request from the UI to perform an action.

        :param str command: tool command
        :return: None
        """
        raise NotImplementedError

    def set_status(self, status):
        if status:
            self.set_online()
        else:
            self.set_offline()

    def set_online(self, manual=True):
        self.is_online = True
        self._manual_status_change = manual
        self._update_status()

    def set_offline(self, manual=True):
        self.is_online = False
        self._manual_status_change = manual
        # Ensure the lock is released while the tool is offline - call updates tool status
        self._release_tool_lock("Offline")

    def listen_for_event(self, event, callback):
        if self._register_for_event is None:
            log.warning("Tool event registering not enabled")
            return
        self._register_for_event("tool.{0}".format(self.tool_id), event, callback)

    def emit_event(self, event, data):
        if self._emit_event is None:
            log.warning("Tool event emitting not enabled")
            return
        return self._emit_event(event, data)

    def ui_log(self, message):
        self.emit_event(InfoEvents.MESSAGE_UPDATE, {
            "source": "tool.{0}".format(self.tool_id),
            "message": message
        })

    def value_to_ui(self, target, value):
        self.emit_event(InfoEvents.OBJECT_UPDATE, {
            "source": "tool.{0}".format(self.tool_id),
            "target": target,
            "value": value
        })

    def _get_current_status_message(self):
        if self.is_online and not self._locked():
            return "Available"
        elif self.is_online and self._locked():
            return "In Use by '{0}'".format(self.checked_out_by)
        elif not self.is_online:
            return "Offline"
        else:
            return "Offline"

    def get_endpoints(self):
        return []

    def _get_tool_url(self):
        """
        Get the URL of the current tool

        :return: specific tool url
        """
        return r"/tool/{0}".format(self.tool_id)

    def _locked(self):
        """ Return True if this Tool is currently in use and is therefore locked. """
        return self._access_lock.locked()

    def _acquire_tool_lock(self, process):
        """

        :param process:
        :return:
        """
        # First, attempt to acquire the lock of the tool
        got_lock = self._access_lock.acquire(False)

        # Check if the tool is online and even available for use
        if not self.is_online:
            # Tool is offline, so release the lock
            try:
                self._access_lock.release()
            except threading.ThreadError:
                # Lock was not locked - ignore - that is what we want
                pass
            raise ToolUnavailableException("Tool '{0}' is offline".format(
                self.tool_id))

        # Check if the lock was successfully acquired
        if not got_lock:
            # Tool is already in use by another process
            raise ToolInUseException("Tool '{0}' already in use by '{1}'".format(
                self.tool_id, self.checked_out_by))

        # If we made it this far, the lock was successfully acquired!
        self.checked_out_by = process
        self._update_status()

    def _release_tool_lock(self, process):
        """

        :param process:
        :return:
        """
        if self.checked_out_by == "None" or process == "Offline":
            # Tool is not currently checked out by anyone; release lock just in case
            # Or tool has gone offline and lock needs to be released for future use
            try:
                self._access_lock.release()
            except threading.ThreadError:
                # Tool was not locked
                pass
        elif process != self.checked_out_by:
            # Tool is in use by some other process
            raise ToolInUseException("'{0}' attempted to return tool '{1}' which is being "
                                     "used by '{2}'".format(process, self.tool_id,
                                                            self.checked_out_by))
        else:
            # Release lock on tool
            try:
                self._access_lock.release()
            except threading.ThreadError:
                # Tool was not locked
                pass
            self.checked_out_by = "None"
        self._update_status()

    def get_status(self):
        return self._status

    def _update_status(self):
        """
        Set the tool status

        :return: None
        """
        status = {
            "tool_type": self.tool_type,
            "name": self.name,
            "tool_id": self.tool_id,

            "online_bool": self.is_online,
            "details": self._get_current_status_message(),
            "inuse": self._locked(),
            "version": self.version
        }

        if self._status != status:
            self._status = status

        # Ask toolbox to update all status
        if self._tool_status_changed is not None:
            self._tool_status_changed()
