// Copyright 2004-present Facebook. All Rights Reserved.

// Known Events
//
//  UI.ON_LINK_CLICK
//  UI.ACTIVE_LINK
//

var event_subscribers = {};

function event_emit(type, data) {
    for (let sub in event_subscribers[type]) {
        event_subscribers[type][sub](data);
    }
}

function event_register(id, callback, event) {
    if (!(event_subscribers.hasOwnProperty(event))) {
        event_subscribers[event] = {};
    }
    event_subscribers[event][id] = callback;
}

function event_unregister(id) {
    for (let key in event_subscribers) {
        delete event_subscribers[key][id];
    }
}

// ********************************************************************************

function random_id(objectName, length=16) {
    let id = "";
    for(let i = 0; i < length; i++) {
        id += Math.floor(((Math.random() * 16) % 16)).toString(16)
    }
    return objectName + "_" + id
}

// ********************************************************************************

class Icon extends React.Component {
icons = {
    "none": {path: ""},
    "x": {path: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"},
    "check": {path: "M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"},
    "home": {path: "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"},
    "tools": {path: "M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"},
    "station": {path: "M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3.58-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5z"},
    "user": {path: "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"},
    "busy": {path: "M6 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm12 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm-6 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"},
    "report": {path: "M18 17H6v-2h12v2zm0-4H6v-2h12v2zm0-4H6V7h12v2zM3 22l1.5-1.5L6 22l1.5-1.5L9 22l1.5-1.5L12 22l1.5-1.5L15 22l1.5-1.5L18 22l1.5-1.5L21 22V2l-1.5 1.5L18 2l-1.5 1.5L15 2l-1.5 1.5L12 2l-1.5 1.5L9 2 7.5 3.5 6 2 4.5 3.5 3 2v20z"},
    "abort": {path: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM4 12c0-4.42 3.58-8 8-8 1.85 0 3.55.63 4.9 1.69L5.69 16.9C4.63 15.55 4 13.85 4 12zm8 8c-1.85 0-3.55-.63-4.9-1.69L18.31 7.1C19.37 8.45 20 10.15 20 12c0 4.42-3.58 8-8 8z"},
    "requeue": {path: "M19 8l-4 4h3c0 3.31-2.69 6-6 6-1.01 0-1.97-.25-2.8-.7l-1.46 1.46C8.97 19.54 10.43 20 12 20c4.42 0 8-3.58 8-8h3l-4-4zM6 12c0-3.31 2.69-6 6-6 1.01 0 1.97.25 2.8.7l1.46-1.46C15.03 4.46 13.57 4 12 4c-4.42 0-8 3.58-8 8H1l4 4 4-4H6z"},
    "exclaim": {path: "M10 3h4v12h-4z M10 17h4v4h-4z"},
    "question": {path: "M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"},
    "caret": {path: "M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"},
};

render() {
    const circle = this.props.circle ? <circle r="12px" transform="translate(12, 12)"
                                            fill={this.props.fill} /> : null;
    const border = this.props.border ? <circle r="11px" transform="translate(12, 12)"
                                            fill="none" stroke="#777" strokeWidth="2px" /> : null;
    const rotate = this.props.rotate ? "rotate(90)" : "";
    return(
        <svg width={this.props.size || "1em"} height={this.props.size || "1em"}
            viewBox="0 0 24 24" className="icon-container-svg" transform={rotate}>
            {circle}
            {border}
            <path fill={this.props.circle ? "white": (this.props.fill || "black")}
                d={this.icons[this.props.icon].path} />
        </svg>
    )}
}

// ********************************************************************************

class Modal extends React.Component {
render() {
    const portal = ReactDOM.createPortal(
        this.props.children, document.getElementById("modal-root")
    );
    return this.props.show ?  portal : null;
}}

// ************************

class ModalPopup extends React.Component {
render() {
    return (
        <div className="modal-popup-container">
            <div className="modal-popup-card">
                {this.props.children}
            </div>
        </div>
    )}
}

// ********************************************************************************

class ActionButton extends React.Component {
    buttonEvent;
    eventData;
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
}

buttonClick = (e) => {
    let runtimedata = this.props.eventData || {};
    send_websocket(this.props.sendId || this.id, this.props.buttonEvent,  {runtimedata: runtimedata});
    e.preventDefault();
};

render() {
    return(
        <React.Fragment>
            <button onClick={this.props.buttonClick || this.buttonClick}
                    className={"se-button actionbutton " + this.props.className}
                    disabled={this.props.disabled} id={this.props.id} name={this.props.name} >
                {this.props.label}</button>
        </React.Fragment>
    )}
}

// ********************************************************************************

class Clock extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.timer = null;
    this.state = {
        time: new Date()
    }
}

componentDidMount() {
    this.timer = setInterval(this.clockUpdate, 1000)
}

componentWillUnmount() {
    clearInterval(this.timer);
}

clockUpdate = () => {
    this.setState({time: new Date()})
};

render() {
    return(
        <div className="station-clock">{this.state.time.toLocaleTimeString([],
            {hour: "2-digit", minute: "2-digit"})}</div>
    )}
}

// ********************************************************************************

class MessageView extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name)
}

render() {
    // TODO Scroll to bottom after appending a message (can we only do that if the user isn't
    //  currently scrolling? Or have a check to disable scroll to bottom?
    //  Explore filter option so that only station/tool specific data shown on proper page
    return(
        <div>
            <textarea id={this.id + "-message"} className="message-view-control" rows="15"
                        readOnly value={this.props.messages.join("\n")}/>
        </div>
    )}
}
