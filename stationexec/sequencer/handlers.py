# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from typing import Callable

import simplejson
from stationexec.station.events import emit_event, emit_event_non_blocking, ActionEvents, RetrievalEvents
from stationexec.web.handlers import ExecutiveHandler


class SequenceStartHandler(ExecutiveHandler):
    """ This endpoint handler is used to request a sequence start. """

    def post(self):
        """ Request execution of a sequence """
        emit_event_non_blocking(ActionEvents.START_SEQUENCE, {"runtimedata": self.json_args})


class SequenceStopHandler(ExecutiveHandler):
    """ This endpoint handler is used to stop a running sequence of operations. """

    def post(self):
        """ Request termination of sequence """
        emit_event_non_blocking(ActionEvents.STOP_SEQUENCE, {})


class SequenceStatusHandler(ExecutiveHandler):
    """
    This endpoint handler is used to request information on the currently running sequence of
    operations.
    """
    sequence_status = None  # type: Callable

    def initialize(self, **kwargs):
        """ Prepare to handle endpoint operation """
        self.sequence_status = kwargs["sequence_status"]

    def get(self):
        """ Write JSON encoded string of the sequence status """
        self.set_header("Content-Type", "application/json")
        data = self.sequence_status()
        self.write(simplejson.dumps(data))


class SequenceHistoryHandler(ExecutiveHandler):
    station_uuid = None
    sequencer = None

    def initialize(self, **kwargs):
        """ Prepare to handle endpoint operation """
        self.station_uuid = kwargs["station_uuid"]
        self.sequencer = kwargs["sequencer"]

    def post(self):
        self.get()

    def get(self):
        """ Write JSON encoded string of the sequence history """
        self.set_header("Content-Type", "application/json")

        history_type = self.json_args.get("historytype")
        if history_type == "sequences":
            # TODO Ideally this could also grab from the local sequence history
            #  (self._sequencer.get_sequence_history()) to get an accurate recent
            #  view since recently run sequences take several seconds to populate in db
            history = emit_event(RetrievalEvents.GET_SEQUENCES, {
                "stationuuid": self.station_uuid,
                "sequenceuuid": self.json_args.get("sequenceuuid", None),
                "number": self.json_args.get("number", 10),
                "starttime": self.json_args.get("starttime", None),
                "endtime": self.json_args.get("endtime", None)
            })
        elif history_type == "operations":
            history = emit_event(RetrievalEvents.GET_SEQUENCE_OPERATIONS, {
                "stationuuid": self.station_uuid,
                "sequenceuuid": self.json_args.get("sequenceuuid"),
            })
        elif history_type == "results":
            history = emit_event(RetrievalEvents.GET_SEQUENCE_RESULTS, {
                "stationuuid": self.station_uuid,
                "sequenceuuid": self.json_args.get("sequenceuuid", None),
                "operationuuid": self.json_args.get("operationuuid", None),
                "operationid": self.json_args.get("operationid", None),
            })
        elif history_type == "data":
            history = emit_event(RetrievalEvents.GET_SEQUENCE_DATA, {
                "stationuuid": self.station_uuid,
                "sequenceuuid": self.json_args.get("sequenceuuid", None),
                "operationuuid": self.json_args.get("operationuuid", None),
                "operationid": self.json_args.get("operationid", None),
            })
        else:
            history = emit_event(RetrievalEvents.GET_SEQUENCES, {
                "stationuuid": self.station_uuid,
                "number": 10
            })

        self.write(simplejson.dumps(history))
