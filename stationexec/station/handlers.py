# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1
import os

import simplejson
from stationexec.station.events import emit_event, InfoEvents
from stationexec.utilities import config
from stationexec.web.handlers import ExecutiveHandler


class StationUIHandler(ExecutiveHandler):
    _station_info = None

    def initialize(self, **kwargs):
        self._station_info = kwargs.get("station_info")

    def get(self):
        display_name = self._station_info.name
        station_type = self._station_info.instance
        self.render("station/index.html", station_name=display_name,
                    station_type=station_type)


class StationStatusHandler(ExecutiveHandler):
    _station_status = None

    def initialize(self, **kwargs):
        self._station_status = kwargs.get("station_status")

    def get(self):
        """Write JSON encoded string of the station status"""
        data = self._station_status()
        self.write(simplejson.dumps(data))


class StationHelpHandler(ExecutiveHandler):
    def get(self):
        """Write JSON encoded string of the sequence executed status"""
        station_path = config.get_all_paths()["station"]
        help_path = os.path.join(station_path, "ui", "help")
        data = []
        if os.path.exists(help_path):
            help_file_link = "/static/station/help/"
            for file in os.listdir(help_path):
                data.append({
                    "file": file,
                    "link": "{0}{1}".format(help_file_link, file)
                })
        self.write(simplejson.dumps(data))


class StationCommand(ExecutiveHandler):
    def post(self):
        """
        Send a command to a station. Command to tool is placed in the JSON body.
         Command contains the command with arguments.
        """
        cmd = self.json_args.get("arguments")
        emit_event(InfoEvents.STATION_COMMAND, {"source": "handler.StationCommand",
                                                "target": "station",
                                                "cmd": cmd})
