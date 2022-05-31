// Copyright 2004-present Facebook. All Rights Reserved.

// TODO minify before deployment - see instructions in index.html

class Sidebar extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name)
}

render() {
    return(
        <div className="sidebar">
        </div>
    )}
}

// ********************************************************************************

class Header extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name)
}

render() {
    return(
        <div className="header">
            <a href="/" onClick={this.props.handleClick}
                className="tool-status-link">
                <span className="header-title">{this.props.title}</span>
            </a>
            <ul className="header-nav-list">
                {this.props.children}
            </ul>
        </div>
    )}
}

// ********************************************************************************

class Help extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        help: [],
        activefile: null
    }
}

componentDidMount() {
    fetch("/station/help")
        .then(response => response.json())
        .then(help => this.setState({help}));
}

onLinkClick = (e) => {
    this.setState({activefile: e.target.closest("a").attributes.href.value})
    e.preventDefault();
};

render() {
    const help_files = this.state.help.map((n) =>
        <li key={n.file}>
            <a href={n.link} target="_blank" onClick={this.onLinkClick}>
                {n.file}
            </a>
        </li>
    );
    const pdf_doc = this.state.activefile ?
        <object data={this.state.activefile} type="application/pdf" width="100%" height="100%" /> : null
    return(
        <div>
            <div className="help-page-links">
                <ul>
                    {help_files}
                </ul>
            </div>
            <div className="help-page-doc-viewer">
                {pdf_doc}
            </div>
        </div>
    )}
}

// ********************************************************************************

class Home extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name)
    this.state = {
        station: null
    }
}

componentDidMount() {
    fetch("/station/status")
        .then(response => response.json())
        .then(station => this.setState({station}))
}

render() {
    const station_info = this.state.station ?
        <div>
            <h1>{this.state.station.info.name}</h1>
        </div> : null;
    return(
        <div>
            {station_info}
            <SequenceController />
            <SequenceHistory handleClick={this.props.extras.handleClick} />
            {/* Current sequence backlog (if filled) */}
            {/*<AlertViewer />*/}
        </div>
    )}
}

// ************************

class SequenceController extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        status: "initializing",
        description: "Initializing Station",
    }
}

componentDidMount() {
    ws_register(this.id, this.statusUpdate, "InfoEvents.STATION_HEALTH");
    ws_register(this.id, this.statusUpdate, "InfoEvents.UI_DATA_DELIVERY");
    send_websocket(this.id, "InfoEvents.UI_DATA_REQUEST",  {requesting: "station_health"});
}

componentWillUnmount() {
    ws_unregister(this.id)
}

statusUpdate = (objectData) => {
    if (objectData.hasOwnProperty("target") && objectData.target !== this.id) return;
    if (objectData.target === this.id) {
        // UI Data order has arrived
        objectData.status = objectData.result.status;
        objectData.description = objectData.result.description;
    }
    this.setState({
        status: objectData.status,
        description: objectData.description,
    })
};

render() {
    return(
        <div>
            <div className={"station-status-block ssb-" + this.state.status}>
                <span className={"station-status-text sst-" + this.state.status}>{this.state.status}</span>
                <span className={"station-status-description ssd-" + this.state.status}>{this.state.description}</span>
                <SequenceLauncher status={this.state.status} />
            </div>
        </div>
    )}
}

// ************************

class SequenceLauncher extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {

    }
}

configUpdate = (objectData) => {
    this.setState({
    })
};

render() {
    // Load/reload current sequence file
    // Load sequence file from different file - upload
    // Upload runtime_data json file
    // Launch with multiple DUTs (based on configs queried from server)
    return(
        <div className="station-status-buttons">
            <ActionButton label="Start Sequence" buttonEvent="ActionEvents.START_SEQUENCE"
                          disabled={this.props.status !== "ready"}/>
            <ActionButton label="Stop Sequence" buttonEvent="ActionEvents.STOP_SEQUENCE"
                          disabled={this.props.status !== "running"}/>
        </div>
    )}
}

// ************************

class SequenceHistory extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.timer = null;
    this.state = {
        history: []
    }
}

componentDidMount() {
    ws_register(this.id, this.historyUpdate, "InfoEvents.SEQUENCE_FINISHED");
    ws_register(this.id, this.historyUpdate, "InfoEvents.SEQUENCE_FAILED");
    ws_register(this.id, this.historyUpdate, "InfoEvents.SEQUENCE_ABORTED");
    ws_register(this.id, this.historyUpdate, "InfoEvents.STORAGE_COMPLETE");

    ws_register(this.id, this.statusUpdate, "InfoEvents.UI_DATA_DELIVERY");
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCES",  {number: 10});
}

componentWillUnmount() {
    ws_unregister(this.id);
}

statusUpdate = (objectData) => {
    if (objectData.target !== this.id) return;
    this.setState({
        history: objectData.result || []
    })
};

historyUpdate = (objectData) => {
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCES",  {number: 10});
};

render() {
    const history = this.state.history.map((n) =>
            <tr key={n.uuid}>
                <td>
                    <a href={"/ui/report/" + n.uuid} onClick={this.props.handleClick}>
                        <span>
                            {n.uuid.substr(0, 8) }
                        </span>
                    </a>
                </td>
                <td>{new Date(n.created * 1000).toLocaleTimeString([],
                    {year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit"})}</td>
                <td>{(n.duration / 1000) + "s"}</td>
                <td className={"station-history-result-" + (n.passing === 1 ? "pass" : "fail")}>
                    {(n.passing === 1 ? "Pass" : "Fail")}
                </td>
            </tr>
        );
    return(
        <div>
            <table className="station-history-table">
                <thead>
                    <tr>
                        <th>Sequence</th>
                        <th>Run Date</th>
                        <th>Duration</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {history}
                </tbody>
            </table>
        </div>
    )}
}

// ************************

class AlertViewer extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        alerts: []
    }
}

componentDidMount() {
    ws_register(this.id, this.statusUpdate, "InfoEvents.ALERT_UPDATE");
    ws_register(this.id, this.statusUpdate, "InfoEvents.POPUP_UPDATE");
}

componentWillUnmount() {
    ws_unregister(this.id)
}

statusUpdate = (objectData) => {
    this.setState({
        alerts: this.state.alerts.push(objectData.alert)
    })
};

render() {
    return(
        <div>
            <MessageView messages={this.state.alerts}/>
        </div>
    )}
}

// ********************************************************************************

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
    )}
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
    }}
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
    if (this.props.extras.pages.length > 0) {
        this.firstRender = true;
        let url = "/tool/ui/" + this.props.extras.pages[0];
        this.setState({activetool: this.props.extras.pages[0]});
        fetch(url)
            .then(response => response.text())
            .then(rawhtml => this.setState({html: HTMLReactParser(rawhtml, this.pageOptions)}))
    } else if (this.props.dataCache.tools.length > 0) {
        this.firstRender = true;
        let url = "/tool/ui/" + this.props.dataCache.tools[0].tool_id;
        this.setState({activetool: this.props.dataCache.tools[0].tool_id});
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
    )}
}

// ********************************************************************************

class Report extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        "end": this.formatTimeString(),
        "start": this.formatTimeString(new Date(new Date().setDate(new Date().getDate() - 7))),
        "sequences": [],
        "operations": [],
        "results": {},
        "selectedSequence": null,
        "activeSequence": {},
    };
}

componentDidMount() {
    ws_register(this.id, this.onDataArrival, "InfoEvents.UI_DATA_DELIVERY");

    if (this.props.extras.pages.length > 0) {
        document.getElementById("report-search-by-value-input").value = this.props.extras.pages[0];
        this.searchByValue(this.props.extras.pages[0]);
    } else {
        // Initialize page as if the date search button had been pressed
        this.buttonClick({target: {id: "report-search-by-date"}})
    }
}

componentWillUnmount() {
    ws_unregister(this.id);
}

buttonClick = (e) => {
    if (e.target.id === "report-search-by-date") {
        let start = document.getElementById("report-search-by-date-start").value;
        let end = document.getElementById("report-search-by-date-end").value;
        this.searchByDate(start, end)
    } else if (e.target.id === "report-search-by-value") {
        let uuid = document.getElementById("report-search-by-value-input").value;
        this.searchByValue(uuid);
    }
};

searchByDate = (start, end) => {
    let args = {starttime: start, endtime: end, number: null};
    this.fetchData(args)
};

searchByValue = (uuid) => {
    let args = {sequenceuuid: uuid};
    this.fetchData(args)
};

fetchData = (args) => {
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCES",  args);
};

formatTimeString = (time = new Date()) => {
    // Format the time correctly for the date controls
    // ISO String gives: "YYYY-MM-DDTHH:MM:SS.MMMZ"
    // split on the "T" to get an array with Date in 0 and Time in 1
    return time.toISOString().split("T")[0]
};

dateChange = (e) => {
    if (e.target.name === "end") {
        this.setState({end: e.target.value});
    } else if (e.target.name === "start"){
        this.setState({start: e.target.value});
    }
};

onSeqSelect = (e) => {
    let seqid = e.target.value.split(" ")[0];
    let activeSequence = {};
    for (let seq in this.state.sequences) {
        if (this.state.sequences[seq].uuid.startsWith(seqid)) {
            activeSequence = this.state.sequences[seq];
            break;
        }
    }
    this.setState({
        selectedSequence: e.target.value,
        activeSequence: activeSequence
    });
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCE_OPERATIONS",  {sequenceuuid: seqid});
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCE_RESULTS",  {sequenceuuid: seqid});
};

onDataArrival = (objectData) => {
    if (objectData.target !== this.id) return;

    if (objectData.request_event === "RetrievalEvents.GET_SEQUENCES") {
        this.setState({sequences: objectData.result || []})
    } else if (objectData.request_event === "RetrievalEvents.GET_SEQUENCE_OPERATIONS") {
        this.setState({operations: objectData.result || []})
    } else if (objectData.request_event === "RetrievalEvents.GET_SEQUENCE_RESULTS") {
        this.setState({results: objectData.result || {}})
    }
};

render() {
    const fixPassingState = (state, passing) => {
        if (state === 100 && passing === 0)
            return 140;
        else
            return state
    };
    const sequences = this.state.sequences ? this.state.sequences.map((n) =>
        <option key={n.uuid}>
            {n.uuid.substr(0, 8) + " " + new Date(n.created * 1000).toLocaleTimeString(
                [], {year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit"})
            + " " + (n.passing === 1 ? "Pass" : "Fail") }
        </option>
    ) : null;

    let stateToText = {
        0: "Ready",
        100: "Complete",
        105: "Waiting on Tool",
        120: "Requeued",
        130: "Error in Execution",
        140: "Result Failed",
        150: "Skipped",
        200: "Aborted",
    };
    const operations = this.state.operations ? this.state.operations.map((n) =>
        <tr key={n.uuid}>
            <td>
                <span>
                    {n.name}
                </span>
            </td>
            <td>{(n.duration / 1000) + "s"}</td>
            <td className={"operation-history-result-" + (
                fixPassingState(n.exitcode, n.passing) === 100 ? "pass" : "else")}>
                {stateToText[fixPassingState(n.exitcode, n.passing)]}
            </td>
        </tr>
    ) : <div>None</div>;
    return(
        <div>
            <div className="report-container">
                <div className="report-select-container">
                    <select className="report-sequence-view" size="20" onClick={this.onSeqSelect}>
                        {sequences}
                    </select>
                    <div>
                        <div>
                            <input id="report-search-by-value-input"/>
                            <br />
                            <ActionButton id="report-search-by-value" label="Search By UUID" buttonClick={this.buttonClick}/>
                        </div>
                        <div>
                            <input type="date" name="start" value={this.state.start} onChange={this.dateChange}
                                   max={this.state.end} id="report-search-by-date-start"/>
                            <input type="date" name="end" value={this.state.end} onChange={this.dateChange}
                                   max={this.formatTimeString()} min={this.state.start} id="report-search-by-date-end"/>
                            <br/>
                            <ActionButton id="report-search-by-date" label="Search By Date Range"
                                          buttonClick={this.buttonClick}/>
                        </div>
                    </div>
                </div>
                <ResultTree title={this.state.selectedSequence} operations={this.state.operations}
                        results={this.state.results} sequence={this.state.activeSequence} />
            </div>
        </div>
    )}
}

// ************************

class ResultTree extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
}

render() {
    const fixPassingState = (state, passing) => {
        if (state === 100 && passing === 0)
            return 140;
        else
            return state
    };
    let stateToText = {
        0: "Ready",
        100: "Complete",
        105: "Waiting on Tool",
        120: "Requeued",
        130: "Error in Execution",
        140: "Result Failed",
        150: "Skipped",
        200: "Aborted",
    };
    const res = this.props.results;
    const operations = this.props.operations ? this.props.operations.map((n) =>
        <ResultOpNode key={n.uuid} name={n.name} duration={(n.duration / 1000) + "s"}
                      className={"operation-history-result-" + (fixPassingState(
                          n.exitcode, n.passing) === 100 ? "pass" : "else")}
                      status={stateToText[fixPassingState(n.exitcode, n.passing)]}
                      results={res[n.name]} />) : <div>None</div>;

    if (!this.props.title)
        return null;

    const exitText = this.props.sequence ? this.props.sequence.info.exit_reason : null;
    const exitReason = exitText ?
        <tr>
            <td colSpan="3" className={"operation-history-result-" +
                (this.props.title.includes("Pass") ? "pass" : "else")}>
                {exitText}
            </td>
        </tr> : null;

    return(
        <div className="report-detail-container">
            <table className="operation-history-table" width="400px">
                <thead>
                    <tr>
                        <th>Operation</th>
                        <th>Duration</th>
                        <th>State</th>
                    </tr>
                    <tr>
                        <th colSpan="3" className={"operation-history-result-" +
                            (this.props.title.includes("Pass") ? "pass" : "else")}>
                            {this.props.title}
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {exitReason}
                    {operations}
                </tbody>
            </table>
        </div>
    )}
}

// ************************

class ResultOpNode extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        expanded: false
    }
}

expandClick = (e) => {
    this.setState({expanded: !this.state.expanded})
};

render() {
    const results = (this.props.results && this.props.results.length > 0 && this.state.expanded) ?
        this.props.results.map((n) =>
            <ResultDisplayNode key={n.uuid} resultData={n}/>) : null;
    const drawerIcon = (this.props.results && this.props.results.length > 0) ?
        <Icon icon="caret" rotate={this.state.expanded}/> : null;
    return(
        <React.Fragment>
            <tr onClick={this.expandClick}>
                <td className={(drawerIcon ? "operation-history-table-drawer-cell" : "")}>
                    {drawerIcon}<span>{this.props.name}</span>
                </td>
                <td>{this.props.duration}</td>
                <td className={this.props.className}>{this.props.status}</td>
            </tr>
            {results}
        </React.Fragment>
    )}
}

// ************************

class ResultDisplayNode extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
}

render() {
    const rd = this.props.resultData;
    const description = rd.description ? <span>{rd.description}<br/></span> : null;

    return(
        <tr>
            <td colSpan="2" className="operation-history-table-result-row">
                <span><b>{rd.name}</b></span><br/>
                {description}
                <span>Value: <b>{rd.value}</b></span><br/>
                <ResultCriteria operator={rd.operator} value={rd.value}
                                operand2={rd.operand2} operand3={rd.operand3}/>
            </td>
            <td className={"operation-history-result-" + (rd.passing ? "pass" : "else")}>
                {rd.passing ? "Pass" : "Fail"}</td>
        </tr>
    )}
}

// ************************

class ResultCriteria extends React.Component {
constructor(props) {
    super(props);
}

render() {
    if (this.props.operator === "inrange") {
        return(
            <span className="operation-history-table-result-criteria">
                {this.props.operand2 + " <= "} <b>{this.props.value}</b> {" <= " + this.props.operand3}
            </span>
        )
    } else if (this.props.operator === "!inrange") {
        return(
            <span className="operation-history-table-result-criteria">
                <b>{this.props.value}</b> {" < " + this.props.operand2 + " OR " + this.props.operand3}
                <b>{this.props.value}</b>
            </span>
        )
    } else {
        return(
            <span className="operation-history-table-result-criteria">
                <b>{this.props.value}</b> {" " + this.props.operator + " " + this.props.operand2 }
            </span>
        )
    }
}}

// ********************************************************************************

class Station extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        html: "Loading..."
    };
    this.script_tags = [];

    this.pageOptions = htmlParseOptions((tag) => this.script_tags.push(tag),
        (evt) => this.onButton(evt));
}

componentDidMount() {
    ws_register(this.id, this.updateObject, "InfoEvents.OBJECT_UPDATE");

    fetch("/station")
        .then(response => response.text())
        .then(rawhtml => this.setState({html: HTMLReactParser(rawhtml, this.pageOptions)}))
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
    args.type = "station_command";
    args.target = "station";

    send_websocket(this.id, "InfoEvents.STATION_COMMAND", args)
}

render() {
    return(
        <div id={this.id + "-main"}>
            <ToolStatus allTools={this.props.dataCache.tools} route={this.props.extras.route}
                handleClick={this.props.extras.handleClick}/>
            <div style={{"marginTop": "5px"}}>
                <ActionButton label="Start Sequence" buttonEvent="ActionEvents.START_SEQUENCE" />
                <ActionButton label="Stop Sequence" buttonEvent="ActionEvents.STOP_SEQUENCE" />
            </div>
            <SequenceGraph sequence={this.props.dataCache.sequence} width="100%" height="40%"/>
            <div className="station-loaded-html">
                {this.state.html}
            </div>
            <MessageView messages={this.props.dataCache.messages} />
        </div>
    )}
}

// ************************

class ProgressCircle extends React.Component{
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        mouse: false
    }
}

static makeArc(outer, inner=0, start=0, end=100) {
    let arc = d3_arc()
      .outerRadius(outer)
      .innerRadius(inner)
      .startAngle(start)
      .endAngle(2 * Math.PI * (end / 100));
    return arc();
}

mouseOver = () => {
    this.setState({mouse: true});
    this.props.hover(true, this.props.label)
};

mouseOut = () => {
    this.setState({mouse: false});
    this.props.hover(false)
};

render() {
    const hoverClass = "progress-circle-hover" + (this.state.mouse ? " is-progress-hover" : "");
    const zoom = Math.max(Math.min(1.5, 1 / this.props.zoom), 1);
    const transform = "translate(" + this.props.x + "," + this.props.y + ") scale(" + zoom + ")";

    const complete = (this.props.complete < 0) ? 30 : this.props.complete;
    const spinClass =  (this.props.complete < 0) ? " progress-circle-rotate" : "";

    return(
        <g id={this.props.id} className="graphProgressNode" transform={transform}
           onMouseEnter={this.mouseOver} onMouseLeave={this.mouseOut}>
            <path className={hoverClass}
                  d={ProgressCircle.makeArc(this.props.radius * 1.25)} />
            <path
                className="progress-circle-inner"
                  d={ProgressCircle.makeArc(this.props.radius * 0.9)} />
            <path className="progress-circle-outer"
                  d={ProgressCircle.makeArc(this.props.radius, this.props.radius * 0.5)} />
            <path className={"progress-circle-fill" + spinClass}
                  d={ProgressCircle.makeArc(this.props.radius,
                                  this.props.radius * 0.5,
                                  0, complete)} />
            <g transform="scale(1.25) translate(-8, -8)">
                {this.props.icon}
            </g>
        </g>
    )}
}

// ************************

class GraphNode extends React.Component{
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);

    let s_Idle = 0;
    let s_Completed = 100;
    let s_Waiting = 105;
    let s_Requeued = 120;
    let s_Failed = 130;
    let s_ResultFailure = 140;
    let s_Skipped = 150;
    let s_Aborted = 200;

    this.stateToIcon = {};
    this.stateToIcon[s_Completed] = "check";
    this.stateToIcon[s_Waiting] = "busy";
    this.stateToIcon[s_Requeued] = "requeue";
    this.stateToIcon[s_Failed] = "exclaim";
    this.stateToIcon[s_ResultFailure] = "x";
    this.stateToIcon[s_Skipped] = "none";
    this.stateToIcon[s_Aborted] = "abort";

    this.stateToIconFill = {};
    this.stateToIconFill[s_Completed] = "#89b148";
    this.stateToIconFill[s_Waiting] = "#f39c12";
    this.stateToIconFill[s_Requeued] = "#6495ed";
    this.stateToIconFill[s_Failed] = "#e05a4e";
    this.stateToIconFill[s_ResultFailure] = "#cf5000";
    this.stateToIconFill[s_Skipped] = "#777777";
    this.stateToIconFill[s_Aborted] = "#8b0000";
}

render() {
    let statusCode = this.props.code;
    let complete = statusCode;
    let icon = null;

    if (this.props.code === 100 && this.props.passing === false)
        // If code is 100 (operation completed) but it did not pass (passing == 0)
        //   then one or more of the results failed - results failure code is 140
        statusCode = 140;

    //if ((complete > 0 && complete < 100) && this.props.avgduration === 1) {
    if (complete > 0 && complete < 100) {
        complete = -1
    }
    // TODO add this back in if showing an incrementing progress circle is useful
    // else if (complete > 0 && complete < 100) {
    //    // lock to 99 and switch to spinning if it takes longer than planned?
    //    complete = ((this.props.duration_ms / 1000) / this.props.avgduration) * 100
    //}
    else if (complete >= 100) {
        complete = 100;
        icon = <Icon circle border icon={this.stateToIcon[statusCode]}
                fill={this.stateToIconFill[statusCode]} />
    }
    return(
        <g id={this.props.id}>
            <ProgressCircle radius={this.props.radius} zoom={this.props.zoom} x={this.props.x}
                y={this.props.y} complete={complete} icon={icon} hover={this.props.hover}
                duration_ms={this.props.duration_ms} avgduration={this.props.avgduration}
                label={this.props.id} status={statusCode}/>
        </g>
    )}
}

// ************************

class RunningStatus extends React.Component{
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
    }
}

render() {
    let stateToText = {
        0: "Ready",
        100: "Complete",
        105: "Waiting on Tool",
        120: "Requeued",
        130: "Error in Execution",
        140: "Result Failed",
        150: "Skipped",
        200: "Aborted",
    };
    const running_nodes = this.props.nodes.map((v) => {
        return ![0, 100, 130, 140, 150, 200].includes(v.code) ?
            <div>
                <b>{v.label}</b> <br/>
                {parseFloat((v.duration_ms / 1000.0)).toFixed(2) +
                "s / " + parseFloat(v.avgduration).toFixed(2) + "s (avg)"} <br/>
                {(v.code > 0 && v.code < 100) ? "Running" : stateToText[v.code]}
            </div>
        : null;
        }
    );
    const info_nodes = this.props.nodes.map((v) => {
        return [100, 130, 140, 150, 200].includes(v.code) ?
            <div>
                <b>{v.label}</b> <br/>
                {parseFloat((v.duration_ms / 1000.0)).toFixed(2) +
                "s / " + parseFloat(v.avgduration).toFixed(2) + "s (avg)"} <br/>
                {(v.code > 0 && v.code < 100) ? "Running" : stateToText[v.code]}
            </div>
        : null;
        }
    );
    return(
        <div className="sequence-active-operations">
            <div className="sequence-active-operations-left">
                {running_nodes}
            </div>
            <div className="sequence-active-operations-right">
                {info_nodes}
            </div>
        </div>
    )}
}

// ************************

class SequenceGraph extends React.Component {
constructor(props) {
    super(props);
    this.graph_drawn = false;
    this.id = random_id(this.constructor.name);
    this.state = {
        nodeRadius: 9.5,
        rankSep: 75,
        zoom: 1,
        translate: [0, 0],
        clusters: [],
        nodes: [],
        edges: [],
        isHovering: false,
        hoverOperation: null
    }
}

componentDidMount() {
    ws_register(this.id, this.drawGraph, "InfoEvents.SEQUENCE_LOADED");
    if (Object.entries(this.props.sequence).length > 0 && this.graph_drawn !== true) {
        this.drawGraph();
    }
    window.addEventListener("resize", this.resizeHelper);
}

componentDidUpdate(prevProps) {
    if (this.props.sequence.operations !== prevProps.sequence.operations) {
        this.drawGraph();
    }
    if (Object.entries(this.props.sequence).length > 0 && this.graph_drawn !== true) {
        this.drawGraph();
    }
    this.resizeHelper();
}

componentWillUnmount() {
    ws_unregister(this.id);
    window.removeEventListener("resize", this.resizeHelper);
}

mouseHovering = (isHovering, hoverOperation) => {
    this.setState({isHovering, hoverOperation})
};

resizeHelper = () => {
    if (this.state.isHovering) return;
    let resizeValues = this.resizeGraph();
    if (resizeValues && (resizeValues.zoom !== this.state.zoom)) {
        this.setState({
            zoom: resizeValues.zoom,
            translate: resizeValues.translate,
        })
    }
};

resizeGraph = () => {
    if (!document.getElementById("sequence-graph")) return;
    let svgGroup = document.getElementById("sequence-graph-group");
    let svgElement = document.getElementById("sequence-graph").getBoundingClientRect();
    let svgGroupLocal = document.getElementById("sequence-graph-group").getBBox();

    let padding = 20;
    let zoomScale = Math.min((svgElement.width / (svgGroupLocal.width + padding)),
                             (svgElement.height / (svgGroupLocal.height + padding)));
    svgGroup.setAttribute("transform", "scale(" + zoomScale + ")");

    svgGroupLocal = document.getElementById("sequence-graph-group").getBBox();
    let svgGroupWorld = document.getElementById("sequence-graph-group").getBoundingClientRect();
    let xCenterOffset = Math.floor((svgElement.width - svgGroupWorld.width) / 2) / zoomScale;
    let yCenterOffset = Math.floor((svgElement.height - svgGroupWorld.height) / 2) / zoomScale;
    xCenterOffset -= svgGroupLocal.x;
    yCenterOffset -= svgGroupLocal.y;
    svgGroup.setAttribute("transform", "scale(" + zoomScale + ") translate(" + xCenterOffset + ", "
                            + yCenterOffset + ")");

    return({zoom: zoomScale, translate: [xCenterOffset, yCenterOffset]})
};

drawGraph = () => {
    // Create a new directed graph
    let g = new dagre.graphlib.Graph({compound: true});

    // Set an object for the graph label
    g.setGraph({
        rankdir: "LR",
        //align: "UL",
        nodesep: 30,
        ranksep: this.state.rankSep,
        marginx: 10,
        marginy: 10
    });
    g.setDefaultEdgeLabel(function() { return {}; });

    g.setNode("top-group", {label: "--graph-group"});
    g.setNode("bottom-group", {label: "--graph-group"});

    this.props.sequence.operations.forEach((n) => {
        g.setNode(n.opid, {
            id: n.uuid,
            label: n.opid,
            code: n.exitcode,
            avgduration: n.avgduration,
            duration_ms: n.duration_ms,
            passing: n.passing,
            padding: 12,
            paddingTop: 3,
            paddingBottom: 8,
        })
    });
    this.props.sequence.operations.forEach((n) => {
        n.dependencies.forEach((d) => {
            g.setEdge(d, n.opid)
        })
    });
    this.props.sequence.loops.forEach((l) => {
        let loopGroup = random_id("loop-group", length=5);
        g.setNode(loopGroup, {label: "--graph-group", class: "graph-loop-group"});
        l.members.forEach((m) => {
            g.setParent(m, loopGroup)
        })
    });
    this.props.sequence.entrynodes.forEach((n) => {
        g.setParent(n, "top-group");
    });
    this.props.sequence.exitnodes.forEach((n) => {
        g.setParent(n, "bottom-group");
    });

    dagre.layout(g);

    let positions = Array();
    g.nodes().forEach((v) => {
        let node = g.node(v);
        if (node.label !== "--graph-group") {
            positions.push({
                label: node.label,
                x: node.x,
                y: node.y,
                id: v,
                code: node.code,
                avgduration: node.avgduration,
                duration_ms: node.duration_ms,
                passing: node.passing
            })
        }
    });

    let edges = Array();
    g.edges().forEach(e => {
        let points = Array();
        let source = g.node(e.v);
        let target = g.node(e.w);
        points.push([source.x, source.y]);
        g.edge(e).points.forEach(p => points.push([p.x, p.y]));
        points.push([target.x, target.y]);
        edges.push({
            points: points,
            id: e.v + ">" + e.w,
        })
    });

    let clusters = Array();
    this.props.sequence.loops.forEach((l) => {
        let nodeCoords = l.members.map(n => g.node(n));
        let min = nodeCoords.reduce((o, n) => [Math.min(o[0], n.x), Math.min(o[1], n.y)],
                                              [nodeCoords[0].x, nodeCoords[0].y]);
        let max = nodeCoords.reduce((o, n) => [Math.max(o[0], n.x), Math.max(o[1], n.y)],
                                              [nodeCoords[0].x, nodeCoords[0].y]);
        clusters.push({
            min: min,
            max: max,
            id: random_id("loop-cluster", length=5)
        })
    });

    this.setState({
        nodes: positions,
        edges: edges,
        clusters: clusters
    });

    this.graph_drawn = true;
};

hoverNodeMaker = () => {
    let stateToText = {
        0: "Ready",
        100: "Complete",
        105: "Waiting on Tool",
        120: "Requeued",
        130: "Error in Execution",
        140: "Result Failed",
        150: "Skipped",
        200: "Aborted",
    };

    if (this.state.hoverOperation === null || this.state.hoverOperation === undefined) return null;
    let nodeIndex = -1;
    for (let i in this.state.nodes) {
        if (this.state.nodes[i].label === this.state.hoverOperation) {
            nodeIndex = i;
            break;
        }
    }
    if (nodeIndex === -1) return null;
    let node = this.state.nodes[nodeIndex];

    let statusMsg = (node.code > 0 && node.code < 100) ? "Running" : stateToText[node.code];
    return <div className="sequence-graph-hover-message">
               <b>{node.label}</b> <br />
               {parseFloat((node.duration_ms / 1000.0)).toFixed(2) +
                   "s / " + parseFloat(node.avgduration).toFixed(2) + "s (avg)"} <br />
               {statusMsg}
           </div>;
};

render() {
    if (Object.entries(this.props.sequence).length > 0) {
        let pad = 20;
        const clusters = this.state.clusters.map((c) =>
            <g key={c.id} className="cluster">
                <rect x={c.min[0] - pad} y={c.min[1] - pad} rx="5"
                      width={(c.max[0] - c.min[0]) + (pad * 2)}
                      height={(c.max[1] - c.min[1]) + (pad * 2)} />
            </g>
        );
        const nodes = this.state.nodes.map((v) =>
            <GraphNode id={v.label} key={v.id} x={v.x} y={v.y} avgduration={v.avgduration}
                duration_ms={v.duration_ms} radius={this.state.nodeRadius} zoom={this.state.zoom} code={v.code}
                hover={this.mouseHovering} passing={v.passing}/>
        );
        const gen = d3_line().curve(d3_curveBasis);
        const edges = this.state.edges.map((e) =>
            <g key={e.id} className="edgePath">
                <path className="sequence-graph-edges" d={gen(e.points)} stroke="black"
                    fill="none" />
            </g>
        );
        const hoverNode = this.hoverNodeMaker();

        return(
            <div>
                <RunningStatus nodes={this.state.nodes}/>
                <div className="sequence-holder">
                    <div className="sequence-graph-hover-box">
                        {hoverNode}
                    </div>
                    <svg id="sequence-graph">
                        <g id="sequence-graph-group">
                            <g className="clusters">
                                {clusters}
                            </g>
                            <g className="edgePaths">
                                {edges}
                            </g>
                            <g className="nodes">
                                {nodes}
                            </g>
                        </g>
                    </svg>
                </div>
            </div>
        )
    } else {
        return ("Start sequence to view graph...")
    }}
}

// ********************************************************************************

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
    send_websocket(this.id, "InfoEvents.UI_DATA_REQUEST",  {requesting: "sequence_status"});
}

componentWillUnmount() {
    ws_unregister(this.id)
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
    buffer.unshift(objectData.source + ": " + objectData.message);
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
    return(
        <div id="main">
            {React.cloneElement(this.props.route.object,
                                {extras: this.props.route.extras, dataCache: this.state})}
        </div>
    )}
}

// ************************

class NavLinkItem extends React.Component {
render() {
    return (
        <li className={this.props.active ? "active-nav-link" : null} >
            <a href={this.props.href} onClick={this.props.onClick}
               className="header-nav-link">
                <span className="header-nav-text">
                    <Icon fill="currentColor" icon={this.props.icon || ""} />
                    <span className="header-nav-text-name">{this.props.title}</span>
                </span>
            </a>
        </li>
    )}
}

// ************************

class App extends React.Component {
constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
        route: location.pathname,
        wsConnection: true,
    };
    this.firstConnectionPassed = false;

    window.addEventListener("popstate", e => {
        this.setState({
            route: location.pathname,
        })
    })
}

componentDidMount() {
    // ws_register(this.id, <method>, <event>)
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

pages = {
    "/": { object: <Home />, title: "Home", icon: "home", args: {}},
    "/ui/station": { object: <Station />, title: "Station", icon: "station", args: {}},
    "/ui/tools": { object: <Tools />, title: "Tools", icon: "tools", args: {}},
    "/ui/report": { object: <Report />, title: "Report", icon: "report", args: {}},
    "/ui/help": { object: <Help />, title: "Help", icon: "question", args: {}},
};

getObject = (route) => {
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
    additionalProps.route = route;
    additionalProps.args = this.pages[route].args;
    return {object: this.pages[route].object, extras: additionalProps}
};

render() {
    const active = (item) => (this.state.route === "/" && item === "/") ||
        (this.state.route.startsWith(item) && item !== "/");
    const links = Object.keys(this.pages).map((item) =>
        <NavLinkItem key={this.pages[item].title} active={active(item)}
            onClick={this.onLinkClick} href={item} icon={this.pages[item].icon}
            title={this.pages[item].title} />
    );

    return(
        <div>
            <Sidebar />
            <Header title="StationExec" handleClick={this.onLinkClick}>
                {links}
            </Header>

            <Content route={this.getObject(this.state.route)} />

            <Clock />
            <ActionButton label="Shutdown" buttonEvent="ActionEvents.SHUTDOWN"
                              className="station-shutdown-button"/>
            <Modal show={!this.state.wsConnection}>
                <ModalPopup>Lost Connection to Server. Reconnecting...</ModalPopup>
            </Modal>
        </div>
    )}
}

// ********************************************************************************

const domContainer = document.getElementById("main-content");
ReactDOM.render(<App name="StationExec" />, domContainer);
