# Copyright 2004-present Facebook. All Rights Reserved.

import simplejson
from stationexec.logger import log
from stationexec.station.events import (
    emit_event,
    register_for_event_group,
    InfoEvents,
    ActionEvents,
    RetrievalEvents,
    emit_event_non_blocking,
)
from stationexec.utilities.ioloop_ref import IoLoop
from stationexec.utilities.uuidstr import get_uuid
from tornado import gen
from tornado.iostream import StreamClosedError
from tornado.web import HTTPError
from tornado.websocket import WebSocketClosedError, WebSocketHandler

is_shutting_down = False


class StationSocket(WebSocketHandler):
    """Tornado endpoint handler for requesting a new web socket"""

    manager = None
    uuid = None
    stationuuid = None

    def initialize(self, **kwargs):
        """Get station socket ready for operation."""
        self.manager = kwargs["socket_manager"]
        self.uuid = get_uuid()
        self.stationuuid = kwargs["stationuuid"]

    def open(self):
        self.manager.save(self)

    def prepare(self):
        global is_shutting_down
        if is_shutting_down:
            raise HTTPError()
        else:
            super(WebSocketHandler, self).prepare()

    def on_message(self, message):
        try:
            data = simplejson.loads(message)
            if not isinstance(data, dict):
                raise Exception()
        except Exception:
            data = {"type": "unknown", "message": "message"}

        if "_webevent" in data:
            event_type, event = data["_webevent"].split(".", 1)
            # Cast events into their enum types to verify they are valid events
            if event_type == "ActionEvents":
                event = ActionEvents[event]
            elif event_type == "InfoEvents":
                event = InfoEvents[event]

            elif event_type == "RetrievalEvents":
                self.handle_retrieval_events(RetrievalEvents[event], data)
        else:
            event = InfoEvents.WEBSOCKET_INCOMING

        data["source"] = "socket.{0}".format(self.uuid)
        data["event"] = str(event)

        emit_event_non_blocking(event, data)

    def handle_retrieval_events(self, event, data):
        data["stationuuid"] = self.stationuuid
        result = emit_event(event, data)
        out_data = {
            "target": data["_websource"],
            "result": result,
            "request_event": str(event),
        }
        emit_event_non_blocking(InfoEvents.UI_DATA_DELIVERY, out_data)

    def on_close(self):
        self.manager.delete(self)


class SocketManager(object):
    """ An object that stores all the sockets that have been opened by clients. """

    def __init__(self):
        # Stores all the sockets that have been created, so that we can communicate with them.
        self._socket_sessions = {}  # type: dict

    def initialize(self):
        """Get socket manager ready for operation."""
        register_for_event_group("SocketManager", InfoEvents, self.send_all)

    def shutdown(self):
        global is_shutting_down
        is_shutting_down = True
        IoLoop().current().spawn_callback(self._close_all)

    def save(self, socket):
        """Store a new socket."""
        if is_shutting_down:
            return
        if socket.uuid not in self._socket_sessions:
            self._socket_sessions[socket.uuid] = socket

    def delete(self, socket):
        """Remove a socket from the active list."""
        if socket.uuid in self._socket_sessions:
            self._socket_sessions.pop(socket.uuid, None)

    def send_all(self, **event_data):
        """ Send a message to all open sockets. """
        if is_shutting_down:
            return
        event_data["_event"] = str(event_data["_event"])
        # Schedule it to execute on the main Tornado thread to avoid socket corruption
        IoLoop().current().spawn_callback(self._send_all, simplejson.dumps(event_data))

    @gen.coroutine
    def _send_all(self, message):
        """ Internal function. """
        closed_sockets = []
        sockets = list(self._socket_sessions.keys())
        for socket_id in sockets:
            if is_shutting_down:
                return
            try:
                yield self._socket_sessions[socket_id].write_message(message)
            except (WebSocketClosedError, StreamClosedError) as e:
                log.debug(4, "tried to write to closed socket: {0}".format(e))
                closed_sockets.append(socket_id)
            except BufferError as e:
                log.exception(
                    "socket buffer error with message '{0}'".format(message), e
                )
        for socket_id in closed_sockets:
            self._socket_sessions.pop(socket_id, None)

    @gen.coroutine
    def _close_all(self):
        sockets = list(self._socket_sessions.keys())
        for socket_id in sockets:
            try:
                yield self._socket_sessions[socket_id].close()
            except (WebSocketClosedError, StreamClosedError, BufferError):
                pass
