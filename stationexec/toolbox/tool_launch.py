# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""
The ToolLaunch class is purely a developer-focused module. The methods are intended
to make development and debugging of tools in a context similar to deployment
much simpler.

This is instantiated and launched from the cli tool launcher utility
"""
import os
import signal
import sys
import threading
import webbrowser

from stationexec.logger import log
from stationexec.logger.logger import Logger
from stationexec.station.events import emit_event, register_for_event, InfoEvents, ActionEvents
from stationexec.toolbox.toolbox import verify_status_loop
from stationexec.utilities.ioloop_ref import IoLoop
from stationexec.utilities.uuidstr import get_uuid
from stationexec.web.handlers import ExecutiveHandler, ExecutiveTemplateLoader, ExecutiveStaticFileHandler
from stationexec.web.websocket import SocketManager, StationSocket
from tornado import web

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty

if sys.version_info >= (3, 5):
    import asyncio


# TODO Consider loading global configurations here - it would be handy for launching db tools


class ToolLaunch(object):
    """ Helper class to ease tool development """

    def __init__(self):
        self.tool_id = None
        self.tool_name = None
        self.tool_type = None

        self.obj = None
        self.tool_instance = None
        self.io_loop = None
        self.web_app = None
        self.status_loop = verify_status_loop

        self._is_shutting_down = False
        self.command_queue = Queue()
        self._cmd_thread_id = None

        if os.name == "nt" and sys.version_info >= (3, 8):
            # Python 3.8 changed default event loop policy to Windows incompatible Proactor loop - fix here
            asyncio.DefaultEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy

        # Enable using tornado/asyncio main loop in multiple threads
        if sys.version_info >= (3, 5):
            from tornado.platform.asyncio import AnyThreadEventLoopPolicy
            asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

        IoLoop().init()

        sig_list = [signal.SIGTERM, signal.SIGINT]
        # SIGQUIT only supported on Linux systems
        if os.name != "nt":
            sig_list.append(signal.SIGQUIT)
        else:
            sig_list.append(signal.SIGBREAK)
        for sig_id in sig_list:
            signal.signal(sig_id, self.sig_handler)

        self.port = 8888
        # Load the web socket handler and register to listen for
        # messages to send to the ui sockets.
        self.socket_manager = SocketManager()
        self.socket_manager.initialize()

        Logger().init(debug=8, prefix="tool_launcher")

        register_for_event("ToolLaunch", ActionEvents.SHUTDOWN, self.shutdown)

    def sig_handler(self, signum, frame):
        self.shutdown()

    def build_tool_dict(self, tool_type, name, tool_id, configurations):
        """
        Build the correctly formatted dictionary to configure the tool completely
        with this call.

        :param tool_type: name of the tool folder and file
        :param name: display name for the tool - the friendly name
        :param tool_id: the unique identifier that is used to reference the tool
        :param dict configurations: all required configuration values

        :return: complete tool configuration data
        :rtype: dict
        """
        if type(configurations) is not dict:
            raise RuntimeError("'configurations' argument must be dictionary of config items")

        configurations["tool_type"] = tool_type
        configurations["name"] = name
        configurations["tool_id"] = tool_id

        configurations["debug"] = configurations.get("debug", 2)
        configurations["dev"] = configurations.get("dev", False)

        configurations["_tool_status_changed"] = self.tool_status_listener
        configurations["_register_for_event"] = register_for_event
        configurations["_emit_event"] = emit_event

        self.tool_type = tool_type
        self.tool_name = name
        self.tool_id = tool_id

        return configurations

    def tool_setup(self, tool_object, tool_config_dictionary):
        """
        Prepare the tool object by instantiating with the proper config data

        :param class tool_object: the un-instantiated tool class
        :param dict tool_config_dictionary: output from `build_tool_dict`

        :return: None
        """
        log.info("Setting up tool {0}".format(tool_config_dictionary.get("tool_id")))
        self.tool_instance = tool_config_dictionary
        self.obj = tool_object(**self.tool_instance)
        self.tool_instance["object"] = self.obj

    @staticmethod
    def tool_command_build(delay, command, *args, **kwargs):
        """
        Helper function to build a command tuple. Commands are optional helpers
        that can call any tool function at some later point in the future. This
        is helpful if you want to debug a function without dealing with
        the web server or ui.

        :param float delay: how many seconds to wait before invoking
        :param method command: the method to invoke
        :param list args: un-named arguments
        :param dict kwargs: keyword arguments

        :return: formatted command request
        :rtype: tuple
        """
        log.info("Will run '{0}' after {1} seconds".format(command.__name__, delay))
        cmd = (delay, lambda: command(*args, **kwargs))
        return cmd

    def setup_tool_server(self, port=8888):
        """
        Create a web server at specified port to serve the tool web page and
        allow tool control messages to be received.

        :param int port: web port to serve on

        :return: None
        """
        settings = {
            "static_url_prefix": "/static/",
            "static_path": "auto",
            "static_handler_class": ExecutiveStaticFileHandler,
            "static_handler_args": {"debug": 2},

            "template_loader": ExecutiveTemplateLoader(),

            "compiled_template_cache": False,
            "static_hash_cache": False,
            "serve_traceback": True,

            "cookie_secret": "tool_utility_run",
        }
        endpoints = [
            (r"/", MainHandler, {"util": self}),
            (r"/tool/ui/([A-Za-z0-9\_]+)", ToolPage, {"util": self}),
            (r"/shutdown", ShutdownHandler, {"util": self}),
            (r"/socket", StationSocket, {"socket_manager": self.socket_manager, "stationuuid": get_uuid()})
        ]
        endpoints.extend(self.obj.get_endpoints())
        self.web_app = web.Application(endpoints, **settings)
        self.web_app.listen(port)
        log.info("Access main tool page at http://localhost:{0}".format(port))

    def tool_status_listener(self, **kwargs):
        """
        Log and process incoming status updates from the tools

        :return:
        """
        # Tell UI to refresh tool status
        if self.obj is None:
            return

        emit_event(InfoEvents.TOOL_UPDATE, {
            "source": "Toolbox",
            "status": self.obj.get_status()
        })

    def tool_run(self, port=8888, browser=False, polling_period=5):
        """
        Start the tool running. Schedules all (if any) commands defined above to run at the
        appropriate times. Starts a server at the port requested (default port is 8888),
        and invokes the tool in a similar context to what it runs in during deployment. With
        the server, you can access the tool UI at localhost:<port> and use that to send commands
        to the tool.

        Navigate to localhost:<port>/shutdown to shutdown.

        :param int port: Port to start server on
        :param bool browser: Whether to open new browser tab
        :param int polling_period: Period in seconds between checking for connectivity

        :return: None
        """
        self.port = port
        self.setup_tool_server(port)

        log.info("Initializing tool")

        ret = self.obj.initialize()
        if ret is True or ret is None:
            self.obj.set_online()
        else:
            self.obj.set_offline()

        register_for_event("ToolLaunch", InfoEvents.TOOL_COMMAND, self.ui_command)

        log.info("Launching status checking loop")
        self.io_loop = IoLoop().current()
        self.io_loop.spawn_callback(
            lambda: self.status_loop(self.tool_id, self.tool_instance["object"], polling_period))

        if browser:
            register_for_event("ToolLaunch", InfoEvents.SERVER_STARTED, self.on_startup)
            self.io_loop.spawn_callback(emit_event, InfoEvents.SERVER_STARTED)

        self.io_loop.start()
        log.info("Exiting")

    def on_startup(self, **kwargs):
        webbrowser.open("http://localhost:8888", new=2)

    def shutdown(self, **kwargs):
        self._is_shutting_down = True
        self.obj.shutdown()
        if self.io_loop:
            self.io_loop.stop()

    # ----------------------------------------------------------------------------------------

    def _ui_command(self):
        """
        Run as a looping thread; launched by ui_command

        Process incoming messages from self.command_queue (populated in ui_command), which are
        messages incoming from actions on the UI that pertain to tools and stations. The loop
        checks out tools to complete tool commands (commands will not be performed if the tool
        is offline or in use)
        """
        while not self._is_shutting_down:
            messages = {}
            try:
                while True:
                    msg = self.command_queue.get(True, 0.1)
                    if msg[0] not in messages:
                        messages[msg[0]] = []
                    messages[msg[0]].append(msg)
            except Empty:
                if messages == {}:
                    continue

            to_delete = []
            message_keys = list(messages.keys())
            for source in message_keys:
                to_delete.append(source)
                if self._is_shutting_down:
                    break

                _, obj_id = source.split(".", 1)
                for command in messages[source]:
                    if self._is_shutting_down:
                        break
                    _source_id, kwargs = command
                    try:
                        obj_command = kwargs.pop("command")
                    except Exception as e:
                        log.debug(1, "Exception in on_ui_command arguments {0}: {1}".format(
                            kwargs, e))
                        continue
                    log.debug(3, "ui_command - " + obj_id + ": " + obj_command)
                    try:
                        self.obj.on_ui_command(obj_command, **kwargs)
                    except Exception as e:
                        log.debug(1, "Exception in 'on_ui_command' calling '{0}' of "
                                     "'{1}': {2}".format(obj_command, obj_id, e))
            for source in to_delete:
                del messages[source]

    def ui_command(self, source, **kwargs):
        """
        Put ui command in the processing queue

        Launches _ui_command thread loop if it is not running

        :param str source: source of the event
        :param dict kwargs: Event data dictionary
                            data:
                            target:
                            cmd: JSON string arguments from UI
        :return: None
        """
        target = kwargs.get("target")
        cmd = kwargs.get("arguments")
        if self._cmd_thread_id is None:
            self._cmd_thread_id = threading.Thread(target=self._ui_command)
            self._cmd_thread_id.start()
        self.command_queue.put((target, cmd))


class MainHandler(ExecutiveHandler):
    """ Serve tool UI """
    util = None

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        self.util = kwargs["util"]

    def get(self):
        websocket = "{0}/socket".format(self.util.port)
        websockettype = "ws"

        self.render("ui/html/tool_util.html", tool_name=self.util.tool_name, tool_id=self.util.tool_id,
                    websocket=websocket, websockettype=websockettype)


class ToolPage(ExecutiveHandler):
    util = None

    def initialize(self, **kwargs):
        self.util = kwargs["util"]

    def get(self, tool_id):
        self.render("tool/{0}/index.html".format(self.util.tool_type), tool_id=self.util.tool_id)


class ShutdownHandler(ExecutiveHandler):
    """ Exit tool context """
    util = None

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        self.util = kwargs["util"]

    def post(self):
        self.util.io_loop.call_later(1, self.util.shutdown)
