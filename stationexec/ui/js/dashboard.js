class VersionStatusNode extends React.Component {
    render() {
        return(
            <React.Fragment>
                <div>
                    {this.props.name} : {this.props.versions}
                </div>
            </React.Fragment>
        )
    }
}

// ************************

class VersionStatus extends React.Component {
    allTools;
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name)
        this.state = {
            station_version: "",
            se_version: "",
        };
    }

    componentDidMount(){
        fetch("/station/status")
        .then(response => {
            response.json()
            .then((res) => {
                this.setState({
                    station_version: res['info']["station_version"],
                    se_version: res["se_version"]
                });
            });
        })
    }

    render() {
        if (Object.entries(this.props.allTools).length > 0) {
            const tools = this.props.allTools.map((n) =>
                <VersionStatusNode name={n.name} versions={n.version}/>
            );
            return(
                <div className="tool-status">
                    <h1>StationExec Version</h1>
                    {this.state.se_version}
                    <h1>Tool Versions</h1>
                    <ul className="tool-status-list">
                        {tools}
                    </ul>
                    <h1> Station Version</h1>
                    {this.state.station_version}
                </div>
            )
        }
        else {
            return ("Loading...")
        }
    }
}

// ************************

class Dashboard extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            html: "Loading...",
            activetool: ""
        };
        // this.script_tags = [];
        this.firstRender = false;
    }

    componentDidMount() {
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
        if (this.props.extras.pages.length > 0) {
            this.firstRender = true;

            let defaultTool = (this.props.extras.pages.length < 2) ? 0 : 1;
            let url = "/tool/ui/" + this.props.extras.pages[defaultTool];
            this.setState({activetool: this.props.extras.pages[defaultTool]});
            fetch(url)
                .then(response => response.text())
        } else if (this.props.dataCache.tools.length > 0) {
            this.firstRender = true;

            let defaultTool = (this.props.dataCache.tools.length < 2) ? 0 : 1;
            let url = "/tool/ui/" + this.props.dataCache.tools[defaultTool].tool_id;
            this.setState({activetool: this.props.dataCache.tools[defaultTool].tool_id});
            fetch(url)
                .then(response => response.text())
        }
    }

    render() {
        return(
            <div>
                <VersionStatus allTools={this.props.dataCache.tools}/>
            </div>
        )
    }
}
