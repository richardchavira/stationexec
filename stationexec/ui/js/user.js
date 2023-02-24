const MODES_INCLUDING_DATA_OPTIONS = ['Engineering', 'Troubleshooting']
const USER_MODES = ['Production', 'Troubleshooting', 'GRR (Gauge)', 'Engineering']

class UserBanner extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            color: "",
        };
    }

    componentWillUnmount() {
        this.stopFlashing();
    }

    componentDidUpdate(prevProps) {
        if (prevProps.mode !== this.props.mode && this.props.mode !== "Production") {
            this.startFlashing();
		} 	
		if (this.props.mode === "Production") {
			this.stopFlashing();
		}
    }

    startFlashing = () => {
        const ON_COLOR = "yellow";
        const OFF_COLOR = "inherit";

        if (this.flashTimer) return;

        this.flashTimer = setInterval(() => {
            var nextColor = this.state.color === OFF_COLOR ? ON_COLOR : OFF_COLOR;
            this.setState({ color: nextColor});
        }, 750);
    };

    stopFlashing = () => {
        if (this.flashTimer) {
		  clearInterval(this.flashTimer);
		  this.setState({ color: ""});
 }
    };

    render() {
        // Don't render anything when component is not enabled
        if (!this.props.enabled) {
            return null;
        }

        return (
            <div className="user-banner" style={{ background: this.state.color }}>
                <span className="user-banner-username">User: {this.props.username}</span>
                <span className="user-banner-mode">{this.props.mode} Mode</span>
                {MODES_INCLUDING_DATA_OPTIONS.includes(this.props.mode)?<span className="data-storage-option"><SaveState/></span>:null}
            </div>
        );
    }
}


class User extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.handleChange = this.handleChange.bind(this);
        this.handleKeyUp = this.handleKeyUp.bind(this);
        this.handleLogin = this.handleLogin.bind(this);
        this.handleLogout = this.handleLogout.bind(this);
        this.state = {
            username: "",
            password: "",
            authMethod: 'mes',
            mode: "",
            role: "",
            isLoggedIn: false,
            includeDataOptions: false,
            dataLocations: [],
            dataLocation: null
        };
    }

    componentDidMount() {
        // Query the users tool to check if the current user is logged in
        fetch("/tool/user/auth")
            .then(response => {
                this.setState({ isLoggedIn: response.ok });

                // If user is logged in get user info
                if (response.ok) {
                    response.json().then((json) => {
                        this.setState({
                            username: json["username"],
                            mode: json["mode"],
                            role: json["role"]
                        });
                    });
                }
            })
            .catch(error => console.error('Authorization error:', error));
        this.getDataLocations()
    }

    getDataLocations() {
        fetch('/tool/mongo/uidata')
            .then((res) => res.json())
            .then((json) => this.setState({ dataLocations: json.data_locations }))
            .catch((err) => console.error(err))
    }

    handleChange(event) {
        const { name, value } = event.target;
        this.setState({ [name]: value });
        
        if (name === 'mode') {
            this.handleUserModeChange(value)
        }
    }

    handleUserModeChange = (mode) => {
        if (MODES_INCLUDING_DATA_OPTIONS.includes(mode)){
            this.setState({
                includeDataOptions: true
            })
        } else {
            this.setState({
                includeDataOptions: false,
                dataLocation: null
            })
        }
    }

    initializeDataLocation = () => {
        this.setState({ dataLocation: this.state.dataLocations[0] })
    }

    handleKeyUp(event) {
        if (event.key == 'Enter') {
            event.target.blur();
            this.handleLogin();
        }
        else {
            const { name, value } = event.target;
            this.setState({ [name]: value });
        }
    }

    handleAuthMethodChange = (method) => this.setState({ authMethod: method })

    handleLogin() {
        if(this.state.mode === "") {
            alert("Please select a mode.")
            return;
        }

        // Attempt to login to the system
        const options = {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                username: this.state.username,
                password: this.state.password,
                authMethod: this.state.authMethod,
                mode: this.state.mode,
                role: this.state.role,
                data_location: this.state.dataLocation
            }),
        }

        fetch("/tool/user/login", options)
            .then((response) => {
                this.setState({ isLoggedIn: response.ok });
                // If login fails alert the user with reason why
                if (!response.ok) {
                    response.json().then((json) => alert("Failed login: " + json["reason"]));
                }
                else if (response.ok) {
                    this.componentDidMount()
                }
            })
            .catch((error) => console.error("Login error:", error));
    }

    handleLogout() {
        fetch("/tool/user/logout", {method: "POST"})
        .then((response) => {
            if (response.ok) {
                this.setState({
                    username: "",
                    password: "",
                    mode: "",
                    role: "",
                    isLoggedIn: false,
                });
            }
            else {
                alert("Failed logout");
            }
        })
        .catch((error) => console.error("Logout error:", error));
    }

    render() {
        const isLoggedIn = this.state.isLoggedIn;
        let page;
        if (isLoggedIn) {
            page = (
                <UserPage label="Current User">
                    <UserInfo username={this.state.username} mode={this.state.mode} role={this.state.role}/>
                    <ActionButton id="user-logout" className="user-button-logout" label="Logout" buttonClick={this.handleLogout} />
                </UserPage>
            );
        }
        else {
            page = (
                <UserPage label="User Login">
                    <LoginForm
                        handleChange={this.handleChange}
                        handleKeyUp={this.handleKeyUp}
                        handleLogin={this.handleLogin}
                        includeDataOptions={this.state.includeDataOptions}
                        authMethod={this.state.authMethod}
                        handleAuthMethodChange={this.handleAuthMethodChange}
                        initializeDataLocation={this.initializeDataLocation}
                        handleDataLocationChange={this.handleChange}
                        dataLocations={this.state.dataLocations} />
                </UserPage>
            );
        }
        return (
            <div>
                {page}
            </div>
        );
    }
}

function UserPage(props) {
    return (
        <div>
            <table className="user-header">
                <tr>
                    <td><Icon fill="currentColor" icon={"user" || ""} size="2em" /></td>
                    <td>{props.label}</td>
                </tr>
            </table>
            <div className="user-display">
                {props.children}
            </div>
        </div>
    );
}

function ModeSelect(props) {
    const renderUserModeInputs = () => {
        return (
            USER_MODES.map((mode) => {
                return (
                    <div>
                        <input type="radio" name="mode" id={mode} value={mode} onChange={props.handleChange} />
                        <label for={mode}>{mode}</label><br/>
                    </div>
                )
            })
        )
    }

    return (
        <fieldset className="mode-border">
            <legend>Mode</legend>
            {renderUserModeInputs()}
        </fieldset>
    );
}

function UserCredentials(props) {
    return (
        <div>
            <label className="user-label">Username</label>
            <input type="text" className="user-input" name="username" onKeyUp={props.handleKeyUp} />
            <br />
            <label className="user-label">Password</label>
            <input type="password" className="user-input" name="password" onKeyUp={props.handleKeyUp} />
            <br />
        </div>
    );
}

function LoginForm(props) {
    return (
        <div>
            <ModeSelect handleChange={props.handleChange}/>
            <UserCredentials handleKeyUp={props.handleKeyUp}/>
            {props.includeDataOptions ? <DataStorageOptions
                                            initializeDataLocation={props.initializeDataLocation}
                                            handleChange={props.handleDataLocationChange}
                                            dataLocations={props.dataLocations} />
            : null }
            <AuthenticationMethodOptions
                method={props.authMethod}
                handleChange={props.handleAuthMethodChange} />
            <ActionButton id="user-button" label="Login" buttonClick={props.handleLogin} />
        </div>
    );
}

function UserInfo(props) {
    return (
        <table className="user-info">
            <tr>
                <td>Username:</td>
                <td>{props.username}</td>
            </tr>
            <tr>
                <td>Role:</td>
                <td>{props.role}</td>
            </tr>
            <tr>
                <td>Mode:</td>
                <td>{props.mode}</td>
            </tr>
        </table>
    );
}

class SaveState extends React.Component{
    id = random_id(this.constructor.name)
    state = {
        dataLocation: null
    }

    componentDidMount = () => {
        fetch('/tool/mongo/uidata')
            .then(response => response.json())
            .then((data) => this.setState({ dataLocation: data.data_location }))
            .catch((error) => console.error("Error occured in SaveState:", error))
    }

    render () {
        return(
            <div>
                {`Data Location: ${this.state.dataLocation}`}
            </div>
        )}
}

class DataStorageOptions extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            mongoToolConnected: true
        };
    }

    componentDidMount = () => {
        this.props.initializeDataLocation()
        fetch('/tool/mongo/update')
            .then((res) => res.json())
            .then((json) => this.setState({ mongoToolConnected: json.connected }))
            .catch((err) => this.setState({ mongoToolConnected: false }))
    }

    render () {
        if (this.state.mongoToolConnected == false || this.props.dataLocations.length === 0) {
            return null;
        }
        return (
            <fieldset className="mode-border">
                <legend>Data Storage Location</legend>
                <select
                    id='dataLocation'
                    name='dataLocation'
                    onChange={this.props.handleChange}>
                    {this.props.dataLocations.map((value) => (
                        <option value={value}>{value}</option>
                    ))}
                </select>
            </fieldset>
            )
        }
}

function AuthenticationMethodOptions(props) {
    const handleChange = (event) => props.handleChange(event.target.value)
    const isSelectedMethod = (method) => method === props.method

    return (
        <fieldset className="mode-border">
            <legend>Authentication Method</legend>
            <input
                type="radio"
                id="mongo"
                value="mongo"
                onChange={handleChange}
                checked={isSelectedMethod('mongo')} />
            <label for="mongo">MongoDB</label>
            <input
                type="radio"
                id="mes"
                value="mes"
                onChange={handleChange}
                checked={isSelectedMethod('mes')} />
            <label for="mes">MES</label>
        </fieldset>
        )
    }
