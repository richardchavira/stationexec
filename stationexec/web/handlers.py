# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import os

import simplejson
from stationexec.logger import log
from stationexec.station.events import emit_event_non_blocking, ActionEvents
from stationexec.toolbox.tool_utilities import get_tool_path
from stationexec.utilities import config, path_utils
from tornado.template import BaseLoader, Template
from tornado.web import HTTPError, RequestHandler, StaticFileHandler


class ExecutiveHandler(RequestHandler):
    """Adds additional functionality to RequestHandler."""
    json_args = None  # type: dict

    def prepare(self):
        """
        Automatically decode any JSON arguments send to the endpoint, into a variable named
        json_args.
        """
        if ("Content-Type" in self.request.headers and
                self.request.headers["Content-Type"].startswith("application/json")):
            self.json_args = simplejson.loads(self.request.body)
        else:
            self.json_args = {}

    def on_finish(self):
        pass

    def data_received(self, chunk):
        log.error("received,ignored unexpected websocket data: {0}".format(chunk))


class ShutdownHandler(ExecutiveHandler):
    def post(self):
        """Request the Station Executive to shut down"""
        log.info("Shutting down station.")
        emit_event_non_blocking(ActionEvents.SHUTDOWN)


class IsAliveHandler(ExecutiveHandler):
    def get(self):
        """Request the Station Executive to shut down"""
        self.write("True")


class ExecutiveUI(ExecutiveHandler):
    web_info = None

    def initialize(self, **kwargs):
        """Prepare to handle endpoint operation"""
        self.web_info = kwargs["get_web_info"]

    def get(self, url=None, children=None):
        """Serve main Station Executive web user interface"""
        port, ssl = self.web_info()
        websocket = "{0}/socket".format(port)
        websockettype = "ws" if ssl is None else "wss"

        self.render("ui/html/index.html", websocket=websocket, websockettype=websockettype)


class ExecutiveStaticFileHandler(StaticFileHandler):
    """
    Subclass to serve static files from the application.
    See Tornado source code for subclassing notes:
    https://fburl.com/pxn4y5pc

    URLs of the form /static/filename map to the base/ui folder

    URLs of the form /static/station/filename map to the station/<current station type>/ui folder

    URLs of the form /static/tool/<toolname>/filename map tp the tool/<toolname>/ui folder
    """
    module_path = None  # type: str
    internal_tool_path = None  # type: str
    tool_path = None  # type: str
    station_path = None  # type: str
    main_ui_folder = None  # type: str
    default_ui_folder = None  # type: str
    debug = None  # type: bool
    is_zip = ".zip" in os.path.abspath(__file__)  # type: bool

    # noinspection PyMethodOverriding
    def initialize(self, debug, **kwargs):
        """Prepare to handle endpoint operation"""
        super(ExecutiveStaticFileHandler, self).initialize(**kwargs)
        self.module_path = config.get_all_paths()["module_root"]
        self.internal_tool_path = config.get_all_paths()["tools_internal"]
        self.tool_path = config.get_all_paths()["tools_external"]
        self.station_path = config.get_all_paths()["station"]
        self.main_ui_folder = config.get_all_paths()["ui_folder"]
        self.default_ui_folder = config.get_all_paths()["default_ui_folder"]
        self.debug = debug

    def data_received(self, chunk):
        log.error("ExecutiveStaticFileHandler received, ignored websocket data")

    def parse_url_path(self, url_path):
        return url_path

    def set_extra_headers(self, path):
        # Disable static file caching
        if self.debug > -1:
            self.set_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")

    @classmethod
    def get_content(cls, abspath, start=None, end=None):
        return path_utils.get_file_content(abspath)
        # else:
        #    super(ExecutiveStaticFileHandler, cls).get_content(abspath, start, end)

    @classmethod
    def get_absolute_path(cls, _root, path):
        """Override base absolute path behavior"""
        return path

    def get_content_size(self):
        if self.is_zip:
            return len(self.get_content(self.absolute_path))
        else:
            return super(ExecutiveStaticFileHandler, self).get_content_size()

    def get_modified_time(self):
        if self.is_zip:
            return None
        else:
            return super(ExecutiveStaticFileHandler, self).get_modified_time()

    def validate_absolute_path(self, _root, absolute_path):
        """Custom path resolution to fit project folder structure"""
        relative_path = absolute_path

        # URLs explicitly use /, not the os separator
        folders = relative_path.lstrip("/").split("/")

        # do not allow .. anywhere in path!!
        if ".." in folders:
            raise HTTPError(404)

        try:
            if folders[0] == "station":
                if folders[1] == "static":
                    file_path = os.path.join(self.station_path, "static", *folders[2:])
                else:
                    file_path = os.path.join(self.station_path, "ui", *folders[1:])
            elif folders[0] == "tool":
                if folders[1] == "static":
                    tool_path = get_tool_path(folders[2])
                    file_path = os.path.join(tool_path, "static", *folders[3:])
                else:
                    tool_path = get_tool_path(folders[1])
                    file_path = os.path.join(tool_path, "ui", *folders[2:])
            else:
                file_path = os.path.join(self.main_ui_folder, *folders[0:])
                if not path_utils.exists(file_path):
                    # If main is an alternate ui path and file isn't there, try the default folder
                    file_path = os.path.join(self.default_ui_folder, *folders[0:])
        except Exception as e:
            log.exception("failed to form path", e)
            raise HTTPError(404)

        log.debug(10, "Calculated static file {0}".format(file_path))

        if path_utils.exists(file_path):
            return file_path
        else:
            raise HTTPError(404)


class ExecutiveTemplateLoader(BaseLoader):
    """
    Subclass to serve templates.
    See Tornado source code for subclassing notes:
    https://fburl.com/irmhelhj
    """

    def __init__(self, **kwargs):
        """Store custom arguments and call base class"""
        super(ExecutiveTemplateLoader, self).__init__(**kwargs)
        self.module_path = config.get_all_paths()["module_root"]
        self.internal_tool_path = config.get_all_paths()["tools_internal"]
        self.tool_path = config.get_all_paths()["tools_external"]
        self.station_path = config.get_all_paths()["station"]
        self.main_ui_folder = config.get_all_paths()["ui_folder"]
        self.default_ui_folder = config.get_all_paths()["default_ui_folder"]
        self.is_zip = ".zip" in os.path.abspath(__file__)

    def resolve_path(self, name, parent_path=None):
        """Custom path resolution to fit project folder structure"""
        # URLs explicitly use /, not the os separator
        folders = name.lstrip("/").split("/")
        if folders[0] == "ui":
            folders.pop(0)

        # do not allow .. anywhere in path!!
        if ".." in folders:
            raise HTTPError(404)

        # templates must be .html files
        if os.path.splitext(folders[-1])[1] != ".html":
            # Unknown file type requested
            raise HTTPError(404)

        try:
            if folders[0] == "station":
                if folders[1] == "static":
                    file_path = os.path.join(self.station_path, "static", *folders[2:])
                else:
                    file_path = os.path.join(self.station_path, "ui", *folders[1:])
            elif folders[0] == "tool":
                if folders[1] == "static":
                    tool_path = get_tool_path(folders[2])
                    file_path = os.path.join(tool_path, "static", *folders[3:])
                else:
                    tool_path = get_tool_path(folders[1])
                    file_path = os.path.join(tool_path, "ui", *folders[2:])
            else:
                file_path = os.path.join(self.main_ui_folder, *folders[0:])
                if not path_utils.exists(file_path):
                    # If main is an alternate ui path and file isn't there, try the default folder
                    file_path = os.path.join(self.default_ui_folder, *folders[0:])
        except Exception as e:
            log.exception("failed to form path", e)
            raise HTTPError(404)

        log.debug(10, "Calculated static file {0}".format(file_path))

        if path_utils.exists(file_path):
            return file_path
        else:
            raise HTTPError(404)

    def _create_template(self, name):
        """Override template load behavior and return a template from our custom path"""
        path = name
        if self.is_zip:
            content = path_utils.get_file_content(path)
        else:
            with open(path, "rb") as f:
                content = f.read()
        template = Template(content, name=name, loader=self)
        return template
