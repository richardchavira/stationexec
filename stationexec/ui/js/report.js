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
        )
    }
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
        )
    }
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
        )
    }
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
        )
    }
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
    }
}
