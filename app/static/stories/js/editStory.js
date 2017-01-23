/**
 * Created by alfred on 26/12/16.
 */

class Parameters extends React.Component {
    render() {
        return (
            <div className="row">
                <div className="col-md-2">
                    <input className="form-control" onChange={this.handleNameChange.bind(this)} type="text"
                           value={this.props.object.name}/>
                </div>
                <div className="col-md-2">
                    <input className="form-control" onChange={this.handleRequiredChange.bind(this)} type="checkbox"
                           checked={this.props.object.required}/>
                </div>
                <div className="col-md-8">
                    <textarea className="form-control" onChange={this.handlePromptChange.bind(this)}
                              value={this.props.object.prompt}></textarea>
                </div>
                <br/>
            </div>
        )
    }

    handleNameChange(event) {
        var items = this.props.object
        items["name"] = event.target.value
        this.props.onUpdate(this.props.indexId, items)
    }

    handleRequiredChange(event) {
        var items = this.props.object
        items["required"] = event.target.checked
        this.props.onUpdate(this.props.indexId, items)
    }

    handlePromptChange(event) {
        var items = this.props.object
        items["prompt"] = event.target.value
        this.props.onUpdate(this.props.indexId, items)
    }
}

class Main extends React.Component {
    constructor() {
        super();
        this.state = {parameters: []}
        this.handleSubmit = this.handleSubmit.bind(this);
    }

    loadDataFromServer() {
        $.ajax({
            url: '/stories/' + this.props.storyId,
            dataType: 'json',
            success: (data) => {
                this.setState(data);
            }
        });
    }

    componentWillMount() {
        this.loadDataFromServer();
    }

    handleChange(event) {
        var nextState = {}
        console.log(event.target.value)
        nextState[event.target.id] = event.target.value
        this.setState(nextState)
    }

    handleApiRequiredChange(event) {
        var nextState = {}
        nextState[event.target.id] = event.target.checked
        this.setState(nextState)
    }

    handleApiValueChange(event) {
        var nextState = this.state.apiDetails
        nextState[event.target.id] = event.target.value
        this.setState({"apiDetails":nextState})
    }

    handleSubmit(event) {
        event.preventDefault();
        $.ajax({
            url: '/stories/' + this.props.storyId,
            type: 'PUT',
            data: JSON.stringify(this.state),
            contentType: 'application/json; charset=utf-8',
            success: function () {
                alert("Story updated sucessfully")
            }
        });
    }

    onUpdate(index, data) {
        var nextState = this.state
        nextState.parameters[index] = data
        this.setState(nextState)
    }

    render() {
        return (
            <div>
                <div className="row">
                    <b>Story Name,</b><input className="form-control" id="storyName" type="text"
                                             value={ this.state.storyName} onChange={this.handleChange.bind(this)}/><br/>
                    <b>Intent Name,</b><input className="form-control" id="intentName" type="text"
                                              value={ this.state.intentName} onChange={this.handleChange.bind(this)}/><br/>
                </div>

                <div className="row">
                    <div className="col-md-2">
                        <div className="checkbox">
                            <label><input type="checkbox" id="apiTrigger" onChange={this.handleApiRequiredChange.bind(this)} checked={this.state.apiTrigger}/> API trigger </label>
                        </div>
                    </div>
                    <div className="col-md-8">
                        <input className="form-control" placeholder="API url" id="url" type="text" value={this.state.apiTrigger ? this.state.apiDetails.url : ""} disabled={!this.state.apiTrigger} onChange={this.handleApiValueChange.bind(this)}/>
                    </div>
                    <div className="col-md-2">
                        <select className="form-control" id="requestType" value={this.state.apiTrigger ? this.state.apiDetails.requestType : "GET"}  disabled={!this.state.apiTrigger} onChange={this.handleApiValueChange.bind(this)}>
                            <option value="GET" >GET</option>
                            <option value="POST">POST</option>
                            <option value="POST">PUT</option>
                            <option value="POST">DELETE</option>
                        </select>
                    </div>
                </div>
                <br/>
                <div className="row"><h3>Parameters</h3></div>

                <div className="row">
                    <div className="col-md-2">
                        <h4>Name</h4>
                    </div>
                    <div className="col-md-2">
                        <h4>Required</h4>
                    </div>
                    <div className="col-md-2">
                        <h4>Prompt</h4>
                    </div>
                </div>
                { this.state.parameters.map((object, index) => <Parameters indexId={index} object={object}
                                                                           onUpdate={this.onUpdate.bind(this)}/>) }
                <br/>
                <b>Speech Response,</b><textarea onChange={this.handleChange.bind(this)} value={ this.state.speechResponse}
                                                 className="form-control" id="speechResponse"></textarea><br/>
                <button onClick={this.handleSubmit} className="btn btn-success pull-right" type="submit">Save</button>
            </div>
        );
    }
}
;

ReactDOM.render(
    <Main storyId={document.getElementById('storyId').value}/>,
    document.getElementById('app')
);