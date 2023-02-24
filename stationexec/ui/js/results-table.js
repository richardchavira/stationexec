class ArteResultsTable extends React.Component {
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.table_drawn = false;
        this.objectUpdate = this.objectUpdate.bind(this);
        this.sequenceStarted = this.sequenceStarted.bind(this);

        //this.setState(rows: _rows);
        this.state = {
            rowData: [],
            measuredData: [],
            loopNumData: [],
            numLoopsData: []
        }
    }

    componentDidMount() {
        //alert("arte componentDidMount");
         ws_register(this.id, this.sequenceLoaded, "InfoEvents.SEQUENCE_LOADED");
         ws_register(this.id, this.objectUpdate, "InfoEvents.OBJECT_UPDATE");

         // g2 note: apparently this event never fires, so this.sequenceStarted
         // gets called from componentDidUpdate() instead.
         ws_register(this.id, this.sequenceStarted, "InfoEvents.SEQUENCE_STARTED");
    }

    componentDidUpdate(prevProps) {
        //alert("arte componentDidUpdate");
        if (this.props.sequence.operations !== prevProps.sequence.operations) {
            this.sequenceLoaded();
        }
        if (Object.entries(this.props.sequence).length > 0 && this.table_drawn !== true) {
            this.sequenceLoaded();
        }
    }

    objectUpdate(props) {
        // This gets events from the value_to_ui() function.

        // alert("from objectUpdate");
        // let s = "source = " + props.source + ", target = " + props.target + ", opid = " + props.opid + ", valueType = " + props.valueType + ", value = " + props.value;
        // alert(s);

        try {
            if (props.target == "versionUpdate") {
                //alert("versionUpdate " + props.opid +  " " + props.value);
                return;
            } else if (props.target == "opUpdate") {
                let _measuredData = [];
                let _loopNumData = [];
                let _numLoopsData = [];
                let rd = this.state.rowData;
                for (var n = 0; n < rd.length; n++) {
                    _measuredData.push(this.state.measuredData[n]);
                    _loopNumData.push(this.state.loopNumData[n]);
                    _numLoopsData.push(this.state.numLoopsData[n]);

                    if (rd[n].operation == props.opid) {
                        //alert("found " + props.opid);

                        switch(props.valueType) {
                            case "measured":
                                //alert("updating " + props.valueType + " from " + rd[n].measured + " to " + props.value);
                                //rd[n].measured = props.value;
                                _measuredData.pop();
                                _measuredData.push(props.value);
                                break;
                            case "run":
                                //alert("Before updating run: _loopNumData.length = " + _loopNumData.length.toString()
                                //    + " - " + props.opid + " - " + props.value + " state " + _loopNumData[n].toString());
                                _loopNumData.pop();
                                //alert("_loopNumData.length = " + _loopNumData.length.toString());
                                _loopNumData.push(props.value);
                                //alert("After updating run: _loopNumData.length = " + _loopNumData.length.toString()
                                //    + " - " + props.opid + " - " + props.value + " state " + _loopNumData[n].toString());
                                break;
                            case "numLoops":
                                _numLoopsData.pop();
                                _numLoopsData.push(props.value);
                                break;
                            default:
                                alert("Unknown valueType: " + props.valueType);
                                break;
                        }
                    }
                }

                this.setState({measuredData: _measuredData});
                this.setState({loopNumData: _loopNumData});
                this.setState({numLoopsData: _numLoopsData});
            }
        }
        catch (e) {
            alert("objectUpdate exception: " + e.message);
        }
    }

    sequenceStarted() {
        //alert("sequenceStarted");

        this.setState({measuredData: []});
        this.setState({loopNumData: []});
        this.setState({numLoopsData: []});
    }

    sequenceLoaded(props) {
        //alert("sequenceLoaded");

    try {
        this.setState({rowData: []});

        //alert("measuredData.length = " + this.state.measuredData.length.toString());
        let addOtherData = (this.state.measuredData.length == 0);
        let _measuredData = [];
        let _loopNumData = [];
        let _numLoopsData = [];
        let _rowData = [];
        for (var i = 0; i < Object.entries(this.props.sequence).length; i++) {
            try {
                if (this.props.sequence.operations[i] !== undefined) {
                    let operationIsStarting = true;

                    const opid = this.props.sequence.operations[i].opid;
                    const exitcode = this.props.sequence.operations[i].exitcode;

                    var style = { backgroundColor: 'white', width: '60%'};
                    var result = "";
                    if (exitcode === 1) {
                        style = { backgroundColor: 'lightblue', width: '60%'};
                    } else if (exitcode === 100) {
                        style = { backgroundColor: 'lightgreen', width: '60%'};
                        result = "Pass";
                        operationIsStarting = false;
                    } else if ((exitcode === 130) || (exitcode === 140)) {
                        style = { backgroundColor: 'pink', width: '60%'};;
                        result = "Fail";
                        operationIsStarting = false;
                    }

                    if (addOtherData || operationIsStarting) {
                        //alert("adding other data");
                        _measuredData.push("");
                        _loopNumData.push("");
                        _numLoopsData.push("");
                        //alert("_measuredData.length = " + _measuredData.length.toString());
                    }
                    else {
                        _measuredData.push(this.state.measuredData[i]);
                        _loopNumData.push(this.state.loopNumData[i]);
                        _numLoopsData.push(this.state.numLoopsData[i]);
                    }

                    let rowDatum = {
                        style: style,
                        operation: opid,
                        measured: "",
                        run: "",
                        _of: "",
                        result: result
                    };
                    _rowData.push(rowDatum);
                }
            }
            catch (e) {
                console.error(e.message);
                _rows.push(<h2>{e.message}</h2>);
            }

         }

        this.setState({rowData: _rowData});

        if (addOtherData) {
            this.setState({measuredData: _measuredData});
            this.setState({loopNumData: _loopNumData});
            this.setState({numLoopsData: _numLoopsData});
            //alert("measuredData.length = " + this.state.measuredData.length.toString() + " after update");
        }

        this.table_drawn = true;
    }
    catch (e) {
        alert (e.message);
    }
    }

    render() {
        let _rows = [];
        //alert("this.state.rowData.length = " + this.state.rowData.length);
        for (var i = 0; i < this.state.rowData.length; i++) {
            try {
                const rd = this.state.rowData[i];
                const measured = this.state.measuredData[i];
                const loopNumData = this.state.loopNumData[i];
                const numLoopsData = this.state.numLoopsData[i];
                _rows.push (
                    <ArteResultsRow
                        style={rd.style}
                        operation={rd.operation}
                        measured={measured}
                        run={loopNumData}
                        _of={numLoopsData}
                        result={rd.result}
                    />
                );
            }
            catch (e) {
                console.error(e.message);
                _rows.push(<h2>{e.message}</h2>);
            }
        }

        return (
            <div>
                <table>
                    <thead>
                    <tr>
                        <th/>
                        <th>Measured</th>
                        <th>Run</th>
                        <th>of</th>
                        <th>Result</th>
                    </tr>
                    </thead>
                    <tbody>{_rows}</tbody>
                </table>
            </div>
        );
    }
}

class ArteResultsRow extends React.Component {
    render() {
        const style = this.props.style;
        const operation = this.props.operation;
        const measured = this.props.measured;
        const run = this.props.run;
        const _of = this.props._of;
        const result = this.props.result;

        return (
            <tr style={style}>
            <td align="left">{operation}</td>
            <td align="center">{measured}</td>
            <td align="center">{run}</td>
            <td align="center">{_of}</td>
            <td align="center">{result}</td>
            </tr>
        );
    }
}
