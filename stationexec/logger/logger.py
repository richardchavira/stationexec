# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import time
import warnings

import colorama
from stationexec.logger.log import LogKind, _publish_log_message
from stationexec.station.events import register_for_event, InfoEvents
from stationexec.utilities.colors import Colors
from stationexec.utilities.config import get_all_paths
from stationexec.utilities.singleton import Singleton
from stationexec.utilities.time import get_local_time

colorama.init()


# noinspection PyUnusedLocal
class Logger(Singleton):
    """ A class which processes log messages. """

    prefix = None  # type: str
    _debug = 0  # type: int
    log_file_base = None  # type: str

    def init(self, prefix, debug, file_path=None, collapse_empty_caller=False):
        """
        'init' instead of '__init__' to fit the singleton pattern

        __init__ is called every time the class is referenced, whereas
        init is only called explicitly.
        """
        self.prefix = prefix
        self._debug = int(debug)

        self.log_file_base = file_path or get_all_paths()["log_folder"]
        self.collapse_empty_caller = collapse_empty_caller

        warnings.showwarning = self._override_warnings

        register_for_event("logger", InfoEvents.LOG, self.log_message)

    @staticmethod
    def _override_warnings(message, category, filename, lineno, file=None, line=None):
        """Hook to write a warning to a file; replace if you like."""
        msg = warnings.WarningMessage(message, category, filename, lineno, file, line)
        _publish_log_message(message=warnings._formatwarnmsg_impl(msg), kind=LogKind.DEBUG, debug_level=5)

    def _log(self, color, prefix, message, data, pid, caller):
        prefix = "{0} | {1}".format(get_local_time().strftime("%Y-%m-%d %H:%M:%S"), prefix)
        self._log_to_file(prefix, message + (": " + str(data) if data else ""), pid, caller)

        if bool(self._debug >= 0):
            if caller:
                message = str(caller) + "- " + message
            if pid:
                message = "({0}) {1}".format(pid, message)
            print(
                color + prefix + ": " + message + (": " + str(data) if data else "") + Colors.ENDC)

    def log_message(self, message, stream, debug_level, data, stack_trace, pid, caller, **kwargs):
        if stream == LogKind.DEBUG.value:
            # level 99 can be used during development to mean "always display" regardless of
            # --debug level
            if debug_level <= self._debug or debug_level == 99:
                prefix = "Debug{0:<2}".format(debug_level)
                self._log(Colors.OKBLUE, prefix, message, data, pid, caller)
        elif stream == LogKind.INFO.value:
            self._log(Colors.ENDC, "Info   ", message, data, pid, caller)
        elif stream == LogKind.WARNING.value:
            self._log(Colors.WARNING, "Warning", message, data, pid, caller)
        elif stream == LogKind.ERROR.value:
            self._log(Colors.ERROR, "Error  ", message, data, pid, caller)
        elif stream == LogKind.EXCEPTION.value:
            self._log(Colors.ERROR, stack_trace, message, data, pid, caller)
        else:
            self._log(Colors.BLINK, "Unknown", message, data, pid, caller)

    def _log_to_file(self, prefix, message, pid, caller):
        # Tag files with prefix and name them per day
        file_name_timestamp = time.strftime("%Y-%m-%d", time.localtime())
        log_file_name = os.path.join(self.log_file_base, "{0}-{1}.log".format(
            self.prefix, file_name_timestamp))
        with open(log_file_name, "a") as f:
            if caller:
                caller = "{0:<42}|".format(caller)
            else:
                if self.collapse_empty_caller:
                    caller = ""
                else:
                    caller = "{0:<42}|".format("")

            f.write("{0:<27}|{1:<6}|{2}{3}\n".
                    format(prefix, pid, caller, message))
