// Copyright 2004-present Facebook. All Rights Reserved.

// TODO minify before deployment - see instructions in index.html

class Sidebar extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name)
    }

    render() {
        return (
            <div className="sidebar">
            </div>
        )
    }
}

// ************************

class Header extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name)
    }

    render() {
        return(
            <div className="header">
                <span className="header-title">{this.props.title}</span>
                <ul className="header-nav-list">
                    {this.props.children}
                </ul>
            </div>
        )
    }
}

// ************************

class Content extends React.Component {
    constructor(props) {
        // TODO now that there is the UI_DATA_REQUEST and UI_DATA_DELIVERY event
        //   pairing (see <SequenceController />), much of this object can be phased out
        //   and each object can grab its own data (except for those that need
        //   to maintain history between loads like the messages object)
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            sequence: {},
            sequence_redraw: false,
            tools: {},
            log: [],
            messages: [],
            userInputSchemas: []
        }
    }

    componentDidMount() {
        ws_register(this.id, this.updateSequence, "InfoEvents.SEQUENCE_UPDATE");
        ws_register(this.id, this.updateSequenceDraw, "InfoEvents.SEQUENCE_LOADED");
        ws_register(this.id, this.updateTool, "InfoEvents.TOOL_UPDATE");
        ws_register(this.id, this.updateMessage, "InfoEvents.MESSAGE_UPDATE");
        ws_register(this.id, this.updateMessage, "InfoEvents.ALERT_UPDATE");
        ws_register(this.id, this.updateLog, "InfoEvents.LOG");

        // TODO either generalize this or remove all of this
        ws_register(this.id, this.updateSequence, "InfoEvents.UI_DATA_DELIVERY");
        ws_register(this.id, this.getUserInputData, "InfoEvents.USER_INPUT_REQUEST");

        send_websocket(this.id, "InfoEvents.UI_DATA_REQUEST",  {requesting: "sequence_status"});
    }

    componentWillUnmount() {
        ws_unregister(this.id)
    }

    getUserInputData = (data) => {
        delete data['_event']
        this.setState((prevState) => ({
          userInputSchemas: [...prevState.userInputSchemas, data]
        }))
    }

    clearUserInputData = (uuid) => {
        this.setState((prevState) => ({
            userInputSchemas: prevState.userInputSchemas.filter((data) => data.uuid !== uuid)
        }))
    }
  
    updateSequence = (objectData) => {
        if (typeof objectData == "undefined") return;
        if (objectData.hasOwnProperty("target") && objectData.target !== this.id) return;
        if (objectData.target === this.id) {
            this.setState({
                sequence: objectData.result.data
            })
        } else {
            this.setState({
                sequence: JSON.parse(objectData.data)
            })
        }
    };

    updateSequenceDraw = (objectData) => {
        if (typeof objectData == "undefined") return;
        this.setState({
            sequence_redraw: true
        })
    };

    updateTool = (objectData) => {
        if (typeof objectData == "undefined") return;
        this.setState({
            tools: objectData.status
        })
    };

    updateMessage = (objectData) => {
        if (typeof objectData == "undefined") return;
        // Prepend new message to buffer
        let buffer = this.state.messages;

        buffer.unshift(
            {
                "message": objectData.message,
                "event": objectData._event,
                "source": objectData.source
            })

        if (buffer.length > 1000) {
            buffer.pop()
        }
        this.setState({
            messages: buffer
        })
    };

    updateLog = (objectData) => {
        if (typeof objectData == "undefined") return;
        let buffer = this.state.log;
        buffer.unshift(objectData);
        if (buffer.length > 500) {
            buffer.pop()
        }
        this.setState({
            log: buffer
        })
    };

    render() {
        const userInputData = this.state.userInputSchemas[0]
        return(
            <div id="main">
                {React.cloneElement(this.props.route.object,
                                    {extras: this.props.route.extras, dataCache: this.state})}
            
                <Modal show={this.state.userInputSchemas.length}>
                    {userInputData ?
                        <UserInputModal
                            inputData={userInputData}
                            clearInput={this.clearUserInputData}
                            key={userInputData.uuid} /> : null}
                </Modal>
            </div>
        )
    }
}

// ************************

class NavLinkItem extends React.Component {
    render() {
        return (
            <li className={this.props.active ? "active-nav-link" : null} >
                <a href={this.props.href} onClick={this.props.onClick}
                className={this.props.enabled ? "header-nav-link" : "disabled-header-nav-link"}>
                    <span className={this.props.enabled ? "header-nav-text" : "disabled-header-nav-text"}>
                        <Icon fill="currentColor" icon={this.props.icon || ""} />
                        <span className="header-nav-text-name">{this.props.title}</span>
                    </span>
                </a>
            </li>
        )
    }
}

// ************************

class App extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            route: location.pathname,
            wsConnection: true,
            isUserLoggedIn: false,
            username: "",
            mode: ""
        };
        this.firstConnectionPassed = false;

        // If user/login support is enabled
        if (this.props.userEnabled) {
            this.checkLogin().then(() => {
                // If user login is enabled don't allow any other routes except login page until user is logged in
                if (!this.state.isUserLoggedIn && this.state.route !== "/ui/user") {
                    this.setState({route: "/ui/user"});
                    window.history.pushState({}, "", "/ui/user");
                }
            });
        }
        else {
            // Remove the user page to stop the user Navbar button from displaying
            if ("/ui/user" in this.pages) {
                delete this.pages["/ui/user"];
            }
        }

        window.addEventListener("popstate", e => {
            this.setState({
                route: location.pathname,
            })
        })
    }

    componentDidMount() {
        document.title = this.props.name
        open_websocket(this.onWebsocketOpen, this.onWebsocketClose)
    }

    componentWillUnmount() {
        ws_unregister(this.id);
        close_websocket()
    }

    onWebsocketOpen = () => {
        if (this.firstConnectionPassed) {
            window.location.reload(true)
        }
        this.setState({wsConnection: true});
        this.firstConnectionPassed = true;
        send_websocket(this.id, "InfoEvents.UI_LOADED", {});

        ws_register(this.id, this.onLogin, "InfoEvents.USER_LOGGED_IN")
        ws_register(this.id, this.onLogout, "InfoEvents.USER_LOGGED_OUT")
    };

    onWebsocketClose = () => {
        this.setState({wsConnection: false});
        setTimeout(open_websocket, 3000, this.onWebsocketOpen, this.onWebsocketClose)
    };

    onLinkClick = (e) => {
        let route_update = e.target.closest("a").attributes.href.value || "/";
        window.history.pushState({}, "", route_update);
        this.setState({
            route: route_update
        });
        e.preventDefault();
    };

    onLogin = (objectData) => {
        this.setState({
            isUserLoggedIn: true,
            username: objectData.username,
            mode: objectData.mode
        })
    };

    onLogout = (objectData) => {
        this.setState({
            isUserLoggedIn: false,
            username: "",
            mode: ""
        })
    };

    checkLogin = async () => {
        if (!this.props.userEnabled) {
            return;
        }

        try {
            // Query the users tool to check if the current user is logged in
            let response = await fetch("/tool/user/auth")

            this.setState({ isUserLoggedIn: response.ok });

            // If user is logged in get user info
            if (response.ok) {
                response.json().then((json) => {
                    this.setState({
                        username: json["username"],
                        mode: json["mode"],
                    });
                });
            }
        }
        catch (e) {
            console.error(e)
        }
    }

    pages = {
        "/ui/user": { object: <User />, title: "User", icon: "user", args: {}},
        "/ui/home": { object: <Home />, title: "Home", icon: "home", args: {}},
        "/ui/station": { object: <Station />, title: "Station", icon: "station", args: {}},
        "/ui/tools": { object: <Tools />, title: "Tools", icon: "tools", args: {}},
        "/ui/report": { object: <Report />, title: "Report", icon: "report", args: {}},
        "/ui/help": { object: <Help />, title: "Help", icon: "question", args: {}},
        "/ui/dashboard": { object: <Dashboard />, title: "Dashboard", icon: "dashboard", args: {}},
    };

    getObject = (route) => {
        // Redirect index route based on user login enabled
        if (route === "/") {
            if (this.props.userEnabled) {
                route = "/ui/user";
            }
            else {
                route = "/ui/home";
            }
            window.history.pushState({}, "", route);
        }

        let additionalProps = { handleClick: this.onLinkClick, pages: [] };
        for (let val in this.pages) {
            if (route.startsWith(val) && (val !== "/") && (route !== val)) {
                let pages = route.split(val)[1];
                if (pages.startsWith("/")) pages = pages.substring(1);
                additionalProps.pages = pages.split("/");
                route = val;
                break;
            }
        }

        // If route exists
        if (route in this.pages) {
            additionalProps.route = route;
            additionalProps.args = this.pages[route].args;
            return {object: this.pages[route].object, extras: additionalProps}
        }
        else {
            // Handle request for URL that is undefined
            return {object: <h1>Error: Page Not Found</h1>, extras: additionalProps}
        }
    };

    render() {
        const active = (item) => (this.state.route === "/" && item === "/") ||
            (this.state.route.startsWith(item) && item !== "/");
        const enabled = (item) => !this.props.userEnabled || (this.state.isUserLoggedIn || item === "/ui/user");
        const links = Object.keys(this.pages).map((item) =>
            <NavLinkItem key={this.pages[item].title} active={active(item)}
                onClick={this.onLinkClick} href={item} icon={this.pages[item].icon}
                title={this.pages[item].title} enabled={enabled(item)}/>
        );

        // Only display the user banner if user tool is being used and
        // user is logged in and he current page is not the login page
        const userBannerEnabled = this.props.userEnabled &&
            this.state.isUserLoggedIn &&
            this.state.route !== "/ui/user";

        return(
            <div>
                <Sidebar />
                <Header title={this.props.name} handleClick={this.onLinkClick}>
                    {links}
                    <UserBanner enabled={userBannerEnabled} username={this.state.username} mode={this.state.mode}/>
                </Header>

                <Content route={this.getObject(this.state.route)} />

                <ActionButton label="Shutdown" buttonEvent="ActionEvents.SHUTDOWN"
                                className="station-shutdown-button"/>

                <Modal show={!this.state.wsConnection}>
                    <ModalPopup>Lost Connection to Server. Reconnecting...</ModalPopup>
                </Modal>
            </div>
        )
    }
}

// ********************************************************************************

function initialize() {
    fetch("/station/status")
        .then(response => response.json())
        .then(data => {
            const isUserEnabled = data.tools.some((tool) => tool.tool_type === "user")
            loadApp(isUserEnabled)
        })
        .catch(error => console.error(error));
};

function loadApp(isUserEnabled) {
    const domContainer = document.getElementById("main-content");
    ReactDOM.render(<App name="StationExec" userEnabled={isUserEnabled} />, domContainer);
};


initialize();
