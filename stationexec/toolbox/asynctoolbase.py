# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
This is a general Asynchronous communication handling class. Classes that connect to tools via
Serial or TCP can inherit from this class.
"""

import socket
import time
from collections import deque
from datetime import datetime
from threading import Lock

# noinspection PyPackageRequirements
import serial
import tornado.iostream
from serial.serialutil import Timeout
from stationexec.logger import log
from stationexec.toolbox.tool import Tool
from stationexec.utilities.byte_conversion import to_bytes
from stationexec.utilities.ioloop_ref import IoLoop
from tornado import gen


class AsyncToolBase(Tool):
    """A communication class to base comm tools on."""

    def __init__(self, message_processor=None, **kwargs):
        super(AsyncToolBase, self).__init__(**kwargs)
        self._asynctool = AsyncTool(**kwargs)
        self._asynctool.set_processor_callback(message_processor)
        self._asynctool.set_status_callback(self.set_status)

    def initialize(self):
        self._asynctool.initialize()

    def verify_status(self):
        if self._asynctool.is_active:
            self.set_online()
        else:
            self.set_offline()

    def set_status(self, status_bool):
        if status_bool:
            self.set_online()
        else:
            self.set_offline()

    def shutdown(self):
        self.set_offline()
        self.is_shutting_down = True
        self._asynctool.shutdown()

    def send(self, data):
        """
        Send data to active connection

        :param data:
        :return:
        """
        try:
            self._asynctool.write(data)
        except Exception as e:
            log.exception(
                "Error while sending async data in {0}".format(self.tool_id), e
            )

    def receive(self, wait=False, after=None):
        """
        Receive next piece of data available from connection

        If wait is false, oldest available data is returned immediately, if no data, return None
        If wait is true, if no data is available, wait until there is data to return
        If after is defined, the data must be received after the specified time

        :param bool wait:
        :param datetime after:
        :return:
        """
        try:
            return self._asynctool.read(wait, after)
        except Exception as e:
            log.exception(
                "Error while receiving async data in {0}".format(self.tool_id), e
            )
            return None

    def send_receive(self, data, clear_buffer=False):
        """
        Send a packet and wait for a response that comes after the sending

        :param str data:
        :param bool clear_buffer:
        :return:
        """
        try:
            if clear_buffer:
                self._asynctool.clear_rx_queue()
            now = datetime.now()
            self.send(data)
            return self.receive(wait=True, after=now)
        except Exception as e:
            log.exception(
                "Error while doing async send_receive in {0}".format(self.tool_id), e
            )
            return None

    def clear_rx_buffer(self):
        """

        :return:
        """
        try:
            self._asynctool.clear_rx_queue()
        except Exception as e:
            log.exception(
                "Error while clearing async rx data in {0}".format(self.tool_id), e
            )

    def run_on_connect(self, method, delay=0):
        self._asynctool.run_on_connect(method, delay)

    def on_ui_command(self, command, **kwargs):
        raise NotImplementedError


class AsyncMessage(object):
    def __init__(self, msg_id, data):
        self.msg_id = msg_id
        self.timestamp = datetime.now()
        self.data = data


class AsyncTool(object):
    """An communication class to base comm tools on."""

    def __init__(self, delimiter=None, no_delimiter=False, timeout=1, **kwargs):
        # type: (str, bool, int, **int) -> None
        """
        Initialize object.

        **One of the following keyword arguments** should be specified as the connection method
        for the device:

        * com - com port of device
        * serial - serial id of device
        * vidpid - VID/PID of USB device
        * host,port - the hostname name or ip and the port on the host

        Optional arguments for both types

        * timeout - default second timeout for operations and retries
        * delimiter - end of data line marker - if None, will look for \n, \r, and \r\n

        Optional additional keyword arguments for serial devices:

        * baud - option baud rate for serial devices, default 115200
        * parity - optional parity for serial devices, default N(one)
        * stopbits - optional stop bits for serial devices, default 1
        * poll_seconds - how often to poll serial device, default 0.1 sec

        :param dict kwargs: keyword arguments, see above
        """
        # Create two double-ended queues for handling rx and tx messages
        # arbitrarily restrict historical size to 100 elements
        self._rx_queue = deque([], maxlen=100)
        self._tx_queue = deque([], maxlen=100)
        self._rx_queue_lock = Lock()
        # Time window in seconds for which rx messages are deemed valid
        self.rx_time_to_live = 10
        self.msg_id = 1

        self.poll_seconds = float(kwargs.get("poll_seconds", 0.1))
        self.timeout = int(timeout)
        if self.timeout > 10:
            log.warning(
                "Unusually long timeout of {0}s found for tool".format(self.timeout)
            )
        self.delimiter = None if delimiter is None else to_bytes(delimiter)
        self.no_delimiter = no_delimiter
        self.message_processor = None
        self.set_online_status = lambda *args: None

        self.is_active = False
        self.is_shutting_down = False
        self.on_connect_methods = []

        self.is_serial = False
        self.com = None
        self._stream = None
        self.rx_buffer = b''

        # Determine if the configuration is for serial or TCP
        comport = kwargs.get("com", None)
        serial_id = kwargs.get("serial", None)
        vidpid = kwargs.get("vidpid", None)
        if comport is not None or vidpid is not None or serial_id is not None:
            # Setup serial port connection details
            self.is_serial = True
            self.port_args = {
                'baudrate': kwargs.get("baud", 115200),
                'parity': kwargs.get("parity", "N"),
                'stopbits': kwargs.get("stopbits", 1),
                'timeout': int(self.timeout * 1000),
                'xonxoff': 0,
                'rtscts': 0,
            }
            if comport is not None:
                self.com = comport
            elif vidpid is not None:
                self.com = 'hwgrep://{0}'.format(vidpid)
            else:
                self.com = 'hwgrep://{0}'.format(serial_id)
        else:
            # Setup TCP connection details
            host = kwargs.get("host", None)
            port = kwargs.get("port", None)
            assert host is not None
            self.host = host
            self.port = port

    def initialize(self):
        """
        Begins the process of trying to connect to the serial/ip tool.
        Connection will run in a loop for the life of the tool

        :return: None
        """
        IoLoop().current().spawn_callback(self.connection)

    def shutdown(self):
        """
        Safely close all open serial/ip connection resources

        :return: None
        """
        # from socket import SHUT_RDWR
        self.is_shutting_down = True

        if self._stream is not None:
            # Use this for gentle shutdown
            # self._stream.socket.shutdown(SHUT_RDWR)
            self._stream.close()

    def set_status_callback(self, callback):
        """
        Set the callback that allows this object to affect the status of a tool

        :param callback:
        :return:
        """
        self.set_online_status = callback
        self.set_online_status(False)

    def set_processor_callback(self, callback):
        """
        Set the callback that this object can use to pass parsed messages for processing

        :param callback:
        :return:
        """
        self.message_processor = callback

    def close_on_error(self):
        """
        Close all serial/ip connection resources in event of a connection
        or communication error to prepare for a new attempt at connection

        :return: None
        """
        self.is_active = False
        self.set_online_status(False)
        try:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
        except Exception as e:
            log.debug(1, "exception closing stream: {0}".format(e))

    def on_close(self):
        """
        Invoked when the TCP stream is closed, whether deliberate or unexpected.

        :return: None
        """
        log.debug(2, "TCP stream closed")
        self.set_online_status(False)

    def run_on_connect(self, method, delay=0):
        """
        Register callback functions to be invoked after all successful connect/reconnect attempts

        :param function method: Handle to the method
        :param int delay: How long to wait after connection to call the method
        :return: None
        """
        self.on_connect_methods.append((method, delay))

    @gen.coroutine
    def connection(self):
        """
        Calls the methods that check for connectivity every 5 seconds.

        Coroutine that runs indefinitely - launched by `.initialize`

        :return: None
        """
        while True:
            if self.is_shutting_down is True:
                break

            if self.is_serial:
                yield self.connection_serial()
            else:
                yield self.connection_ip()
            yield gen.sleep(self.timeout)

    @gen.coroutine
    def connection_serial(self):
        """
        Establish connection to serial port

        Called by `.connection` - if the current connection is not valid, do connect;
         otherwise, return.

        :return: None
        """
        if self._stream is not None:
            if self._stream.is_open:
                return
        log.debug(2, "Connecting to serial port {0}".format(self.com))
        try:
            ser = serial.serial_for_url(self.com, do_not_open=True, **self.port_args)
        except serial.SerialException as e:
            log.exception("Unable to connect to serial port {0}".format(self.com), e)
            self.close_on_error()
            return

        try:
            ser.open()
        except Exception as e:
            log.debug(
                2,
                "Unable to open to serial port {0}. Error: {1}".format(
                    self.com, str(e)
                ),
            )
        else:
            self._stream = ser
            try:
                self.on_connect()
            except Exception as e:
                log.exception(
                    "Unable to start reader for serial port {0}".format(self.com), e
                )
            else:
                self.is_active = True
                self.set_online_status(True)

    @gen.coroutine
    def connection_ip(self):
        """
        Establish TCP connection

        Called by `.connection` - if the current connection is not valid, do connect;
         otherwise, return.

        :return: None
        """
        if self._stream is not None:
            if not self._stream.closed():
                return

        # If IP address is all zeros, skip so that reconnection error messages are avoided
        if self.host == '0.0.0.0':
            return

        log.debug(4, "Connecting to TCP {0}:{1}".format(self.host, self.port))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            _stream = tornado.iostream.IOStream(s)
        except socket.error as e:
            log.exception(
                "Unable to setup socket for TCP {0}:{1}.".format(self.host, self.port),
                e,
            )
            self.close_on_error()
            raise e
        try:
            yield _stream.connect((self.host, self.port))
        except tornado.iostream.StreamClosedError as e:
            log.debug(
                3,
                "Unable to setup socket for TCP {0}:{1}. Errors: '{2}', '{3}'".format(
                    self.host, self.port, str(e), str(e.real_error)
                ),
            )
            self.close_on_error()
        else:
            self._stream = _stream
            try:
                self.on_connect()
            except Exception as e:
                log.exception(
                    "Unable to start reader for TCP {0}:{1}".format(
                        self.host, self.port
                    ),
                    e,
                )
            else:
                self.is_active = True
                self.set_online_status(True)

    def on_connect(self):
        """
        Called after every successful connect/reconnect. If connection is asynchronous,
         spawn the stream reading methods. Then, call all of the 'on_connect' methods
         that were set in `.run_on_connect`

        :return: None
        """
        log.debug(2, 'Async tool connection successful')
        if self.is_serial:
            IoLoop().current().spawn_callback(self.read_serial)
            self._stream.flushOutput()
            self._stream.flushInput()
        else:
            self._stream.read_until_close(streaming_callback=self.read_ip)
            self._stream.set_close_callback(self.on_close)

        for method in self.on_connect_methods:
            IoLoop().current().call_later(method[1], method[0])

    @gen.coroutine
    def write_async(self):
        """
        Callback for asynchronous sending. Launched in `write`. Will send all available data
         and exit

        In the case of an invalid connection, the method returns and will be spawned again in the
         event of a successful reconnect.

        :return: None
        """
        if self._stream is None:
            return

        while self._tx_queue:
            # Send as long as there is data in the queue to be sent
            msg = self._tx_queue.popleft().data
            if self.is_serial:
                try:
                    self._stream.write(msg)
                    self._stream.flushOutput()
                except Exception as e:
                    log.debug(2, "Serial stream write exception: {0}".format(e))
                    self.close_on_error()
            else:
                try:
                    yield self._stream.write(msg)
                except Exception as e:
                    log.debug(2, "TCP stream write exception: {0}".format(e))
                    self.close_on_error()

    @gen.coroutine
    def read_serial(self):
        """
        Indefinite callback for asynchronous serial port reading. Launched in `.on_connect` on
         all successful connect/reconnect attempts. After 'poll_seconds' time elapses, attempt
         to read from the serial port.

        In the case of an invalid serial connection, the method returns and will be spawned again
         in the event of a successful reconnect.

        :return: None
        """
        while True:
            if not self._stream.is_open:
                return

            try:
                data = self._stream.read_all()
            except serial.SerialException:
                log.debug(1, "Serial exception while reading")
                self.close_on_error()
            else:
                if data:
                    log.debug(5, data)
                    self.parse_rx_data(data)

            yield gen.sleep(self.poll_seconds)

    def read_ip(self, raw_data):
        """
        Called when new data appears on the TCP stream. Set as the stream read method in
        `.on_connect`.

        In the case of an invalid serial connection, the method returns and will be spawned again
         in the event of a successful reconnect.

        :param bytes raw_data: Raw data read from the TCP stream for processing
        :return: None
        """
        self.parse_rx_data(raw_data)

    def write(self, data):
        """
        Add a message to the outgoing messages queue

        :param str data: message to be written
        :return:
        """
        self._add_to_tx_queue(data)
        IoLoop().current().spawn_callback(self.write_async)

    def read(self, wait=True, after=None):
        """
        Cleanup rx queue and return oldest message; return None if no data available

        If wait, wait until timeout expires for available data
        If after, message must be received after specified time

        :param bool wait:
        :param datetime after:
        :return: data string or None
        """
        if wait:
            timeout_timer = Timeout(self.timeout)
            while not timeout_timer.expired():
                self._cleanup_rx_queue(after)
                if self._rx_queue:
                    return self._rx_queue.popleft().data
                time.sleep(0.1)
            return None
        else:
            self._cleanup_rx_queue(after)
            if self._rx_queue:
                return self._rx_queue.popleft().data
            else:
                return None

    def parse_rx_data(self, raw_data):
        """
        Parse incoming data into individual data packets

        :param raw_data:
        :return:
        """
        # Convert data to bytes
        data = to_bytes(raw_data)
        self.rx_buffer += data
        messages = []
        if self.no_delimiter:
            # Incoming data is not delimited
            pass
        elif self.delimiter is None:
            for delimiter in [b'\r\n', b'\n', b'\r']:
                if delimiter in data:
                    messages = data.split(delimiter)
                    break
        else:
            if self.delimiter in data:
                messages = data.split(self.delimiter)

        if self.no_delimiter:
            # Incoming data is not delimited
            if self.message_processor is None:
                raise Exception("Message processor required for non-delimited data")
            self.rx_buffer = self.message_processor(self.rx_buffer)
            return
        elif len(messages) == 0:
            # No delimiter found
            messages.append(data)
        else:
            for msg in messages[:-1]:
                # Save parsed messages to the rx queue
                self._add_to_rx_queue(msg)
            if len(messages[:-1]) > 0:
                # Pass the parsed messages to the user message processor
                if self.message_processor is not None:
                    self.message_processor(messages[:-1])

        # Save leftover data for next batch of processing
        self.rx_buffer = messages[-1]

    def _add_to_tx_queue(self, data):
        self._tx_queue.append(AsyncMessage(self.msg_id, data))
        self.msg_id += 1

    def _add_to_rx_queue(self, data):
        with self._rx_queue_lock:
            self._rx_queue.append(AsyncMessage(self.msg_id, data))
            self.msg_id += 1

    def _cleanup_rx_queue(self, after):
        """
        Clean out old messages in rx_queue

        :return: None
        """
        with self._rx_queue_lock:
            no_old_data = [
                msg
                for msg in self._rx_queue
                if (datetime.now() - msg.timestamp).seconds < self.rx_time_to_live
            ]

            if after is not None:
                no_old_data = [msg for msg in no_old_data if msg.timestamp > after]

            self._rx_queue = deque(no_old_data, maxlen=100)

    def clear_rx_queue(self):
        """
        Empty the RX queue

        :return: None
        """
        self._rx_queue.clear()
