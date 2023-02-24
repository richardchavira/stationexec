class OperationLogPopup extends React.Component {

    renderMessageLine = (message) => {
        let style = {color: 'white', 'font-weight': 'normal', margin: '0'};
        if (message.event === EVENTS.ALERT) {
            style.color = 'red'
        }
        if (message.source === 'sequencer') {
            style.margin = '10 0 10 0';
        }
        return <p style={style}>{message.message}</p>
    }
    render() {
        return (
            <ModalPopup>
                <div className="operation-popup">
                    <div className="message-view-control" style={{width: "100%", "margin-top": "2%" }}>
                        {this.props.messages.map(this.renderMessageLine)}
                    </div>
                    <button onClick={this.props.close} className='se-button' style={{'margin-top': '5px'}}>Close</button>
                </div>
            </ModalPopup>
        )
    }
}