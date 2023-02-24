class Home extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name)
        this.state = {
            station: null,
            tools: [],
            userMode: ''
        }
    }

    componentDidMount() {
      fetch('/station/status')
        .then((res) => res.json())
        .then((station) => {
          this.setState({
            station,
            tools: station.tools,
            userMode: station.user_info.mode
          })
        })
        .catch((err) => console.error(err))
    }

    renderDutTool() {
      const dut = this.state.tools.find((tool) => tool.tool_id == 'dut')

      if (dut && !dut.dev) {
        return true
      } else {
        return false
      }
    }

    renderRoutingTool() {
      if (this.state.tools.find((tool) => tool.tool_id == 'routing')) {
        if (this.state.userMode == 'Production') {
          return true
        }
      return false
    }
  }

    render() {
        const station_info = this.state.station ?
            <div>
                <h1>{this.state.station.info.name}</h1>
            </div> : null;

        return(
            <div>
                {station_info}
                {this.renderDutTool() ? <DutInfo /> : null}
                {this.renderRoutingTool() ? <RoutingInfo /> : null}
                <SequenceController renderStationStatus={true} />
                <SequenceHistory handleClick={this.props.extras.handleClick} />

                {/* Current sequence backlog (if filled) */}
                {/*<AlertViewer />*/}
            </div>
        )
    }
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
      )
  }
}

// ************************

class DutInfo extends React.Component {
    constructor(props) {
      super(props);

      this.state = {
        tempSerialNumber: '',
        verifiedSerialNumber: '',
        status: false
      };
    };

    componentDidMount = () => {
      this.getSerialNumber();
      ws_register(this.id, this.getSerialNumber, "InfoEvents.DUT_SERIAL_NUMBER_UPDATE");
    }

    setSerialNumber = () => {
      const options = {
        "method": "POST",
        "headers": {
          "Content-Type": "application/json"
        },
        "body": JSON.stringify({
          serialNumber: this.state.tempSerialNumber
        })
      }

      this.setState({
        verifiedSerialNumber: '',
        status: false 
      }, () => {
        fetch("/tool/dut/data", options)
          .then(response => response.json())
          .then(json => {
            if (json.serial_number) {
              this.setState({
                tempSerialNumber: '',
                verifiedSerialNumber: json.serial_number,
                status: true
              })
            } else if (json.serial_number === false) {
              this.setState({ verifiedSerialNumber: "INVALID SERIAL NUMBER" })
            }
          })
          .catch((err) => console.error(err))
        })
    }

    getSerialNumber = () => {
      fetch("/tool/dut/data")
        .then(response => response.json())
        .then(json => {
          if (json.serial_number) {
            this.setState({
              verifiedSerialNumber: json.serial_number,
              status: true
            })  
          } else {
            this.setState({ status: false })
          }
        })
    }


    handleFormSubmit = (e) => {
      e.preventDefault();

      this.setSerialNumber()
    };

    handleInputChange = (e) => {
      let input = e.target;
      let value = input.value;

      this.setState({ tempSerialNumber: value })
    }

    render() {
      const status = this.state.status ? 'ready' : 'down'
      return (
        <div className={"station-status-block ssb-" + status}>
            <form onSubmit={this.handleFormSubmit} className="station-status-description">
              <label for="serialNumber">DUT Serial Number: </label>
              <input
                id="serialNumber"
                value={this.state.tempSerialNumber}
                type="text"
                name="serialNumber"
                onChange={this.handleInputChange} />
              <ActionButton
                disabled={!this.state.tempSerialNumber}
                label="Submit"
                buttonClick={this.handleFormSubmit}/>
            </form>
          <span className="station-status-description">Serial Number: {this.state.verifiedSerialNumber}</span>
        </div>
      )
    }
  }

// ************************

class RoutingInfo extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      dutSerialNumber: null,
      workOrderNumber: null,
      routeQualifierName: null,
      validatedWorkOrderNumber: null,
      routeQualifierValueOptions: [],
      routeQualifierValue: null,
      validatedRouteQualifierValue: null
    }
  }

  componentDidMount() {
    this.getWorkOrderInfo();
    this.getDutSerialNumber();
    ws_register(this.id, this.dutSerialNumberUpdate, "InfoEvents.DUT_SERIAL_NUMBER_UPDATE");
    ws_register(this.id, this.getWorkOrderInfo, "InfoEvents.SEQUENCE_FINISHED");
  }

  getDutSerialNumber = () => {
    fetch('/tool/dut/data')
      .then((res) => res.json())
      .then((json) => this.setState({ dutSerialNumber: json.serial_number }))
      .catch((err) => console.error(err))
  }

  dutSerialNumberUpdate = (event) => {
    if (event.valid) {
      this.setState({ dutSerialNumber: event.serial_number });
    }
  }

  handleInput = (e) => {
    this.setState({ [e.target.name]: e.target.value });
  }

  getWorkOrderInfo = () => {
    fetch('/tool/routing/work-order-data')
      .then((res) => res.json())
      .then((json) => {
        this.setState({ validatedWorkOrderNumber: json.work_order_number })
        if (json.route_qualifier_name) {
          this.setState({
            routeQualifierName: json.route_qualifier_name,
            routeQualifierValueOptions: json.route_qualifier_value_options,
            validatedRouteQualifierValue: json.route_qualifier_value,
            routeQualifierValue: json.route_qualifier_value_options[0]
          })
        }
      })
      .catch((err) => console.error(err))
  }

  setWorkOrderNumber = (event) => {
    event.preventDefault();
    const options = {
      "method": "POST",
      "headers": { "Content-Type": "application/json" },
      "body": JSON.stringify({
        workOrderNumber: this.state.workOrderNumber,
        routeQualifierValue: this.state.routeQualifierValue
      })
    }

    fetch("/tool/routing/work-order-data", options)
      .then((res) => {
        if (!res.ok) {
          throw new Error(res.statusText);
        }
        return res.json();
      })
      .then((json) => {
        if (!json.valid) {
          alert(json.error_message);
          return;
        }
        this.setState({
          workOrderNumber: null,
          validatedWorkOrderNumber: json.work_order_number,
          routeQualifierValue: null,
          validatedRouteQualifierValue: json.route_qualifier_value
        })
      })
      .catch((err) => alert(err.message))
  }

  renderRouteQualifierValueInput = () => {
    return (
      <div>
        <label for='routeQualifierValue'>
          Route Qualifier Value:
          <select
            id='routeQualifierValue'
            name='routeQualifierValue'
            disabled={!this.state.workOrderNumber || this.state.validatedRouteQualifierValue ? true : false}
            onChange={this.handleInput}>
            {this.state.routeQualifierValueOptions.map((value) => (
              <option value={value} >{value}</option>
            ))}
          </select>
        </label>
      </div>
    )
  }

  renderWorkOrderNumber = () => {
    if (this.state.validatedWorkOrderNumber) {
      return this.state.validatedWorkOrderNumber 
    } else {
      return (
        <input
        type="text"
        id='workOrderNumber'
        name='workOrderNumber'
        disabled={!this.state.dutSerialNumber}
        value={this.state.workOrderNumber}
        onChange={this.handleInput} />
      )
    }
  }

  render() {
    const status = this.state.validatedWorkOrderNumber ? 'ready' : 'down';
    return (
      <div className={"station-status-block ssb-" + status}>
        <form onSubmit={this.setWorkOrderNumber} className="station-status-description">
          <div>
            <label for='workOrderNumber'>
              Work Order Number: {this.renderWorkOrderNumber()}
            </label>
          </div>
          {(this.state.routeQualifierName && this.state.routeQualifierValueOptions)
            ? this.renderRouteQualifierValueInput() : null}
          <ActionButton
            label="Submit"
            disabled={!this.state.dutSerialNumber || !this.state.workOrderNumber}
            buttonClick={this.setWorkOrderNumber} />
        </form>
       </div>
    )
  }
}
