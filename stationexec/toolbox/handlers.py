# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

# noinspection PyPackageRequirements
import simplejson
from stationexec.logger import log
from stationexec.station.events import emit_event, InfoEvents
from stationexec.web.handlers import ExecutiveHandler
from tornado.routing import Router
from tornado.web import HTTPError

_get_tool_routes_ = None


def _set_tool_routes(callback):
    global _get_tool_routes_
    if _get_tool_routes_ is None:
        _get_tool_routes_ = callback


class ToolRouteError(ExecutiveHandler):
    def initialize(self, *args, **kwargs):
        pass

    def get(self, *args, **kwargs):
        self.set_status(404)
        self.write("404: Not Found")

    def post(self, *args, **kwargs):
        self.set_status(404)
        self.write("404: Not Found")


class ToolRouter(Router):
    def __init__(self, _app):
        self.app = _app

    def find_handler(self, request, **kwargs):
        global _get_tool_routes_
        path_args = []
        path_kwargs = {}
        target_kwargs = {}
        if _get_tool_routes_ is None:
            handler = ToolRouteError
        else:
            endpoints = _get_tool_routes_()
            if request.remote_ip not in ["::1", "localhost", "127.0.0.1"]:
                log.debug(
                    10,
                    "Request received from {0}: {1}".format(request.remote_ip, request),
                )

            handler = None
            for endpoint in endpoints:
                params = endpoint.matcher.match(request)
                if isinstance(params, dict):
                    handler = endpoint.target
                    target_kwargs = endpoint.target_kwargs
                    path_args = params.get("path_args", [])
                    path_kwargs = params.get("path_kwargs", {})
                    break
            if handler is None:
                handler = ToolRouteError
        return self.app.get_handler_delegate(
            request,
            handler,
            target_kwargs=target_kwargs,
            path_args=path_args,
            path_kwargs=path_kwargs,
        )


class ToolCommand(ExecutiveHandler):
    def post(self):
        """
        Send a command to a tool. Command to tool is placed in the JSON body.
         Command contains the target (tool_id) and command with arguments.
        """
        tool_id = self.json_args.get("target")
        cmd = self.json_args.get("arguments")
        emit_event(
            InfoEvents.TOOL_COMMAND,
            {"source": "handler.ToolCommand", "target": tool_id, "cmd": cmd},
        )


class ToolboxStatus(ExecutiveHandler):
    _get_status = None

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        self._get_status = kwargs["status"]

    def get(self, parameter=None):
        """Write JSON encoded string containing status of all tools"""
        self.set_header("Content-Type", "application/json")
        self.set_header(
            "Cache-Control", "no-store, no-cache, must-revalidate, max-age=0"
        )
        self.write(simplejson.dumps(self._get_status()))


class ToolUI(ExecutiveHandler):
    _tool_type_map = None

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        self._tool_type_map = kwargs["tool_type_map"]

    def get(self, tool_id=None):
        """Render and display requested UI of an available tool"""
        try:
            tool_type = self._tool_type_map()[tool_id]
            self.render("tool/{0}/index.html".format(tool_type), tool_id=tool_id)
        except HTTPError as e:
            log.exception("failed to render UI for tool '{0}'".format(tool_id), e)
            raise
        except Exception as e:
            log.exception("failed to render UI for tool '{0}'".format(tool_id), e)
