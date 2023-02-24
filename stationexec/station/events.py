# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from collections import defaultdict
from enum import Enum, EnumMeta, unique

from stationexec.logger import log
from stationexec.utilities.ioloop_ref import IoLoop

_known_events = defaultdict(list)

# Callback methods for tooling in DataStorage
__reg_callback = None
__unreg_callback = None
__trig_callback = None


def register_for_event_group(source, event_group, callback):
    if type(event_group) is not EnumMeta:
        raise Exception("Invalid reference given for event group registration")
    for event_enum in event_group:
        register_for_event(source, event_enum, callback)


def register_for_events(source, event_enums, callback):
    for event in event_enums:
        register_for_event(source, event, callback)


def register_for_event(source, event_enum, callback):
    # Callback must take 1 argument that is the data dictionary
    global _known_events
    global __reg_callback

    storage_event = isinstance(event_enum, StorageEvents) or isinstance(
        event_enum, RetrievalEvents
    )
    if storage_event and __reg_callback is not None:
        # Tell DataStorage about Storage or Retrieval event registrations exclusively
        __reg_callback(source, event_enum, callback)
    else:
        _known_events[event_enum].append((source, event_enum, callback))

def clear_event_subscribers(source, event_enum):
    global _known_events
    global __unreg_callback
    global __reg_callback

    storage_event = isinstance(event_enum, StorageEvents) or isinstance(
        event_enum, RetrievalEvents
    )
    if storage_event and __reg_callback is not None:
        log.warning("Clearing event subscribers for StorageEvents is not supported")
    else:
        for reg_source, reg_event, reg_callback in _known_events[event_enum]:
            if reg_source == source:
                _known_events[event_enum].remove((reg_source, reg_event, reg_callback))

def unregister_from_event(source, event_enum, callback):
    global _known_events
    global __unreg_callback

    storage_event = isinstance(event_enum, StorageEvents) or isinstance(
        event_enum, RetrievalEvents
    )
    if storage_event and __reg_callback is not None:
        __unreg_callback(source, event_enum, callback)
    else:
        _known_events[event_enum].remove((source, event_enum, callback))


def emit_event(event_enum, data_dict=None):
    global _known_events
    global __trig_callback
    ret_data = None

    if not data_dict:
        data_dict = {}

    storage_event = isinstance(event_enum, StorageEvents) or isinstance(
        event_enum, RetrievalEvents
    )
    if storage_event:
        if __trig_callback is None:
            return None
        # Tell DataStorage about Storage or Retrieval event triggers exclusively
        ret_data = __trig_callback(event_enum, data_dict)
    else:
        for subscriber in _known_events[event_enum]:
            # Log source and maybe the subscribers
            source, event, callback = subscriber
            data_dict["_event"] = event
            try:
                callback(**data_dict)
            except Exception as e:
                log.exception("Exception in event call", e)

    # Allow retrieval events to return data immediately - no other events return data
    return ret_data


def emit_event_non_blocking(event_enum, data_dict=None):
    if not data_dict:
        data_dict = {}
    IoLoop().current().spawn_callback(emit_event, event_enum, data_dict)


def _set_storage_callbacks(register, unregister, trigger):
    # DataStorage callbacks for when a registration or trigger occurs
    global __reg_callback
    global __unreg_callback
    global __trig_callback
    if __reg_callback is None:
        __reg_callback = register
    if __unreg_callback is None:
        __unreg_callback = unregister
    if __trig_callback is None:
        __trig_callback = trigger


@unique
class StorageEvents(Enum):
    ON_CUSTOM_STORAGE = 0
    ON_SEQUENCE_START = 1
    ON_SEQUENCE_END = 2
    ON_OPERATION_START = 3
    ON_OPERATION_END = 4
    ON_RESULT_STORE = 5
    ON_DATA_STORE = 6
    ON_REGISTER_STATION = 7
    ON_UPDATE_STATION = 8
    ON_REGISTER_STATION_LOCAL = 9
    ON_LOG_DATA = 11
    ON_MAINTENANCE_EVENT = 12
    ON_ERROR_CODE = 13
    ON_ADD_DUT = 14

@unique
class RetrievalEvents(Enum):
    GET_CUSTOM_DATA = 0
    GET_OPERATION_AVERAGE_DURATION = 1
    GET_STATION_DATA = 2
    GET_STATION_DATA_LOCAL = 3
    GET_LOG_DATA = 6
    GET_MAINTENANCE_DATA = 7
    GET_SEQUENCES = 8
    GET_SEQUENCE_OPERATIONS = 9
    GET_SEQUENCE_RESULTS = 10
    GET_SEQUENCE_DATA = 11
    GET_DUT_DATA = 12

@unique
class ActionEvents(Enum):
    SHUTDOWN = 0
    START_SEQUENCE = 1
    STOP_SEQUENCE = 2
    EMERGENCY_STOP = 3
    EMERGENCY_STOP_CLEAR = 4
    RELOAD_TOOL_MANIFEST = 5
    RELOAD_SEQUENCE_OPERATIONS = 6
    RELOAD_STATION = 7
    RELOAD_CONFIG = 8
    UPDATE_TOOL_STATUS = 9
    UPDATE_STATION_STATUS = 10


@unique
class InfoEvents(Enum):
    SHUTTING_DOWN = 0
    SEQUENCE_STARTED = 1
    SEQUENCE_FINISHED = 2
    SEQUENCE_FAILED = 3
    SEQUENCE_ABORTED = 4
    EMERGENCY_STOP = 5
    EMERGENCY_STOP_CLEARED = 6
    USER_LOGGED_IN = 7
    USER_LOGGED_OUT = 8
    UNAUTHORIZED_ACCESS = 9
    WEBSOCKET_INCOMING = 10
    SEQUENCE_UPDATE = 11
    TOOL_UPDATE = 12
    MESSAGE_UPDATE = 13
    OBJECT_UPDATE = 14
    ALERT_UPDATE = 15
    POPUP_UPDATE = 16
    LOG = 17
    SERVER_STARTED = 18
    TOOL_COMMAND = 19
    STATION_COMMAND = 20
    TOOLS_LOADED = 21
    SEQUENCE_LOADED = 22
    STATION_LOADED = 23
    CONFIG_LOADED = 24
    UI_LOADED = 25
    STATION_HEALTH = 26
    UI_DATA_REQUEST = 27
    UI_DATA_DELIVERY = 28
    STORAGE_COMPLETE = 29
    REPEATER_UPDATE = 30
    PLOTTER_DATA_UPDATE = 31
    DUT_SERIAL_NUMBER_UPDATE = 32
    ROUTING_DATA_UPDATE = 35
    PASS_ERROR_CODE = 36
    USER_INPUT_REQUEST = 37
