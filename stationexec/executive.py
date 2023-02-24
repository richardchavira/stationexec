# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

"""Executive"""
import os
import time
import threading
from functools import partial

from addict import Dict as Addict

import stationexec.sequencer.sequencer
from stationexec.logger import log
from stationexec.logger.logger import Logger
from stationexec.sequencer.handlers import (
    SequenceStartHandler,
    SequenceStatusHandler,
    SequenceStopHandler,
    SequenceHistoryHandler,
    SequenceRepeaterHandler,
)
from stationexec.sequencer import sequence_factory
from stationexec.station.data_storage import DataStorage
from stationexec.station.helpers import update_station_info
from stationexec.station.events import (
    emit_event,
    emit_event_non_blocking,
    register_for_event,
    register_for_events,
    ActionEvents,
    InfoEvents,
    RetrievalEvents,
    StorageEvents,
)
from stationexec.station.handlers import (
    StationUIHandler,
    StationStatusHandler,
    StationCommand,
    StationHelpHandler,
    PlotterDataHandler,
)
from stationexec.toolbox.toolbox import ToolBox, Tool
from stationexec.utilities import config, pc_info
from stationexec.utilities.exceptions import (
    ToolNotExistsException,
    ToolInUseException,
    ToolUnavailableException,
)
from stationexec.utilities.uuidstr import get_uuid
from stationexec.web.websocket import SocketManager, StationSocket
from stationexec.version import version as se_version
from stationexec.built_in.dut.dut import DEFAULT_SERIAL_NUMBER

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty


class Executive(object):
    """
    The Executive oversees all operation of the station and holds all objects used by the station.
    """

    config = None  # type: dict
    station_info = None  # type: Addict
    _station = None
    _storage_manager = None  # type: DataStorage
    # A websocket manager for maintaining all websocket communication
    _socket_manager = None  # type: SocketManager
    # The Sequencer object for running the Operations on the DUT
    _sequencer = None
    # The ToolBox object containing all the tools on this station
    _toolbox = None  # type: ToolBox
    # Hold the web port and SSL information (or None if no SSL)
    _web_port = None  # type: tuple

    def __init__(self, instance_config):
        """
        Initialize an Executive object and prepare to run `.Operation`\s for this `.Station`
        instance.

        :param dict instance_config: the configuration dictionary for this station id
        """
        self._is_shutting_down = False
        self.command_queue = Queue()
        self._cmd_thread_id = None

        # Load configuration data for the station type
        self.config = instance_config

        self.station_info = Addict(
            {
                "variant": self.get_cfg("station"),
                "name": self.get_cfg("name"),
                "instance": self.get_cfg("instance"),
                "id": get_uuid(),
                "mac_address": pc_info.get_mac_address(),
                "hostname": pc_info.get_hostname()
            }
        )

        self.user_info = Addict(
            {"username": "", "mode": "", "role": "", "logged_in": False}
        )

        self.sequence_repeater_info = Addict(
            {'current_rep': 0, 'total_reps': 1, 'infinite_reps': False}
        )

        self.plotter_data = Addict({"graphs_data": []})

        self.in_estop = False
        self.station_simple_status = "initializing"

        Logger().init(debug=self.get_cfg("debug"), api_logging=self.get_cfg("api_logging"), prefix=self.station_info.variant)

        log.debug(6, "Creating data storage manager")
        self._storage_manager = DataStorage()

        log.debug(5, "Creating toolbox")
        self._toolbox = ToolBox(
            self.get_cfg("debug"), self.get_cfg("dev"), self.get_cfg("db_data")
        )

        # Toolbox is ready - set checkout/return callbacks in data storage
        self._storage_manager.set_tool_management(
            self._toolbox.checkout_tool, self._toolbox.return_tool
        )

        # StorageEvents are ready for log messages - send one now to mark beginning
        log.debug(1, "Setting up Executive")

        log.debug(5, "Creating sequencer")
        self._sequencer = stationexec.sequencer.sequencer.Sequencer(self.get_cfg)

        log.debug(5, "Importing user station object")
        try:
            self._station = config.remote_path_import(
                os.path.join(config.get_all_paths()["station"], "station.py")
            )
            self.config["station_version"] = getattr(self._station, "version", "0.1")
            self.station_info["station_version"] = self.config["station_version"]
        except Exception as e:
            log.exception("Unable to initialize user station object", e)
            self._station = None

        log.debug(6, "Creating socket manager")
        self._socket_manager = SocketManager()

        self._dut_serial_number = DEFAULT_SERIAL_NUMBER

    def initialize(self):
        """ Create and initialize all sub-objects and prepare for actual processing. """
        # Initialize Station
        log.debug(5, "Initializing station")
        self._station_call(
            "initialize", partial(register_for_event, "userstation"), self.get_cfg
        )

        # Load the web socket manager
        log.debug(5, "Initializing socket manager")
        self._socket_manager.initialize()

        # Load tool manifest and initialize tools
        log.debug(5, "Initializing toolbox")
        self._toolbox.initialize()

        # Load sequence information, after we have a station AND a station_uuid
        log.debug(5, "Initializing sequencer")
        self._sequencer.initialize()

        # Register Executive for events
        register_for_event("executive", ActionEvents.SHUTDOWN, self.shutdown)
        register_for_event(
            "executive", ActionEvents.START_SEQUENCE, self.launch_sequence
        )
        register_for_event(
            "executive", ActionEvents.STOP_SEQUENCE, self.terminate_sequence
        )
        register_for_event("executive", ActionEvents.EMERGENCY_STOP, self.estop)
        register_for_event(
            "executive", ActionEvents.EMERGENCY_STOP_CLEAR, self.estop_clear
        )

        register_for_event("executive", InfoEvents.TOOL_COMMAND, self.ui_command)
        register_for_event("executive", InfoEvents.STATION_COMMAND, self.ui_command)
        register_for_event("executive", InfoEvents.WEBSOCKET_INCOMING, self.ui_command)

        register_for_event(
            "executive", InfoEvents.UI_DATA_REQUEST, self.sequence_status
        )
        register_for_event("executive", InfoEvents.UI_DATA_REQUEST, self.station_health)

        register_for_events(
            "executive",
            [
                InfoEvents.TOOL_UPDATE,
                InfoEvents.SEQUENCE_UPDATE,
                InfoEvents.SEQUENCE_STARTED,
                InfoEvents.SEQUENCE_ABORTED,
                InfoEvents.SEQUENCE_FAILED,
                InfoEvents.SEQUENCE_FINISHED,
                InfoEvents.EMERGENCY_STOP,
                InfoEvents.EMERGENCY_STOP_CLEARED,
            ],
            self.station_health,
        )
        register_for_event(
            "executive", InfoEvents.USER_LOGGED_IN, self.update_user_info
        )
        register_for_event(
            "executive", InfoEvents.USER_LOGGED_IN, self.refresh_station_data
        )
        register_for_event(
            "executive", InfoEvents.USER_LOGGED_OUT, self.update_user_info
        )
        register_for_event(
            "executive", InfoEvents.SEQUENCE_FINISHED, self.on_sequence_finish
        )
        register_for_event(
            "executive", InfoEvents.SEQUENCE_STARTED, self.on_sequence_start
        )
        register_for_event(
            "executive", InfoEvents.REPEATER_UPDATE, self.update_sequence_repeater_info
        )
        register_for_event(
            "executive", InfoEvents.PLOTTER_DATA_UPDATE, self.update_plotter_data
        )
        register_for_event(
            "executive", InfoEvents.DUT_SERIAL_NUMBER_UPDATE, self.on_update_dut_serial_number
        )


        # Update Mongo with Tool versions loaded
        self.send_tool_versions()

        # Start data storage service
        self._storage_manager.initialize()

        # Give the storage manager a second to get started and process its first batch of data
        time.sleep(1)

        # Check if this station has already been registered in the StationExec.Stations table
        self.station_data()

        if self.get_cfg('update_station_info'):
            update_station_info(self.get_cfg('station'), self.get_cfg('instance'))
            log.info('Updating station info')

        try:
            self._sequencer.set_active_sequence(self._load_default_sequence({}))
        except Exception as e:
            log.exception("Unable to load default sequence", e)

        emit_event(InfoEvents.STATION_LOADED, dict(self.station_info))

    def send_tool_versions(self):
        # Emit event to update Mongo with Tool versions loaded
        tools = {}
        for tool_id in self._toolbox.tools:
            tool_info = self._toolbox.tools[tool_id]
            tools[tool_info.tool_id] = tool_info.version

        emit_event(InfoEvents.TOOLS_LOADED, data_dict=tools)

    def update_user_info(self, **kwargs):

        if kwargs.get('_event') == InfoEvents.USER_LOGGED_IN:
            self.user_info.username = kwargs.get('username')
            self.user_info.mode = kwargs.get('mode')
            self.user_info.role = kwargs.get('role')
            self.user_info.logged_in = True
        else:
            self.user_info.username = ""
            self.user_info.mode = ""
            self.user_info.role = ""
            self.user_info.logged_in = False

    def update_sequence_repeater_info(self, **kwargs):
        for key in kwargs:
            if key != '_event':
                self.sequence_repeater_info[key] = kwargs.get(key)

    def on_sequence_finish(self, **kwargs):
        if kwargs['runcode'] == 'ABORTED':
            emit_event(InfoEvents.REPEATER_UPDATE, {'current_rep': 0})
            return
        if (
            self.sequence_repeater_info.current_rep
            < self.sequence_repeater_info.total_reps
        ) or self.sequence_repeater_info.infinite_reps:
            self.launch_sequence(runtimedata={})

    def on_sequence_start(self, **kwargs):
        if (
            self.sequence_repeater_info.current_rep
            >= self.sequence_repeater_info.total_reps
        ) and not self.sequence_repeater_info.infinite_reps:
            emit_event(InfoEvents.REPEATER_UPDATE, {'current_rep': 1})
        else:
            emit_event(
                InfoEvents.REPEATER_UPDATE,
                {'current_rep': self.sequence_repeater_info.current_rep + 1},
            )

    def update_plotter_data(self, **kwargs):
        self.plotter_data.graphs_data = kwargs.get('graphs_data')

    def get_station_data(self, event):
        station_search_data = {
            'instance': self.station_info.instance,
            'hostname': self.station_info.hostname,
            'mac_address': self.station_info.mac_address
        }

        station = emit_event(event, station_search_data)
        return station
    
    def register_station(self, event):
        station_info = {
            "uuid": self.station_uuid,
            "variant": self.station_info.variant,
            "instance": self.station_info.instance,
            "macaddress": self.station_info.mac_address,
            "hostname": self.station_info.hostname,
            "location": self.get_cfg('location', 'UNKNOWN'),
            "lineid": self.get_cfg('lineid', "UNKNOWN"),
            "info": self.get_cfg('info', None),
            "preferences": self.get_cfg('preferences', None),
            "addeduuid": "admin",
        }

        emit_event(event, station_info)

    def station_data(self, data_location=None):
        events = self.station_events(local=False)
        
        if data_location: # user tool login has selected alternate database configured in stationexec.json as 'db_endpoints' dict
            db_endpoints = config.get_system_config().get('db_endpoints')
            if db_endpoints.get(data_location) is None:
                events = self.station_events(local=True)
    
        if not self._toolbox.tool_exists("mongo"):
            events = self.station_events(local=True)
            
        station = self.get_station_data(events['get_station'])
        
        if station is None:
            # register new station to database
            self.register_station(events['register_station'])
        else:
            # use the registered uuid as the active one
            if type(station) is not dict:
                station = station.__dict__
            self.station_uuid = station.get('uuid')
        
        self._sequencer.station_id = self.station_uuid 
    
    def station_events(self, local=False):
        if local:
            return {
                'get_station': RetrievalEvents.GET_STATION_DATA_LOCAL,
                'register_station': StorageEvents.ON_REGISTER_STATION_LOCAL
            }        
        else:
            return {
                'get_station': RetrievalEvents.GET_STATION_DATA,
                'register_station': StorageEvents.ON_REGISTER_STATION
            }

    def refresh_station_data(self, **kwargs):
        # find / update station data if user has specified alternate data_location on login
        data_location = kwargs.get('data_location')
        if data_location:
            self.station_data(data_location)

    def on_update_dut_serial_number(self, **kwargs):
        self._dut_serial_number = kwargs.get("serial_number")

    def get_cfg(self, key, default=None):
        """
        Get config value from station configuration or default (None, unless specified)

        :param str key: the key to find
        :param str default: if specified, value to return if key not found; defaults to None
        :return: value of key
        """
        return self.config.get(key, default)

    def get_endpoints(self):
        """ Get the endpoints for each sub-object used by Station """
        endpoints = [
            (
                r"/socket",
                StationSocket,
                {
                    "socket_manager": self._socket_manager,
                    "stationuuid": self.station_info.id,
                },
            ),
            (r"/station", StationUIHandler, {'station_info': self.station_info}),
            (r"/station/command", StationCommand, {'station': self._station_call}),
            (
                r"/station/status",
                StationStatusHandler,
                {'station_status': self.station_status},
            ),
            (r"/station/help", StationHelpHandler),
            (
                r"/sequence/history",
                SequenceHistoryHandler,
                {"station_uuid": self.station_uuid, "sequencer": self._sequencer},
            ),
            (
                r"/sequence/start",
                SequenceStartHandler,
                {"launch_sequence": self.launch_sequence},
            ),
            (
                r"/sequence/status",
                SequenceStatusHandler,
                {"sequence_status": self.sequence_status},
            ),
            (
                r"/sequence/stop",
                SequenceStopHandler,
                {"terminate_sequence": self.terminate_sequence},
            ),
            (
                r"/sequence/repeater",
                SequenceRepeaterHandler,
                {"sequence_repeater_info": self.sequence_repeater_info},
            ),
            (r"/graphs_data", PlotterDataHandler, {"graphs_data": self.plotter_data}),
        ]
        return endpoints

    def shutdown(self, **kwargs):
        """ stop all threads in this and lower objects, and prepare to exit """
        if not self._is_shutting_down:
            log.warning("Executive shutting down sequencer, toolbox, storage manager")
            self._is_shutting_down = True
            self._sequencer.shutdown()
            self._toolbox.shutdown()
            self._storage_manager.shutdown()
            self._socket_manager.shutdown()

    def get_web_info(self):
        """
        Returns a tuple with the configured web port and either a dict with the SSL config info for
        this station instance or else None if not configured for https.
        """
        return self.get_cfg("port"), self.get_cfg("https_data")

    def _station_call(self, method, *args, **kwargs):
        """ Cleanly and safely call a station method by name if it exists """
        if self._station is not None:
            if hasattr(self._station, method):
                return getattr(self._station, method)(*args, **kwargs)
        return None

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

                obj_ref = None
                obj_id = None
                try:
                    if source.startswith("tool."):
                        _, obj_id = source.split(".", 1)
                        obj_ref = self._toolbox.checkout_tool("on_ui_command", obj_id)
                    else:
                        obj_id = "station"
                        obj_ref = self._station
                except (
                    ToolNotExistsException,
                    ToolUnavailableException,
                    ToolInUseException,
                ) as e:
                    log.debug(
                        1,
                        "Unable to checkout tool '{0}' in "
                        "'on_ui_command': {1}".format(obj_id, e),
                    )
                    emit_event(
                        InfoEvents.MESSAGE_UPDATE,
                        {"source": "toolbox", "message": str(e)},
                    )
                except Exception as e:
                    log.exception("Exception in on_ui_command parsing", e)
                else:
                    for command in messages[source]:
                        if self._is_shutting_down:
                            break
                        _source_id, kwargs = command
                        try:
                            obj_command = kwargs.pop("command")
                        except Exception as e:
                            log.debug(
                                1,
                                "Exception in on_ui_command arguments {0}: {1}".format(
                                    kwargs, e
                                ),
                            )
                            continue
                        log.debug(3, "ui_command - " + obj_id + ": " + obj_command)
                        try:
                            obj_ref.on_ui_command(obj_command, **kwargs)
                        except Exception as e:
                            log.debug(
                                1,
                                "Exception in 'on_ui_command' calling '{0}' of "
                                "'{1}': {2}".format(obj_command, obj_id, e),
                            )
                finally:
                    try:
                        if obj_ref is not None and isinstance(obj_ref, Tool):
                            self._toolbox.return_tool("on_ui_command", obj_ref)
                    except ToolInUseException:
                        log.debug(
                            2,
                            "Tried to return a tool owned by another process in "
                            "'on_ui_command'",
                        )
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
        if source.startswith("socket") and kwargs.get("type") in [
            "tool_command",
            "station_command",
        ]:
            cmd = kwargs.get("arguments")
        else:
            if "cmd" in kwargs:
                cmd = kwargs.get("cmd")
            else:
                return
        target = kwargs.get("target")

        # Disallow ui_commands while sequence is running
        if self._sequencer.is_active():
            log.warning(
                "Command for '{0}' ignored because sequence is active".format(target)
            )
            emit_event(
                InfoEvents.MESSAGE_UPDATE,
                {
                    "source": "executive",
                    "message": "Command for '{0}' ignored because sequence is active".format(
                        target
                    ),
                },
            )
            return

        if self._cmd_thread_id is None:
            self._cmd_thread_id = threading.Thread(target=self._ui_command)
            self._cmd_thread_id.start()
        self.command_queue.put((target, cmd))

    # ----------------------------------------------------------------------------------------

    def launch_sequence(self, runtimedata, **kwargs):
        """
        Build a sequence and submit it to the sequencer for running

        Registered to be called on ActionEvents.START_SEQUENCE
            Emitted from: SequenceStartHandler - /sequence/start

        :param dict runtimedata:
        :param dict kwargs:
        :return:
        """
        if self._sequencer.is_active():
            emit_event(
                InfoEvents.ALERT_UPDATE,
                {
                    "source": "executive",
                    "message": "Unable to start sequence - sequence already running",
                },
            )
            return

        try:
            sequence = self._load_default_sequence(runtimedata)
        except Exception as e:
            emit_event(
                InfoEvents.ALERT_UPDATE,
                {
                    "source": "executive",
                    "message": "Unable to load sequence: {0}".format(e),
                },
            )
            log.exception("Unable to load sequence. Sequence not started\n", e)
            return

        # TODO Add check to see that tools registered for data storage are also online here
        tools = sequence.get_required_tools()

        try:
            unavailable_tools = []
            for tool in tools:
                online, in_use = self._toolbox.get_tool_status(tool)
                if in_use or not online:
                    unavailable_tools.append(tool)
            if len(unavailable_tools) > 0:
                raise Exception(
                    "Tool(s) in use or offline: {0}".format(",".join(unavailable_tools))
                )
        except Exception as e:
            emit_event(
                InfoEvents.MESSAGE_UPDATE,
                {
                    "source": "executive",
                    "message": "Unable to start sequence: {0}".format(e),
                },
            )
            emit_event(
                InfoEvents.ALERT_UPDATE,
                {
                    "source": "executive",
                    "message": "Unable to start sequence: {0}".format(e),
                },
            )
            log.exception("Unable to start sequence", e)
        else:
            self._sequencer.run(sequence)

    def _load_default_sequence(self, runtimedata):
        tool_functions = (self._toolbox.checkout_tool, self._toolbox.return_tool)

        operation_config = config.get_all_paths()["operation_config"]
        operation_code = config.get_all_paths()["operation_defs"]

        avg_runtimes = emit_event(
            RetrievalEvents.GET_OPERATION_AVERAGE_DURATION,
            {"stationuuid": self.station_info.id},
        )

        runtimedata['dut_serial_number'] = self._dut_serial_number

        return sequence_factory.from_file(
            operation_config,
            operation_code,
            tool_functions,
            self.config,
            avg_operation_runtimes=avg_runtimes,
            runtimedata=runtimedata,
            n_up=0,
        )

    def terminate_sequence(self, **kwargs):
        """
        Terminate the active sequence

        Registered to be called on ActionEvents.STOP_SEQUENCE
            Emitted from: SequenceStopHandler - /sequence/stop

        :param kwargs:
        :return:
        """
        self._sequencer.stop("Sequence termination requested")

    def estop(self, **kwargs):
        # Call user estop code if it exists
        self.in_estop = True
        emit_event_non_blocking(InfoEvents.EMERGENCY_STOP, {})

    def estop_clear(self, **kwargs):
        # Call user estop clear code if it exists
        self.in_estop = False
        emit_event_non_blocking(InfoEvents.EMERGENCY_STOP_CLEARED, {})

    def sequence_status(self, **kwargs):
        # Call user sequence_status if it exists
        seq_status = self._sequencer.get_status()
        if seq_status != {}:
            seq_status["custom"] = self._station_call("sequence_status") or {}

        if (
            kwargs.get("event") == "InfoEvents.UI_DATA_REQUEST"
            and kwargs.get("requesting") == "sequence_status"
        ):
            emit_event_non_blocking(
                InfoEvents.UI_DATA_DELIVERY,
                {"result": {"data": seq_status}, "target": kwargs["_websource"]},
            )
        return seq_status

    def station_status(self, **kwargs):
        # Return the status of the station
        station_status, description = self.station_health()
        return {
            "status": station_status,
            "status_description": description,
            "se_version": se_version,
            "user_info": self.user_info,
            "info": self.station_info,
            "sequence": self.sequence_status(),
            "tools": self._toolbox.get_status(),
            "custom": self._station_call("station_status") or {},
        }

    def station_health(self, **kwargs):
        """
        Report a simple text status of the station: "ready", "running", "down"

        :param kwargs:
        :return:
        """
        tools = self._toolbox.get_status()
        # TODO restrict to just sequence required items?
        unavailable_tools = [
            tool["tool_id"] for tool in tools if not tool["online_bool"]
        ]
        sequence_running = self._sequencer.is_active()

        if self.in_estop:
            status = "down"
            description = "Estop is active"
        elif sequence_running:
            status = "running"
            description = "Sequence {0:.8} is running".format(
                self._sequencer.active_sequence.uuid
            )
        elif len(unavailable_tools) > 0:
            status = "down"
            description = "Tool(s) are offline: {0}".format(
                ", ".join(unavailable_tools)
            )
        elif not sequence_running:
            status = "ready"
            description = "Ready to run"
        else:
            # System is a) not in estop, b) all tools are online, c) no active sequence available
            status = "ready"
            description = "Ready to run"

        if (
            kwargs.get("event") == "InfoEvents.UI_DATA_REQUEST"
            and kwargs.get("requesting") == "station_health"
        ):
            emit_event_non_blocking(
                InfoEvents.UI_DATA_DELIVERY,
                {
                    "result": {"status": status, "description": description},
                    "target": kwargs["_websource"],
                },
            )

        if status != self.station_simple_status:
            self.station_simple_status = status
            emit_event_non_blocking(
                InfoEvents.STATION_HEALTH,
                {
                    "status": status,
                    "description": description,
                },
            )

        return status, description

    # ----------------------------------------------------------------------------------------

    @property
    def station_uuid(self):
        return self.station_info.id

    @station_uuid.setter
    def station_uuid(self, sid):
        self.station_info.id = sid
