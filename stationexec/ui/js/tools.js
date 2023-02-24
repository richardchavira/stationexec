class ToolStatusNode extends React.Component {
    inuse;
    render() {
        const icon = this.props.status ? (this.props.inuse ? "busy" : "check") : "x";
        const color = this.props.status ? (this.props.inuse ? "#f39c12" : "#89b148") : "#e05a4e";
        return(
            <React.Fragment>
                <li className={"tool-status-item" + (this.props.active ? " tool-status-item-active" : "")}>
                    <a href={"/ui/tools/" + this.props.id} onClick={this.props.handleClick}
                        className="tool-status-link">
                        <span className="tool-status-text">
                            <Icon circle icon={icon} fill={color} />
                            {this.props.name}
                        </span>
                    </a>
                </li>
            </React.Fragment>
        )
    }
}

// ************************

class ToolStatus extends React.Component {
    allTools;
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name)
    }

    render() {
        if (Object.entries(this.props.allTools).length > 0) {
            const tools = this.props.allTools.map((n) =>
                <ToolStatusNode key={n.tool_id} id={n.tool_id} name={n.name}
                                status={n.online_bool === true} inuse={n.inuse === true}
                                details={n.details} route={this.props.route}
                                handleClick={this.props.handleClick} active={n.tool_id === this.props.active} />
            );

            return(
                <div className="tool-status">
                    <ul className="tool-status-list">
                        {tools}
                    </ul>
                </div>
            )
        } else {
            return ("Loading...")
        }
    }
}

// ************************

class Tools extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            html: "Loading...",
            activetool: ""
        };
        this.script_tags = [];
        this.firstRender = false;

        this.pageOptions = htmlParseOptions((tag) => this.script_tags.push(tag),
            (evt) => this.onButton(evt));
    }

    componentDidMount() {
        ws_register(this.id, this.updateObject, "InfoEvents.OBJECT_UPDATE");
        this.fetchToolUrl()
    }

    componentDidUpdate(prevProps) {
        if (this.props.extras.pages.length === 0 &&
            this.props.dataCache.tools.length > 0 && (!this.firstRender)) {
            this.fetchToolUrl()
        } else if (this.props.extras.pages[0] !== prevProps.extras.pages[0]) {
            this.fetchToolUrl()
        }
    }

    fetchToolUrl() {
        // TODO have a nice "can't find that ui" message

        // g2 note: changing the initial selection from "Station Storage" to the next
        // tool since "Station Storage" is very slow to load and unload.
        if (this.props.extras.pages.length > 0) {
            this.firstRender = true;

            let defaultTool = (this.props.extras.pages.length < 2) ? 0 : 1;
            let url = "/tool/ui/" + this.props.extras.pages[defaultTool];
            this.setState({activetool: this.props.extras.pages[defaultTool]});
            fetch(url)
                .then(response => response.text())
                .then(rawhtml => this.setState({html: HTMLReactParser(rawhtml, this.pageOptions)}))
        } else if (this.props.dataCache.tools.length > 0) {
            this.firstRender = true;

            let defaultTool = (this.props.dataCache.tools.length < 2) ? 0 : 1;
            let url = "/tool/ui/" + this.props.dataCache.tools[defaultTool].tool_id;
            this.setState({activetool: this.props.dataCache.tools[defaultTool].tool_id});
            fetch(url)
                .then(response => response.text())
                .then(rawhtml => this.setState({html: HTMLReactParser(rawhtml, this.pageOptions)}))
        }
    }

    componentWillUnmount() {
        ws_unregister(this.id);

        // If this component added script tags to header, remove them now
        this.script_tags.forEach(tag => {
            let script_element = document.getElementById(tag);
            script_element.parentNode.removeChild(script_element);
        })
    }

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
        args.target = "tool." + (this.props.extras.pages[0] || this.props.dataCache.tools[0].tool_id);

        send_websocket(this.id, "InfoEvents.TOOL_COMMAND", args)
    }

    render() {
        return(
            <div>
                <ToolStatus allTools={this.props.dataCache.tools} route={this.props.extras.route}
                    handleClick={this.props.extras.handleClick} active={this.state.activetool} />
                <div className="tool-page-user-ui">
                    {this.state.html}
                </div>
                <MessageView messages={this.props.dataCache.messages} />
            </div>
        )
    }
}