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
        name = atype.__name__
        stack_trace = "Exception Occurred\n"
        stack_trace += "  {0}: {1}\n".format(name, value)
        for item in traceback.format_tb(tb, 7):
            stack_trace += "    {0}\n".format(item.rstrip('\r\n'))
        # Get string representation of Exception object
        data = str(data)

    log_data = {
        "source": "log",
        "stream": kind.value,
        "message": message,
        "debug_level": debug_level,
        "data": data,
        "stack_trace": stack_trace,
        "pid": os.getpid(),
        "caller": caller
    }
    emit_event(StorageEvents.ON_LOG_DATA, log_data)
    emit_event(InfoEvents.LOG, log_data)


def _get_class_from_frame(fr):
    args, _, _, value_dict = inspect.getargvalues(fr)
    # we check the first parameter for the frame function is named 'self'
    if len(args) and args[0] == 'self':
        # in that case, 'self' will be referenced in value_dict
        the_class = fr.f_locals["self"].__class__.__name__
        the_method = fr.f_code.co_name
        return "{}.{}()".format(str(the_class), the_method)
    return None
