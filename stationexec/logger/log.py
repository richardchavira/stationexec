# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
This file implements a method to publish log messages of varying
severities.

Other files should import this file, then make calls like:

.. code-block:: python

    from stationexec.logging import log
    log.info("This is a message")

"""

import inspect
import os
import sys
import traceback
from enum import Enum, unique

from stationexec.station.events import emit_event, InfoEvents, StorageEvents


@unique
class LogKind(Enum):
    """
    The supported kinds of log messages.
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    EXCEPTION = "exception"
    USAGE = "usage"
    DISPLAY = "display"
    API = "API"

class MethodLoggingWrapper:
    """ This class wraps any callable and will log the arguments, keyword arguments, and response of the
    method or function provided to it.
    """
    def __init__(self, method, api_name=" ", excluded_methods=None):
        self.method = method
        self.api_name = api_name
        if not excluded_methods:
            self.excluded_methods = [
                '__class__',
                '__delattr__',
                '__dict__',
                '__dir__',
                '__doc__',
                '__eq__',
                '__format__',
                '__ge__',
                '__getattribute__',
                '__gt__',
                '__hash__',
                '__init__',
                '__init_subclass__',
                '__le__',
                '__lt__',
                '__module__',
                '__ne__',
                '__new__',
                '__reduce__',
                '__reduce_ex__',
                '__repr__',
                '__setattr__',
                '__sizeof__',
                '__str__',
                '__subclasshook__',
                '__weakref__',
                '_acquire_tool_lock',
                '_get_current_status_message',
                '_get_tool_url',
                '_locked',
                '_release_tool_lock',
                '_update_status',
                'emit_event',
                'get_endpoints',
                'get_status',
                'initialize',
                'listen_for_event',
                'log_message',
                'on_ui_command',
                'set_offline',
                'set_online',
                'set_status',
                'shutdown',
                'store_error_code',
                'ui_log',
                'value_to_ui',
                'verify_status',
                'tool_status_listener'
            ]
        else:
            self.excluded_methods = excluded_methods

    def api_logger(self, arguments, keywords, result):
        if self.method.__name__ in self.excluded_methods:
            return
        api(f'calling method: {self.method.__name__} of api {self.api_name} with arguments: {arguments} and keywords: {keywords}')
        api(f'{self.api_name} method {self.method.__name__} responded with: {result}')
    
    def __call__(self, *args, **kwargs):
        result = self.method(*args, **kwargs)
        self.api_logger(args, kwargs, result)
        return result


def debug(level, message):
    # type: (int, str) -> None
    """
    Publish a debug message.

    :param int level: debug verbosity level of message, beginning at 1; 99 can be used during
        development to always display the debug message, but should not be left in the code
    :param str message: text of log message
    """
    if level < 1:
        level = 1
    _publish_log_message(kind=LogKind.DEBUG, debug_level=level, message=message)


def info(message):
    # type: (str) -> None
    """
    Publish an informational level message.

    :param str message: text of log message
    """
    _publish_log_message(kind=LogKind.INFO, message=message)


def warning(message):
    # type: (str) -> None
    """
    Publish a warning message.

    :param str message: text of log message
    """
    _publish_log_message(kind=LogKind.WARNING, message=message)

def api(message):
    _publish_log_message(kind=LogKind.API, message=message)


def error(message):
    # type: (str) -> None
    """
    Publish an error message.

    :param str message: text of log message
    """
    _publish_log_message(kind=LogKind.ERROR, message=message)


def exception(message, e):
    # type: (str, Exception) -> Exception
    """
    Publish an exception error event.

    :param str message: text of log message
    :param Exception e: exception that occurred
    :return: the exception passed in
    """
    _publish_log_message(kind=LogKind.EXCEPTION, message=message, data=e)
    return e


def _publish_log_message(kind, message, debug_level=None, data=None):
    """
    Core function to publish a log message. Do not call directly.

    :param LogKind kind: type of log message
    :param str message: text of log message
    :param int debug_level: debug message level, if log_type=="debug", else ignored
    :param object data: optional data string or Exception object
    """

    caller = _get_class_from_frame(inspect.stack()[2][0])

    stack_trace = ""
    if kind == LogKind.EXCEPTION:
        atype, value, tb = sys.exc_info()
        for line in traceback.format_exception(atype, value, tb):
            stack_trace = f"{stack_trace}\n{line}"

    log_data = {
        "source": "log",
        "stream": kind.value,
        "message": message,
        "debug_level": debug_level,
        "data": None,
        "stack_trace": stack_trace,
        "pid": os.getpid(),
        "caller": caller,
    }
    emit_event(StorageEvents.ON_LOG_DATA, log_data)
    emit_event(InfoEvents.LOG, log_data)


def _get_class_from_frame(fr):
    args, _, _, value_dict = inspect.getargvalues(fr)
    # we check the first parameter for the frame function is named 'self'
    op_name = args[0] if len(args) else ''
    if op_name == 'self' or op_name == 'op_instance':
        # in that case, 'self' will be referenced in value_dict
        the_class = fr.f_locals[op_name].__class__.__name__
        the_method = fr.f_code.co_name
        return "{}.{}()".format(str(the_class), the_method)
    return None
