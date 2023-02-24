# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import argparse
import base64
import os
import sys
from collections import Counter

import tornado.httpserver
import tornado.web
import tornado.ioloop
from tornado.routing import Rule, PathMatches

import stationexec
from stationexec.executive import Executive
from stationexec.logger import log
from stationexec.station.events import (
    emit_event_non_blocking,
    register_for_event,
    ActionEvents,
    InfoEvents,
    emit_event,
)
from stationexec.toolbox.handlers import ToolRouter
from stationexec.utilities import config
from stationexec.utilities.ioloop_ref import IoLoop
from stationexec.utilities.shutdown import (
    install_signal_handlers,
    stop_loop,
    MAX_WAIT_SECONDS_TILL_SHUTDOWN,
)
from stationexec.web.handlers import (
    ExecutiveUI,
    ExecutiveStaticFileHandler,
    ShutdownHandler,
    ExecutiveTemplateLoader,
    IsAliveHandler,
)

if sys.version_info >= (3, 5):
    import asyncio

from stationexec.version import version as __version__


class Main(object):
    def __init__(self):
        """Set up tornado configuration, set station and instance, and initialize other objects."""
        self._is_shutting_down = False

        parser = argparse.ArgumentParser(description="Station executive")

        parser.add_argument("station", help="station to launch")
        # Optional configuration arguments
        parser.add_argument(
            "-d",
            "--debug",
            help="set log debug level",
            nargs="?",
            const=1,
            default=2,
            type=int,
        )
        parser.add_argument("-a", "--api-logging", help="toggles api logging on and off, 0 for off, 1 for on", default=1, type=int)
        parser.add_argument(
            "-i", "--instance", help="unique station instance designation", default=None
        )
        parser.add_argument("-n", "--name", help="proper name of station", default=None)
        parser.add_argument(
            "-p",
            "--port",
            help="change default HTTP server port",
            default=8888,
            type=int,
        )
        parser.add_argument(
            "-t",
            "--threads",
            help="change default max task parallelism",
            default=10,
            type=int,
        )
        parser.add_argument(
            "--dev", help="launch station in development mode", action="store_true"
        )
        parser.add_argument(
            "--alt",
            help="alternate home directory",
            type=str,
            required=False,
            default=None,
        )
        # Optional arguments can be provided by file if desired
        parser.add_argument(
            "-f", "--file", help="config file name or path", default=None
        )

        parser.add_argument(
            "--update-station-info",
            help="Updates the station info",
            action="store_true",
            required=False
        )
        input_arguments = parser.parse_args(sys.argv)

        if input_arguments.alt:
            config._set_alternate_app_path(input_arguments.alt)

        if os.name == "nt" and sys.version_info >= (3, 8):
            # Python 3.8 changed default event loop policy to Windows incompatible Proactor loop - fix here
            asyncio.DefaultEventLoopPolicy = asyncio.WindowsSelectorEventLoopPolicy

        # Enable using tornado/asyncio main loop in multiple threads
        if sys.version_info >= (3, 5):
            from tornado.platform.asyncio import AnyThreadEventLoopPolicy

            asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())

        IoLoop().init()

        # Print any log messages in __init__ directly - logger is initialized below in Executive
        # Hold any Storage or Retrieval event registrations until after Executive is created

        # Ensure the system installation directory is setup correctly
        config.set_station_identity(input_arguments.station)
        config.verify_paths_exist()

        # System variable initialization
        self.web_server = None
        config_data = config.merge_config_data(input_arguments)

        self._executive = Executive(config_data)

        register_for_event("main", ActionEvents.SHUTDOWN, self.shutdown)

        self.tornado_settings = {
            "static_url_prefix": "/static/",
            "static_path": "auto",
            "static_handler_class": ExecutiveStaticFileHandler,
            "static_handler_args": {"debug": self._executive.get_cfg("debug", -1)},
            "template_loader": ExecutiveTemplateLoader(),
            "cookie_secret": base64.b64encode(os.urandom(64)),
        }

        if int(self._executive.get_cfg("debug", -1)) > -1:
            self.tornado_settings["compiled_template_cache"] = False
            self.tornado_settings["static_hash_cache"] = False
            self.tornado_settings["serve_traceback"] = True

        self.tornado_endpoints = [
            (r"/", ExecutiveUI, {"get_web_info": self._executive.get_web_info}),
            (
                r"/ui/([A-Za-z0-9\_]+)",
                ExecutiveUI,
                {"get_web_info": self._executive.get_web_info},
            ),
            (
                r"/ui/([A-Za-z0-9\_]+)/([A-Za-z0-9\_]+)",
                ExecutiveUI,
                {"get_web_info": self._executive.get_web_info},
            ),
            (r"/shutdown", ShutdownHandler),
            (r"/isalive", IsAliveHandler),
        ]

    def start(self):
        self._executive.initialize()
        self.tornado_endpoints.extend(self._executive.get_endpoints())

        install_signal_handlers(self)

        # Check if there are any duplicate endpoints declared
        endpoint_list = [endpoint[0] for endpoint in self.tornado_endpoints]
        duplicate_check = Counter(endpoint_list)
        duplicates = [item for item in duplicate_check if duplicate_check[item] > 1]
        if len(duplicates) != 0:
            log.warning("Duplicate endpoints detected in setup")
            for endpoint in duplicates:
                log.warning("   " + endpoint)
            sys.exit(1)

        # Create the application, then start a single threaded HTTP server
        application = tornado.web.Application(
            self.tornado_endpoints, **self.tornado_settings
        )
        # Add the custom router to handle tool-related routes
        application.add_handlers(
            ".*", [Rule(PathMatches("/tool.*"), ToolRouter(application))]
        )
        (web_port, ssl_config) = self._executive.get_web_info()
        self.web_server = tornado.httpserver.HTTPServer(
            application, ssl_options=ssl_config
        )

        if (
            web_port <= 1024 and os.name != "nt" and os.geteuid() != 0
        ):  # nt means Windows and euid == sudo
            log.error(
                "only root can use ports lower than 1024 on Linux "
                "(am configured for port {0})".format(web_port)
            )
            emit_event(ActionEvents.SHUTDOWN)
            sys.exit(1)

        try:
            self.web_server.listen(web_port)
        except Exception as e:
            log.exception(
                "Unable to bind to port: '{0}'. Port probably in use.".format(web_port),
                e,
            )
            emit_event(ActionEvents.SHUTDOWN)
            sys.exit(1)

        log.info("Station Executive v{0}".format(stationexec.__version__))
        log.info(
            "StationExec server v{1} started on {3} port {0}, pid {2}".format(
                web_port,
                tornado.version,
                os.getpid(),
                "http" if ssl_config is None else "https",
            )
        )
        emit_event_non_blocking(
            InfoEvents.SERVER_STARTED,
            {
                "port": web_port,
                "ssl": ssl_config is not None,
                "pid": os.getpid(),
                "server_version": tornado.version,
            },
        )

        IoLoop().current().start()
        log.info(
            "Exited StationExec server v{1} on {3} port {0}, pid {2}".format(
                web_port,
                tornado.version,
                os.getpid(),
                "http" if ssl_config is None else "https",
            )
        )

    def shutdown(self, **kwargs):
        emit_event(InfoEvents.SHUTTING_DOWN)
        if not self._is_shutting_down:
            self._is_shutting_down = True
            log.warning("StationExec shutting down")
            io_loop = IoLoop().current()

            log.info("Stopping HTTP server")
            io_loop.add_callback(self.web_server.stop)
            log.info(
                "      Will shutdown within {0} seconds ...".format(
                    MAX_WAIT_SECONDS_TILL_SHUTDOWN
                )
            )
            io_loop.call_later(MAX_WAIT_SECONDS_TILL_SHUTDOWN, stop_loop)
