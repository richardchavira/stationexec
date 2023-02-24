var ws = null;
var connection = "";

//*******************************************************************
// Helper functions
//*******************************************************************

function open_websocket(callOnOpen, callOnClose) {
    if (ws != null) {
        ws.close();
        ws = null;
    }
    ws = new WebSocket(connection);
    ws.onmessage = receive_websocket;
    ws.onopen = callOnOpen;
    ws.onclose = callOnClose;
}

function close_websocket() {
    if (ws != null) {
        ws.close();
        ws = null;
    }
}

var ws_events = {};

function receive_websocket(evt) {
    let data = JSON.parse(evt.data);
    let type = data._event;
    if (!(ws_events.hasOwnProperty(type))) {
        return
    }
    for (let sub in ws_events[type]) {
        ws_events[type][sub](data);
    }
}

var backlog = [];
// If messages are sent before the websocket is live, store them until the
//   connection is valid. At that point, send them all and empty the array

function send_websocket(source, event, data_object) {
    data_object._websource = source;
    data_object._webevent = event;
    let msg = JSON.stringify(data_object);
    if (ws && ws.readyState === 1) {
        for (let m in backlog) {
            ws.send(backlog[m]);
        }
        backlog = [];
        ws.send(msg);
    } else {
        backlog.push(msg);
    }
}

function ws_register(id, callback, event) {
    if (!(ws_events.hasOwnProperty(event))) {
        ws_events[event] = {};
    }
    ws_events[event][id] = callback;
}

function ws_unregister(id) {
    for (let key in ws_events) {
        delete ws_events[key][id];
    }
}

function notify_closed_websocket(data) {
    console.log("Lost connection with server websocket");
    if (connection !== "") {
        // Retry websocket connection until successful or page closes
        window.setTimeout(open_websocket, 5000);
    }
}

window.addEventListener("beforeunload", () => {
    close_websocket()
});
