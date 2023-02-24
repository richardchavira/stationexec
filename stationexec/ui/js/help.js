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
        )
    }
}
