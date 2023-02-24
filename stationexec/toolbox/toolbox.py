# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

import time
from functools import wraps, partial

from addict import Dict as Addict
from stationexec.logger import log
from stationexec.station.events import emit_event, register_for_event, InfoEvents, ActionEvents, unregister_from_event
from stationexec.toolbox.handlers import ToolCommand, ToolboxStatus, ToolUI, _set_tool_routes
from stationexec.toolbox.tool import Tool
from stationexec.toolbox.tool_utilities import load_tool_object
from stationexec.utilities import config
from stationexec.utilities.exceptions import ToolExistsException, ToolNotExistsException, \
    ToolUnavailableException, ToolInUseException
from stationexec.utilities.ioloop_ref import IoLoop
from tornado import gen
from tornado.routing import Rule, PathMatches


REQUIRED_TOOLS = [
    {
        'id': 'station_storage',
        'name': 'Station Storage',
    },
    {
        'id': 'dut',
        'name': 'DUT',
        'configurations': {
            'dev': True,
            'id_patterns': ''
        }
    },
    {
        'id': 'user_input',
        'name': 'User Input'
    }
]

def get_tools(*tools):
    """
    Decorator to be used to checkout tools into a function. Intended for use in station.py
    primarily. Add the decorator on top of a function with all of the required tool ids as the
    arguments and the tool references will be passed in an object to the first argument in your
    function. If the tool is offline or in use, an error will be logged stating so and the
    function will not be called. When the

    e.g. ::

        @get_tools("camera", "robot")
        def function_needing_tools(tools, other_arg):
            tools.camera.perform_action()
            tools.robot.perform_other_action()

    """

    def decorator(func):
        @wraps(func)
        def inner(*args, **kwargs):
            tool_objects = Addict()
            ret = None
            for tool in tools:
                if get_tools.checkout_tool is None:
                    return
                try:
                    tool_objects[tool] = get_tools.checkout_tool(
                        f"toolbox.get_tools:{func.__name__}", tool)
                except (ToolUnavailableException, ToolInUseException):
                    log.error(f"Cannot checkout tool '{tool}' at this time")
                    raise ToolUnavailableException(f"Cannot checkout tool '{tool}' at this time")
            if len(tool_objects) == len(tools):
                # Only execute if all required tools were checked out
                try:
                    ret = func(*args, tools=tool_objects, **kwargs)
                except Exception as e:
                    # Catch the exception, then continue through to return tools
                    log.exception(f"Exception thrown by function '{func.__name__}'\
                                  wrapped by 'get_tools'", e)
            else:
                log.warning(f"Could not check out all tools - '{func.__name__}' will not run")
            for tool in tools:
                if get_tools.return_tool is None:
                    return
                try:
                    get_tools.return_tool(f"toolbox.get_tools:{func.__name__}",
                                          tool_objects[tool])
                except Exception:
                    continue
            return ret

        return inner

    return decorator


get_tools.checkout_tool = None
get_tools.return_tool = None


class ToolBox(object):
    # How often do tool status checks happen, in seconds

    def __init__(self, debug, dev, db_data):
        """
        Init the Toolbox object.

        :param int debug:
        :param bool dev:
        :param dict db_data:
        """
        self._debug = debug
        self._dev = dev

        # A dictionary holding all tools
        self.tools = {}
        self.db_tools = {}
        self.tool_usage_times = {}

        self.system_db_config = Addict(db_data)
        system_paths = config.get_all_paths()
        self._manifest_data = config.load_config(system_paths["tool_manifest"])
        self._tool_events = {}

        tool_types = [tool["tool_type"] for tool in self._manifest_data]
        for tool in REQUIRED_TOOLS:
            if tool['id'] not in tool_types: 
                self._add_tool(tool)

        self.load_tool_modules(self._manifest_data)

        # Set callbacks for tool getting decorator
        get_tools.checkout_tool = self.checkout_tool
        get_tools.return_tool = self.return_tool

        register_for_event("toolbox", InfoEvents.UI_LOADED, self.tool_status_listener)
        register_for_event("toolbox", ActionEvents.RELOAD_TOOL_MANIFEST, self.reload_tool_manifest)

        self._endpoints = None
        self._tools_reloaded = False
        _set_tool_routes(self.get_endpoints)

    def load_tool_modules(self, tool_info, reload=False):
        """
        Load modules for tools into memory

        :return:
        """
        for tool in tool_info:
            tool = Addict(tool)
            try:
                if "tool_type" not in tool:
                    raise Exception(f"No tool type specified for tool \
                                    definition in manifest:{tool}")
                obj = self.create_tool(tool, reload)
                self.tools[tool.tool_id] = obj
            except Exception as e:
                log.exception(f"Failed to initialize tool '{tool.tool_id}'", e)
                pass

    def initialize(self):
        """
        Initialize object

        :return: None
        """
        self.initialize_tools(self.tools)

    def initialize_tools(self, tools):
        for tool_id in tools:
            tool = tools[tool_id]
            try:
                ret = tool.initialize()
                if tool._manual_status_change:
                    # User deliberately set the status of the tool using set_online
                    #  or set_offline - leave the status alone and trust the user
                    tool._manual_status_change = False
                elif ret is False:
                    # User explicitly returned False - this means the tool should be
                    #  set to offline
                    tool.set_offline(manual=False)
                elif ret is True or ret is None:
                    # User either returned True or nothing - set the tool online
                    tool.set_online(manual=False)
                else:
                    # User returned something unexpected - set tool offline
                    tool.set_offline(manual=False)
            except Exception as e:
                log.exception(f"Exception while initializing tool {tool.tool_id}: {str(e)}", e)
                tool.set_offline()

            poll_period = tool.status_polling_period
            try:
                IoLoop().current().spawn_callback(verify_status_loop, tool_id, tool, poll_period)
            except Exception as e:
                log.exception(f"Unable to start '{tool_id}' status loop: {str(e)}", e)
        self._tools_reloaded = True

    def create_tool(self, tool_cfg, reload=False):
        # type: (Addict, bool) -> Tool
        """
        Create an instance of a named tool. The tool_type name must exist in the tools/ directory.
        The name is displayed to users. The tool_id must be a unique name. Configurations is a dict
        passed to the tool to configure it, and varies by tool.

        :param dict tool_cfg: dictionary containing tool_type, name, tool_id,
        configurations keys passed to tool driver
        :param bool reload: whether to force the tool module to be reloaded
        :raise ToolExistsException: if a tool of the same tool_id already exists
        """
        name, class_name, display_name = config.format_name(tool_cfg.tool_type)
        if "tool_id" not in tool_cfg:
            log.warning(f"No tool_id specified for tool '{name}' in manifest - \
                        auto assigning id of '{name}_1'")
            tool_cfg.tool_id = f"{name}_1"
        if "name" not in tool_cfg:
            tool_cfg.name = display_name

        if tool_cfg.tool_id in self.tools:
            raise ToolExistsException(
                f"attempt to create tool '{tool_cfg.tool_id}' which already exists")

        # Tool 'static' URL to access static folder would conflict with tool called static
        if name == "static":
            raise Exception("Unable to load Tool 'static' - this is a reserved name")

        # Gather identifying data about this tool
        configs = {
            "tool_type": tool_cfg.tool_type,
            "name": tool_cfg.name,
            "tool_id": tool_cfg.tool_id,
            "debug": self._debug,
            "dev": self._dev,
            "db_config": self.system_db_config,
            "_tool_status_changed": self.tool_status_listener,
            "_register_for_event": partial(self._register_for_event, tool_cfg.tool_id),
            "_emit_event": emit_event
        }
        configs.update(tool_cfg.configurations)

        log.debug(3, f"Creating tool {tool_cfg.name} - {tool_cfg.tool_id} ({tool_cfg.tool_type})")

        # Load tool module into memory
        module = load_tool_object(tool_cfg.tool_type, reload_mod=reload, location=configs.get("location"))

        version = "unknown" if not hasattr(module, "version") else module.version
        log.info(f"Loaded tool {tool_cfg.name} - {tool_cfg.tool_id} \
                ({tool_cfg.tool_type}) v{version}")
        configs["version"] = version

        # Return instance of tool driver
        return getattr(module, class_name)(**configs)  # type: Tool

    def shutdown(self):
        """
        Cleanup this and lower objects and prepare to exit.

        :return: None
        """
        for tool_id in self.tools.keys():
            log.debug(4, f"shutting down tool object '{tool_id}'")
            try:
                self.tools[tool_id].is_shutting_down = True
                self.tools[tool_id].shutdown()
                self.tools[tool_id].set_offline()
            except Exception as e:
                log.debug(4, f"Error while cleaning up '{tool_id}': {str(e)}")

    def _register_for_event(self, tool_id, source, event_enum, callback):
        if tool_id not in self._tool_events:
            self._tool_events[tool_id] = []
        self._tool_events[tool_id].append((source, event_enum, callback))
        register_for_event(source, event_enum, callback)

    def reload_tool_manifest(self, manifest=None, **kwargs):
        # TODO Check if tools are in-use before un/reloading
        if manifest is None:
            self._manifest_data = config.load_config(config.get_all_paths()["tool_manifest"])
            self._reload_tools(self._manifest_data)
        else:
            self._reload_tools_new_manifest(manifest)

    def _reload_tools_new_manifest(self, manifest):
        if manifest is None or manifest == {}:
            return

        # Convert the manifest lists into dicts with the IDs as keys; assign a default if
        # ID doesn't exist;
        #  Ignore station_storage - not allowed to reload that tool
        old_manifest = {self._get_tool_id_from_manifest(t): t for t in self._manifest_data}
        #                if self._get_tool_id_from_manifest(t) != "station_storage"}
        new_manifest = {self._get_tool_id_from_manifest(t): t for t in manifest}
        #                if self._get_tool_id_from_manifest(t) != "station_storage"}

        old_tools = list(old_manifest.keys())
        new_tools = list(new_manifest.keys())

        old_tools_to_unload = list(set(old_tools) - set(new_tools))
        new_tools_to_load = list(set(new_tools) - set(old_tools))
        same_tools = list(set(new_tools).intersection(old_tools))
        same_tools_to_reload = [t for t in same_tools if old_manifest[t] != new_manifest[t]]
        untouched_tools = list(set(same_tools) - set(same_tools_to_reload))

        # Unload unused tools
        self._shutdown_and_unregister(old_tools_to_unload)

        # Reload new and changed tools
        new_tool_manifest = [new_manifest[t] for t in new_tools_to_load + same_tools_to_reload]
        self._reload_tools(new_tool_manifest)

        # Add the station_storage and any unchanged tools to create the new official manifest
        if "station_storage" not in new_tool_manifest:
            new_tool_manifest.append(old_manifest["station_storage"])
        for tool_id in untouched_tools:
            new_tool_manifest.append(new_manifest[tool_id])
        self._manifest_data = new_tool_manifest

    @staticmethod
    def _get_tool_id_from_manifest(manifest_item):
        return manifest_item.get("tool_id", f'{manifest_item["tool_type"]}_1')

    def _reload_tools(self, manifest):
        # Shutdown the tools to reload and cleanup after them
        tools = [self._get_tool_id_from_manifest(t) for t in manifest]
        #         if self._get_tool_id_from_manifest(t) != "station_storage"]
        self._shutdown_and_unregister(tools)

        # Load/Reload the tool modules
        reload_manifest = [tool for tool in manifest]
        #                    if self._get_tool_id_from_manifest(tool) != "station_storage"]
        self.load_tool_modules(reload_manifest, reload=True)

        # Initialize the tool modules to start
        tools_to_initialize = {tool_id: self.tools[tool_id] for tool_id in tools}
        self.initialize_tools(tools_to_initialize)

    def _shutdown_and_unregister(self, tools):
        # Shutdown tools and unregister any known events
        for tool_id in tools:
            if tool_id not in self.tools:
                continue
            self.tools[tool_id].is_shutting_down = True
            self.tools[tool_id].shutdown()
            self.tools[tool_id].set_offline()
            self.tools.pop(tool_id)
            if tool_id in self._tool_events:
                for source, event_enum, callback in self._tool_events[tool_id]:
                    unregister_from_event(source, event_enum, callback)
                self._tool_events.pop(tool_id)

    def tool_exists(self, tool_id):
        """
        Check if the named tool exists.

        :param str tool_id: unique tool identifier
        :return: True if a tool with the specified name exists, otherwise False
        :rtype: bool
        """
        return tool_id in self.tools

    def tool_status_listener(self, **kwargs):
        """
        Log and process incoming status updates from the tools

        :return:
        """
        # Tell UI to refresh tool status
        emit_event(InfoEvents.TOOL_UPDATE, {
            "source": "Toolbox",
            "status": self.get_status()
        })

    def get_status(self):
        """
        Return a list with the status of every tool in the toolbox.
        No particular order is returned.

        :return: list with status and info on all known tools
        :rtype: list
        """
        status = []
        for tool_id in self.tools:
            status.append(self.tools[tool_id].get_status())
        return status

    def get_tool_status(self, tool_id):
        """
        Get the online and in_use status of a particular tool

        :param str tool_id: ID of tool
        :return: (bool) online, (bool) in_use
        """
        if tool_id not in self.tools:
            log.error(f"got request for status of unknown tool '{tool_id}'")
            raise ToolNotExistsException(f"Unknown tool '{tool_id}'")

        online = self.tools[tool_id].is_online
        in_use = self.tools[tool_id]._locked()
        return online, in_use

    def get_tool_list(self):
        return self.tools.keys()

    def get_tools_for_ui(self):
        """

        :return:
        """
        tools = {}
        for tool_id in self.tools:
            tools[tool_id] = {
                "name": self.tools[tool_id].name,
                "tool_type": self.tools[tool_id].tool_type,
                "id": tool_id
            }
        return tools

    def get_endpoints(self):
        if not self._tools_reloaded:
            return self._endpoints
        endpoints = [
            Rule(PathMatches(r"/tool/status"), ToolboxStatus, {"status": self.get_status}),
            Rule(PathMatches(r"/tool/command"), ToolCommand),
            Rule(PathMatches(r"/tool/ui/([A-Za-z0-9\_]+)"), ToolUI,
                 {"tool_type_map": self._get_current_tools}),
        ]
        for tool_id in self.tools:
            for endpoint in self.tools[tool_id].get_endpoints():
                # TODO verify that endpoint starts with /tool/<tool_id> and that no
                # other rules are broken
                endpoints.append(Rule(PathMatches(endpoint[0]), *endpoint[1:]))
        self._endpoints = endpoints
        self._tools_reloaded = False
        return self._endpoints

    def _get_current_tools(self):
        return {tool_id: self.tools[tool_id].tool_type for tool_id in self.tools}

    def checkout_tool(self, process, tool_id):
        # type: (str, str) -> Tool
        """
        If tool is available, return instance of tool for use and lock tool until return_tool()
        is called.

        :param str process: optional info on who/what is using the tool
        :param str tool_id: unique tool identifier
        :return: tool instance, if tool is available and not locked.
        :raises ToolNotExistsException: if tool_id does not exist
        :raises ToolUnavailableException: if tool_id is offline
        :raises ToolInUseException: tool in use by another process
        """
        if tool_id not in self.tools:
            log.error(f"'{process}' trying to checkout unknown tool '{tool_id}'")
            raise ToolNotExistsException(f"'{process}' trying to checkout unknown tool '{tool_id}'")

        tool = self.tools[tool_id]

        if process is None or process == "":
            raise RuntimeError("Invalid attempt to anonymously checkout a tool")

        if not process.startswith("datastorage"):
            # Log for all processes except database storage process
            log.debug(7, f"'{process}' checking out tool '{tool_id}'")

        try:
            # Attempt to acquire the rights to use the tool
            tool._acquire_tool_lock(process)
        except ToolUnavailableException:
            # Tool is offline
            log.debug(3, f"Checkout Tool: '{tool_id}' offline")
            raise
        except ToolInUseException:
            # Tools is in use by another process
            log.debug(3, f"Checkout Tool: '{tool_id}' in use by '{tool.checked_out_by}'")
            raise
        else:
            self.tool_usage_times[tool_id] = time.time()
            return tool

    def return_tool(self, process, tool_obj):
        # type: (str, Tool) -> None
        """
        Release the lock on the tool checked out using checkout_tool() after done using.

        :param str process: process that is returning the tool
        :param tool_obj: tool object from checkout_tool()
        :return: None
        """
        try:
            tool_id = tool_obj.tool_id  # type: str
        except Exception as e:
            log.debug(1, f"'{process}' tried to return an invalid tool. Did nothing: {e}")
            return

        if tool_id not in self.tools:
            log.debug(1, f"'{process}' attempting to return unknown tool '{tool_id}'")
            return

        tool_obj._release_tool_lock(process)
        # TODO A good place to log tool usage if desired

        if not process.startswith("datastorage"):
            # Log for all processes except database storage process
            log.debug(8, f"'{process}' returned tool '{tool_id}'")


    def _add_tool(self, tool_data):
        tool = {
            "tool_id": tool_data['id'],
            "tool_type": tool_data['id'],
            "name": tool_data['name'],
            "configurations": tool_data.get('configurations', {})
        }
        
        self._manifest_data.append(tool)

@gen.coroutine
def verify_status_loop(tool_id, _tool, poll_period):
    while not _tool.is_shutting_down:
        try:
            # Check device status - only when tool is not in use
            if not _tool._locked():
                ret = _tool.verify_status()
                if _tool._manual_status_change:
                    # User deliberately set the status of the tool using set_online
                    #  or set_offline - leave the status alone and trust the user
                    _tool._manual_status_change = False
                elif ret is False:
                    # User explicitly returned False - this means the tool should be
                    #  set to offline
                    _tool.set_offline(manual=False)
                elif ret is True or ret is None:
                    # User either returned True or nothing - set the tool online
                    _tool.set_online(manual=False)
                else:
                    # User returned something unexpected - set tool offline
                    _tool.set_offline(manual=False)
        except Exception as e:
            log.warning(f"Exception in status loop for tool '{tool_id}': {e}")
            _tool.set_offline()
        finally:
            # Sleep for the poll delay while still monitoring for a quit state
            for _idx in range(0, int(poll_period) * 4):
                if _tool.is_shutting_down:
                    break
                yield gen.sleep(0.25)
    log.debug(2, f"Exiting status check loop for '{tool_id}'")
