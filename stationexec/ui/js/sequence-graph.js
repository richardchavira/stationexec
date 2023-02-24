class ProgressCircle extends React.Component{
    constructor(props) {
        super(props);
        this.id = random_id(this.constructor.name);
        this.state = {
            mouse: false,
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
            <g
                id={this.props.id}
                className="graphProgressNode"
                transform={transform}
                onMouseEnter={this.mouseOver}
                onMouseLeave={this.mouseOut}
                onClick={this.props.onClick} >
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
        )
    }
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
                <ProgressCircle
                    radius={this.props.radius}
                    zoom={this.props.zoom}
                    x={this.props.x}
                    y={this.props.y}
                    complete={complete}
                    icon={icon}
                    hover={this.props.hover}
                    duration_ms={this.props.duration_ms}
                    avgduration={this.props.avgduration}
                    label={this.props.id}
                    status={statusCode}
                    onClick={() => this.props.openOperationPopup(this.props.id)}/>
            </g>
        )
    }
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
        )
    }
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
        //alert("componentDidMount");
        if (Object.entries(this.props.sequence).length > 0 && this.graph_drawn !== true) {
            this.drawGraph();
        }
        window.addEventListener("resize", this.resizeHelper);
    }

    componentDidUpdate(prevProps) {
        //alert("componentDidUpdate");
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
        //alert("drawGraph");

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
                <GraphNode
                    openOperationPopup={this.props.openOperationPopup}
                    messageData={this.props.messageData}
                    id={v.label}
                    key={v.id}
                    x={v.x} y={v.y}
                    avgduration={v.avgduration}
                    duration_ms={v.duration_ms}
                    radius={this.state.nodeRadius}
                    zoom={this.state.zoom}
                    code={v.code}
                    hover={this.mouseHovering}
                    passing={v.passing}
                    op_name={v.label}/>
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
        }
    }
}
