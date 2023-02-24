# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from stationexec.station.events import (
    emit_event,
    emit_event_non_blocking,
    InfoEvents,
    ActionEvents,
    StorageEvents
)
from stationexec.utilities import config, pc_info


def shutdown():
    """
    Shutdown the station
    """
    emit_event_non_blocking(ActionEvents.SHUTDOWN)


def start_sequence(runtimedata=None):
    """
    Kick off a sequence run - add optional runtime data arguments

    :param runtimedata:
    """
    runtimedata = runtimedata or {}
    emit_event_non_blocking(ActionEvents.START_SEQUENCE, {"runtimedata": runtimedata})


def stop_sequence():
    """
    Terminate a sequence
    """
    emit_event_non_blocking(ActionEvents.STOP_SEQUENCE)


def emergency_stop():
    """
    Set emergency stop state
    """
    emit_event_non_blocking(ActionEvents.EMERGENCY_STOP)


def emergency_stop_clear():
    """
    Clear emergency stop state
    """
    emit_event_non_blocking(ActionEvents.EMERGENCY_STOP_CLEAR)


def ui_log(message, sender="helper"):
    """
    Write a message on the front page log

    :param message:
    :param sender:
    """
    emit_event(InfoEvents.MESSAGE_UPDATE, {"source": sender, "message": message})


def value_to_ui(target, value, sender="helper"):
    """
    Update a value on the
    :param target:
    :param value:
    :param sender:
    """
    emit_event(
        InfoEvents.OBJECT_UPDATE, {"source": sender, "target": target, "value": value}
    )


def reload_tool_manifest(new_manifest=None):
    """
    Trigger a reload of the tool manifest - pass in a new manifest dictionary to override the old one
    :param new_manifest:
    """
    emit_event(ActionEvents.RELOAD_TOOL_MANIFEST, {"manifest": new_manifest})


def update_plotter_data(graphs_data=None):
    emit_event_non_blocking(
        InfoEvents.PLOTTER_DATA_UPDATE, {"graphs_data": graphs_data}
    )


def update_station_info(variant, instance):

    update_info = {
        "variant": variant,
        "instance": instance
    }

    # pc info
    update_info['macaddress'] = pc_info.get_mac_address()
    update_info['hostname'] = pc_info.get_hostname()

    # attempt to get info from station's config.json
    paths = config.get_all_paths()
    station_config_path = paths.get('station_config')
    if station_config_path:
        station_config_data = config.load_config(station_config_path)
        update_info['location'] = station_config_data.get('location', 'UNKNOWN')
        update_info['lineid'] = station_config_data.get('lineid', 'UNKNOWN')
        update_info['info'] = station_config_data.get('info')
        update_info['preferences'] = station_config_data.get('preferences')

    emit_event(
            StorageEvents.ON_UPDATE_STATION,
            update_info,
        )
