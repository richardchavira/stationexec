class SequenceController extends React.Component {
  constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
      stationStatus: "initializing",
      stationStatusDescription: "Initializing Station",
      enforceStationOrder: false,
      dutTestCount: 0
    }
  }

  componentDidMount() {
    ws_register(this.id, this.stationStatusUpdate, "InfoEvents.STATION_HEALTH");
    ws_register(this.id, this.stationStatusUpdate, "InfoEvents.UI_DATA_DELIVERY");
    ws_register(this.id, this.getDutData, "InfoEvents.DUT_SERIAL_NUMBER_UPDATE");
    send_websocket(this.id, "InfoEvents.UI_DATA_REQUEST", { requesting: "station_health" });
    this.getDutData();
  }

  componentWillUnmount() {
    ws_unregister(this.id)
  }

  getDutData = () => {
    fetch('/tool/dut/data')
      .then(response => response.json())
      .then(json => this.setState({ dutTestCount: json.test_count }))
  }

  stationStatusUpdate = (objectData) => {
    if (objectData.hasOwnProperty("target") && objectData.target !== this.id) return;
    if (objectData.target === this.id) {
      // UI Data order has arrived
      objectData.status = objectData.result.status;
      objectData.description = objectData.result.description;
    }
    this.setState({
      stationStatus: objectData.status,
      stationStatusDescription: objectData.description,
    })
  };

  renderStationStatus = () => {
    return (
      <div className={"station-status-block ssb-" + this.state.stationStatus}>
        <span className={"station-status-text sst-" + this.state.stationStatus}>{this.state.stationStatus}</span>
        <span className={"station-status-description ssd-" + this.state.stationStatus}>{this.state.stationStatusDescription}</span>
      </div>
    )
  }

  render() {
    return (
      <div>
        {this.props.renderStationStatus ? this.renderStationStatus() : null}
        <SequenceLauncher
          stationStatus={this.state.stationStatus}
          dutTestCount={this.state.dutTestCount} />
        {/* TODO Enable for DUT routing on system level testing see PS-608qwq */}
        {/* {['Engineering', 'Troubleshooting'].includes(this.props.userMode) ? this.renderEnforceStationOrderOption() : null} */}
      </div>
    )
  }
}

// ************************

class SequenceLauncher extends React.Component {
  constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);
    this.state = {
      mode: ''
    }
  }

  componentDidMount() {
    fetch("/station/status")
      .then(response => {
          response.json()
          .then((res) => {
              console.log(res['user_info'])
              this.setState({
                  mode: res['user_info']["mode"]
              });
          });
      })
  }

  configUpdate = (objectData) => {
    this.setState({
    })
  };

  disableStartSequenceButton = () => {
    if (this.props.stationStatus !== "ready") {
      return true;
    }
    return false;
  }

  handleStartSequenceClick = (event) => {
    // Start sequence
    send_websocket(random_id(this.constructor.name), "ActionEvents.START_SEQUENCE",  {runtimedata: {}});
    event.preventDefault();
  }

  render() {
    // Load/reload current sequence file
    // Load sequence file from different file - upload
    // Upload runtime_data json file
    // Launch with multiple DUTs (based on configs queried from server)
    return (
      <div className="station-status-buttons">
        <div>
          <span className="tool-status-text">Test Count: </span>
          <span>{this.props.dutTestCount}</span>
        </div>
        <ActionButton
          label="Start Sequence"
          buttonClick={this.handleStartSequenceClick}
          buttonEvent={"ActionEvents.START_SEQUENCE"}
          disabled={this.disableStartSequenceButton()} />
        <ActionButton
          label="Stop Sequence"
          buttonEvent="ActionEvents.STOP_SEQUENCE"
          disabled={this.props.stationStatus !== "running"} />
      </div>
    )
  }
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
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCES", { number: 10 });
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
    send_websocket(this.id, "RetrievalEvents.GET_SEQUENCES", { number: 10 });
  };

  render() {
    const history = this.state.history.map((n) =>
      <tr key={n.uuid}>
        <td>
          <a href={"/ui/report/" + n.uuid} onClick={this.props.handleClick}>
            <span>
              {n.uuid.substr(0, 8)}
            </span>
          </a>
        </td>
        <td>{new Date(n.created * 1000).toLocaleTimeString([],
          { year: "numeric", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</td>
        <td>{(n.duration / 1000) + "s"}</td>
        <td className={"station-history-result-" + (n.passing === 1 ? "pass" : "fail")}>
          {(n.passing === 1 ? "Pass" : "Fail")}
        </td>
      </tr>
    );
    return (
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
    )
  }
}

class SequenceRepeater extends React.Component {

  constructor(props) {
    super(props);
    this.id = random_id(this.constructor.name);

    this.state = {
      totalSequenceReps: 1,
      currentSequenceRep: 0,
      infiniteReps: false
    };
  }

  componentDidMount() {
    ws_register(this.id, this.sequenceStarted, "InfoEvents.SEQUENCE_STARTED");
    ws_register(this.id, this.sequenceFinished, "InfoEvents.SEQUENCE_FINISHED");
    this.updateState();
  }

  componentWillUnmount() {
    ws_unregister(this.id);
  }

  updateState = () => {
    fetch('/sequence/repeater')
      .then(response => response.json())
      .then(json => {
        this.setState({
          totalSequenceReps: json.total_reps,
          currentSequenceRep: json.current_rep,
          infiniteReps: json.infinite_reps
        })
      });
  }

  onInfiniteRepChange = (val) => this.state.infiniteReps ? this.infiniteRepsTrueToFalse() : this.infiniteRepsFalseToTrue();

  infiniteRepsTrueToFalse = () => {
    const data = { infinite_reps: !this.state.infiniteReps };

    const options = {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }

    fetch('/sequence/repeater', options)
      .then(response => response.json())
      .then(json => this.setState({ infiniteReps: json.infinite_reps }));
  }

  infiniteRepsFalseToTrue = () => {
    const data = {
      infinite_reps: !this.state.infiniteReps,
      current_rep: 0
    };

    const options = {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }

    fetch('/sequence/repeater', options)
      .then(response => response.json())
      .then(json => this.setState({
        infiniteReps: json.infinite_reps,
        currentSequenceRep: json.current_rep
      }));
  }

  onRepsChange = (val) => {
    if (!this.state.infiniteReps) {
      const reps = parseInt(val.target.value);
      if (isNaN(reps)) {
        this.setState({
          totalSequenceReps: 1,
          currentSequenceRep: 0
        })
      } else this.updateReps(reps);
    }
  }

  updateReps = (val) => {
    const data = {
      total_reps: val,
      current_rep: 0
    };

    const options = {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }

    fetch('/sequence/repeater', options)
      .then(response => response.json())
      .then(json => this.setState({
        totalSequenceReps: json.total_reps,
        currentSequenceRep: 0
      }));
  }

  sequenceStarted = (objectData) => {
    fetch('/sequence/repeater')
      .then(response => response.json())
      .then(data => this.setState({ currentSequenceRep: data.current_rep }));
  }

  sequenceFinished = (objectData) => {
    fetch('/sequence/repeater')
      .then(response => response.json())
      .then(data => this.setState({ currentSequenceRep: data.current_rep }));
  }

  sequenceDisplay = () => this.state.infiniteReps ? 'INF' : this.state.totalSequenceReps;

  render() {
    return (
      <div>
        <h2>Sequence {this.state.currentSequenceRep} of {this.sequenceDisplay()}</h2>
        <label>
          Number of Sequences:
                <input
            type="number"
            value={this.state.totalSequenceReps}
            style={{ width: "50px" }}
            min="1"
            onChange={this.onRepsChange} />
        </label>
        <br />
        <label>
          Infinite Sequence:
                <input
            checked={this.state.infiniteReps}
            type="checkbox"
            name="infiniteReps"
            onChange={this.onInfiniteRepChange} />
        </label>
      </div>
    );
  }
}
