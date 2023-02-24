# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os
import signal
import sys
import threading
from functools import partial

from stationexec.logger import log
from stationexec.station.events import emit_event_non_blocking, ActionEvents
from stationexec.utilities.ioloop_ref import IoLoop

MAX_WAIT_SECONDS_TILL_SHUTDOWN = 2


def install_signal_handlers(self):
    for sig_id in signal_list():
        signal.signal(sig_id, partial(sig_handler, self))


def signal_list():
    """ Return a list of signals to be caught on this OS """
    sig_list = [signal.SIGTERM, signal.SIGINT]
    # SIGQUIT only supported on Linux systems
    if os.name != "nt":
        sig_list.append(signal.SIGQUIT)
    else:
        sig_list.append(signal.SIGBREAK)
    return sig_list


def process_name(pid=None):
    """
    Return the process name (i.e. cmdline) for the specified PID, or the current process
    if pid=None
    """
    if pid is None:
        pid = os.getpid()
    if sys.platform == "linux":
        # This process unsupported on Windows and Mac
        with open("/proc/{0}/cmdline".format(pid), 'r') as content_file:
            name_of_process = content_file.read()
    else:
        name_of_process = "unknown"
    return name_of_process


# noinspection PyUnusedLocal
def sig_handler(self, signum, frame):
    """ catch a signal and shut down the station exec and all threads """
    print("\n")  # if in terminal, move to next line to avoid keypress output

    signals_to_name_dict = {
        getattr(signal, n): n
        for n in dir(signal)
        if n.startswith('SIG') and '_' not in n
    }

    # prevent duplicate signals
    for sig_id in signal_list():
        signal.signal(sig_id, signal.SIG_IGN)

    log.warning(
        "Caught signal on pid {1} '{2}': {0}".format(
            signals_to_name_dict.get(signum, "Unnamed signal: %d" % signum),
            os.getpid(),
            process_name().rstrip('\0'),
        )
    )

    io_loop = IoLoop().current()

    log.info("Stopping HTTP server")
    if self.web_server is not None:
        io_loop.add_callback_from_signal(self.web_server.stop)
    log.info(
        "      Will shutdown within {0} seconds ...".format(
            MAX_WAIT_SECONDS_TILL_SHUTDOWN
        )
    )
    io_loop.call_later(MAX_WAIT_SECONDS_TILL_SHUTDOWN, stop_loop)

    emit_event_non_blocking(ActionEvents.SHUTDOWN)


def stop_loop():
    IoLoop().current().stop()
    log.info('HTTP Shutdown finally')

    # tell user about remaining threads, since they will cause a hang.
    # don't report this thread (MainThread)
    thread_list = threading.enumerate()
    thread_list = list(filter(lambda a: "MainThread" not in a.name, thread_list))
    if thread_list:
        log.warning("The following threads did not shut down:")
        for t in thread_list:
            log.warning("  " + str(t))
