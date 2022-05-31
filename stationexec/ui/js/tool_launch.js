// Copyright 2004-present Facebook. All Rights Reserved.

class ToolStatusNode extends React.Component {
    inuse;
render() {
    const icon = this.props.status ? (this.props.inuse ? "busy" : "check") : "x";
    const color = this.props.status ? (this.props.inuse ? "#f39c12" : "#89b148") : "#e05a4e";
    return(
        <React.Fragment>
            <span className="tool-status-text">
                <Icon circle icon={icon} fill={color} />
                {this.props.name}
            </span>
        </React.Fragment>
    )}
}

// ************************

class ToolLaunch extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        html: "Loading...",
        tools: {},
        messages: [],
        wsConnection: true,
    };
    this.script_tags = [];
    this.firstRender = false;
    this.firstConnectionPassed = false;

    this.pageOptions = htmlParseOptions((tag) => this.script_tags.push(tag),
        (evt) => this.onButton(evt));
}

componentDidMount() {
    ws_register(this.id, this.updateTool, "InfoEvents.TOOL_UPDATE");
    ws_register(this.id, this.updateObject, "InfoEvents.OBJECT_UPDATE");
    ws_register(this.id, this.updateMessage, "InfoEvents.MESSAGE_UPDATE");
    open_websocket(this.onWebsocketOpen, this.onWebsocketClose);
    this.fetchToolUrl()
}

componentDidUpdate(prevProps) {
    if (!this.firstRender) {
        this.fetchToolUrl()
    }
}

fetchToolUrl() {
    this.firstRender = true;
    let url = "/tool/ui/" + this.props.tool_id;
    fetch(url)
        .then(response => response.text())
        .then(rawhtml => this.setState({html: HTMLReactParser(rawhtml, this.pageOptions)}))
}

componentWillUnmount() {
    ws_unregister(this.id);

    // If this component added script tags to header, remove them now
    this.script_tags.forEach(tag => {
        let script_element = document.getElementById(tag);
        script_element.parentNode.removeChild(script_element);
    });

    close_websocket()
}

onWebsocketOpen = () => {
    if (this.firstConnectionPassed) {
        window.location.reload(true)
    }
    this.setState({wsConnection: true});
    this.firstConnectionPassed = true;
};

onWebsocketClose = () => {
    this.setState({wsConnection: false});
    open_websocket(this.onWebsocketOpen, this.onWebsocketClose)
};

updateTool = (objectData) => {
    if (typeof objectData == 'undefined') return;
    this.setState({
        tools: objectData.status
    })
};

updateMessage = (objectData) => {
    if (typeof objectData == 'undefined') return;
    // Prepend new message to buffer
    let buffer = this.state.messages;
    buffer.unshift(objectData.source + ": " + objectData.message);
    if (buffer.length > 1000) {
        buffer.pop()
    }
    this.setState({
        messages: buffer
    })
};

updateObject = (objectData) => {
    let display = document.getElementById(objectData.target);
    if ( !display ) return;

    if ( display.type === "text" || display.type === "textarea" ) {
        display.value = objectData["value"];
    } else if ( display.type === "number" ) {
        display.value = Number(objectData["value"]);
    }
};

onButton(event) {
    let cmd = event.target.id;
    if (!cmd) return;
    let args = {arguments: {command: cmd}};

    let elements = document.querySelectorAll('.' + cmd);
    elements.forEach(element => {
        args.arguments[element.name] = element.value;
    });
    args.type = "tool_command";
    args.target = "tool." + this.props.tool_id;

    send_websocket(this.id, "InfoEvents.TOOL_COMMAND", args)
}

render() {
    return(
        <div>
            <ToolStatusNode key={this.props.tool_id} id={this.props.tool_id} name={this.props.name}
                            status={this.state.tools.online_bool === true} inuse={this.state.tools.inuse === true}
                            details={this.state.tools.details} />
            {this.state.html}
            <MessageView messages={this.state.messages} />
            <ActionButton label="Shutdown" buttonEvent="ActionEvents.SHUTDOWN"
                              className="station-shutdown-button"/>

            <Modal show={!this.state.wsConnection}>
                <ModalPopup>Lost Connection to Server. Reconnecting...</ModalPopup>
            </Modal>
        </div>
    )}
}

// ************************
