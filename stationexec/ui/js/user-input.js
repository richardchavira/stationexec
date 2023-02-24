class UserInputModal extends React.Component {
    constructor(props) {
      super(props);
      this.state = { }
    }
  
    componentDidMount() {
      for (const [input, info] of Object.entries(this.props.inputData)) {
        if (!['message', 'uuid'].includes(input)) {
          if (info.type === 'checkbox') {
            const defaultValue = info.default ? info.default : false
            this.setState({ [input]: defaultValue })
          }
          else if (info.type === 'dropdown') {
            this.setState({ [input]: info.choices[0] })
          }
          else this.setState({ [input]: null })
        }
      }
    }
  
    renderUserInputs = () => {
      let inputs = []
      
      for (const [inputName, inputInfo] of Object.entries(this.props.inputData)) {
        switch(inputInfo.type) {
          case 'radio':
            inputs.push(this.renderRadioButtons(inputName, inputInfo))
            break;
          case 'text':
            inputs.push(this.renderTextInput(inputName, inputInfo.label))
            break;
          case 'checkbox':
            inputs.push(this.renderCheckbox(inputName, inputInfo))
            break;
          case 'dropdown':
            inputs.push(this.renderDropdown(inputName, inputInfo))
            break;
          }
      }
      
      return inputs
    }
  
    handleInputChange = (inputName, event) => {
      this.setState({ [inputName]: event.target.value })
    }
  
    renderRadioButtons = (inputName, data) => {
      const radioButtons = data.choices.map((choice) => {
        return (
          <div>
            <label>
              <input
                type="radio"
                value={choice}
                key={choice}
                checked={this.state[inputName] === choice}
                onChange={(event) => this.handleInputChange(inputName, event)} />
            {choice}
          </label>
          </div>
        )
      })
  
      return (
        <div className='modal-input'>
          <label>{data.label}</label>
          {radioButtons}
        </div>
      )
    }
  
    renderTextInput = (inputName, label) => {
      return (
        <div className='modal-input'>
          <label>
            {label}
            <input
              type="text"
              value={this.state[inputName]}
              onChange={(event) => this.handleInputChange(inputName, event)} />
          </label>
        </div>
      )
    }
  
    renderCheckbox = (inputName, data) => {
      const handleCheck = () => {
        this.setState({ [inputName]: !this.state[inputName] })
      }
  
      return (
        <div className='modal-input'>
          <label>
            <input
              type="checkbox"
              checked={this.state[inputName]}
              onChange={handleCheck} />
          {data.label}
        </label>
        </div>
      )
    }

    renderDropdown = (inputName, info) => {
      const choices = info.choices.map((choice) => <option value={choice}>{choice}</option>)
      return (
        <div className='modal-input'>
          <label>
          {info.label}
            <select
              name={inputName}
              onChange={(event) => this.handleInputChange(inputName, event)}>
              {choices}
            </select>
          </label>
        </div>
      )
    }
  
    handleSubmit = () => {
      const options = {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(this.state)
      }
  
      fetch('/tool/user_input/input-data', options)
        .then((res) => {
          if (res.ok) {
            this.props.clearInput(this.props.inputData.uuid)
          } 
        })
        .catch(err => console.log(err));
    }

    disableSubmit = () => {
      const inputValues = Object.values(this.state);
      if (inputValues.includes(null) || inputValues.includes("")) {
        return true
      } 
      return false
    }
    
    render () { 
      return(
        <ModalPopup>
          <div dangerouslySetInnerHTML={{__html: this.props.inputData.message}} />
          {this.renderUserInputs()}
          <ActionButton
            label='Submit'
            className='modal-input'
            disabled={this.disableSubmit()}
            buttonClick={this.handleSubmit} />
        </ModalPopup>
      )
    }
  
  }
  