class Station extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            html: "Loading...",
            userMode: 'Production',
            stationTagData: {},
            operationPopupId: null
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

        this.getUserMode();
        this.getStationTagData();
        
        document.addEventListener("keydown", this.onEscKeyDown, false);
    }

    componentWillUnmount() {
        ws_unregister(this.id);

        // If this component added script tags to header, remove them now
        this.script_tags.forEach(tag => {
            let script_element = document.getElementById(tag);
            script_element.parentNode.removeChild(script_element);
        })
      document.removeEventListener("keydown", this.onEscKeyDown, false);
    }

    onEscKeyDown = (event) => {
      if (event.key === "Escape") {
        this.setState({ operationPopupId: null })
      }
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

    getUserMode() {
      fetch('/station/status')
        .then(response => response.json())
        .then(data => {
          const userMode = data.user_info.mode;
          if (userMode) this.setState({ userMode: userMode })
        })
        .catch(err => console.log(err))
    }

    getStationTagData = () => {
      fetch('/tool/mongo/uidata')
          .then(response => response.json())
          .then(json => this.setState({ stationTagData: json.station_tag_data }))
          .catch(err => console.log(err));
    }

    filterOperationMessages = () => {
      let operationMessages = this.props.dataCache.messages || [];
      return operationMessages.filter(data => data.source.split('.')[1] == this.state.operationPopupId || data.source == 'sequencer');
    }

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
        <div>
          <Modal show={this.state.operationPopupId ? true : false}>
            <OperationLogPopup
              messages={this.filterOperationMessages()}
              close={() => this.setState({ operationPopupId: null })}/>
          </Modal>
          <div id={this.id + "-main"}>
              <ToolStatus allTools={this.props.dataCache.tools} route={this.props.extras.route}
                  handleClick={this.props.extras.handleClick}/>
              <SequenceController userMode ={this.state.userMode} renderStationStatus={false} />
              {this.state.userMode != 'Production' ? <SequenceRepeater /> : null}
              <SequenceGraph
                openOperationPopup={(id) => this.setState({ operationPopupId: id })}
                sequence={this.props.dataCache.sequence}
                width="100%"
                height="40%"/>
              <Graphs/>
              <div>
                <SequenceTagForm />
                {this.state.stationTagData ? <StationTags tags={this.state.stationTagData} /> : null}
              </div>
              <div className="station-loaded-html">
                  {this.state.html}
              </div>
              <MessageView messageData={this.props.dataCache.messages} />
          </div>
        </div>
      )
    }
}

class SequenceTagForm extends React.Component {
  constructor(props) {
      super(props);
      this.id = random_id(this.constructor.name);
      this.state = {
        sequenceTagData: {}
      };
  }

  componentDidMount() {
    ws_register(this.id, this.sendSequenceTagData, "InfoEvents.SEQUENCE_STARTED");
    ws_register(this.id, this.getSequenceTags, "InfoEvents.SEQUENCE_FINISHED");
    this.getSequenceTags();
  }

  sendSequenceTagData = () => {
    const options = {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(this.state.sequenceTagData)
    };

    fetch('/tool/mongo/uidata', options)
        .then(response => response.json())
        .then(json => console.log('sequenceTagData: ', json))
        .catch(err => console.log(err));
    }

  getSequenceTags = () => {
    fetch('/tool/mongo/uidata')
        .then(response => response.json())
        .then(json => this.setState( {sequenceTagData: json.sequence_tag_data} ))
        .catch(err => console.log(err));
    }

  renderSequenceTags = () => {
    let inputs = [];
    for (const tag in this.state.sequenceTagData) {
      inputs.push(
        <SequenceTagInput
          key={tag}
          name={tag}
          value={this.state.sequenceTagData[tag]} />
      )
    }
    return inputs;
  }

  handleChange = (e) => {
    const [name, value] = [e.target.name, e.target.value];
    this.setState(prevState => {
      let sequenceTagData = prevState.sequenceTagData;
      sequenceTagData[name] = value;
      return { sequenceTagData };
    })
  }

  renderSequenceTagForm = () => {
    return (
      <div className='tag-form'>
        <div>
          <h3>Sequence Tags</h3>
        </div>
        <form onChange={this.handleChange} >
          {this.renderSequenceTags()}
        </form>
      </div>
    )
  }

  render() {
    return this.state.sequenceTagData ? this.renderSequenceTagForm() : null;
  }
}

const SequenceTagInput = props => {
  return (
    <div className="sequence-tag">
      <label for={props.name}>{props.name}: </label>
      <input
        type="text"
        className="value"
        name={props.name}
        value={props.value} />
    </div>
  )
}

const StationTags = props => {
  const tags = props.tags;
  let tagData = [];
  for (const tag in tags) {
    tagData.push(<li>{tag} : {tags[tag]}</li>)
  }

  return (
    <div className='tag-form'>
      <h3>Station Tags</h3>
      <ul className="station-tag-list">{tagData}</ul>
    </div>
  )
}

class Graphs extends React.Component {

    id = random_id(this.constructor.name);
    state = {
        graphs_data: [],
        open: false
    }

    componentDidMount = () => {
        ws_register(this.id, this.updateData, "InfoEvents.PLOTTER_DATA_UPDATE")
        fetch("/graphs_data")
        .then(response => {
            response.json()
            .then((res) => {
                this.setState({
                    graphs_data: res.graphs_data,
                });
            });
        })
    }

    toggleGraphs = (event) => {
        this.setState({
            open: !this.state.open
        })
    }

    updateData = (objectData) => {
        this.setState({
            graphs_data: objectData.graphs_data,
            open: true
        })
    }

    renderGraphs = () => {
        const graphs_data = [...this.state.graphs_data]
        const graphs = graphs_data.map((graph) => {
            return (
                <th>
                    <LineGraph key={graph.data.datasets.label}
                               data={graph.data}
                               options={graph.options}
                    />
                </th>)
        })
        return graphs
    }

    render () {
        return (
            <div>
                    <ActionButton label="Toggle Graphs" buttonClick={this.toggleGraphs} disabled={this.state.graphs_data.length==0}/>
                    {this.state.open?(
                            <table>
                                <tr>
                                    {this.renderGraphs()}
                                </tr>
                            </table>
                    ):null}
            </div>
        )
    }
}

class LineGraph extends React.Component {

    chartRef = React.createRef()
    chartInst = undefined
    id = random_id(this.constructor.name)

    componentDidMount = () => {
        ws_register(this.id, this.updateGraph, "InfoEvents.PLOTTER_DATA_UPDATE")
        const chartRef = this.chartRef.current.getContext("2d")
        this.chartInst = new Chart(chartRef, {
            type: "line",
            data: this.props.data,
            options: this.props.options
        })
    }

    updateGraph = (objectData) => {
        this.chartInst.data = this.props.data
        this.chartInst.options = this.props.options
        this.chartInst.update(0)
    }

    render () {
        return (
            <canvas
                id={this.id}
                ref={this.chartRef}
                height={300}
                width={450}
            />
        )
    }
}
