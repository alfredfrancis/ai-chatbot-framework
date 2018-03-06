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
                <div className="col-md-3">
                    <select className="form-control" id="paramEntityType" value={this.props.object.type ? this.props.object.type : null}
                        onChange={this.handleTypeValueChange.bind(this)}>
                        <option value="mobile">Mobile number</option>
                        <option value="email">Email</option>
                        <option value="free_text">Free Text</option>
                        <option value="number">Number</option>
                        <option value="list">List</option>
                    </select>
                </div>
                <div className="col-md-1">
                    <input className="form-control" onChange={this.handleRequiredChange.bind(this)} type="checkbox"
                           checked={this.props.object.required}/>
                </div>
                <div className="col-md-4">
                    <textarea className="form-control" onChange={this.handlePromptChange.bind(this)}
                              value={this.props.object.prompt}></textarea>
                </div>
                <div className="col-md-2">
                    <button className="btn btn-danger" onClick={this.handleParameterDelete.bind(this)}>Delete</button>
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

    handleTypeValueChange(event) {
        var items = this.props.object
        items["type"] = event.target.value
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
    handleParameterDelete(){
        this.props.onDeleteParam(this.props.indexId)
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
        var nextState = this.state
        if (!nextState[event.target.id].apiTrigger) {
            nextState["apiDetails"] = {
                "url": "",
                "requestType": "GET",
                "isJson": false,
                "jsonData": ""
            }
        }
        nextState[event.target.id] = event.target.checked
        this.setState(nextState)
    }

    handleApiValueChange(event) {
        var nextState = this.state.apiDetails
        nextState[event.target.id] = event.target.value
        this.setState({"apiDetails": nextState})
    }

    handleIsJsonChange(event) {
        var nextState = this.state.apiDetails
        nextState[event.target.id] = event.target.checked
        this.setState({"apiDetails": nextState})
    }

    handleJsonDataChange(event) {
        var nextState = this.state.apiDetails
        nextState[event.target.id] = event.target.value
        this.setState({"apiDetails": nextState})
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

    onDeleteParam(index){
        var nextState = this.state
        nextState.parameters.splice(index,1);
        this.setState(nextState)
    }
    handleParameterSave(){
        var newParam = {
            "name":document.getElementById("name").value,
            "type":document.getElementById("paramType").value,
            "required":document.getElementById("required").checked,
            "prompt":document.getElementById("prompt").value
        }

        var nextState = this.state
        nextState.parameters.push(newParam)
        this.setState(nextState)

        document.getElementById("name").value = "";
        document.getElementById("required").checked = false;
        document.getElementById("prompt").value ="";
    }
    onUpdate(index, data) {
        var nextState = this.state
        nextState.parameters[index] = data
        this.setState(nextState)
    }

    render() {
        var jsonEditor = {
            width: "100%",
            height: "200px",
            display: "None"
        }
        if (this.state.apiDetails && this.state.apiDetails.isJson) {
            jsonEditor.display = "inline-block";
        }
        return (
            <div>
                <div className="row">
                    <b>Story Name,</b><input className="form-control" id="storyName" type="text"
                                             value={ this.state.storyName}
                                             onChange={this.handleChange.bind(this)}/><br/>
                    <b>Intent Name,</b><input className="form-control" id="intentName" type="text"
                                              value={ this.state.intentName}
                                              onChange={this.handleChange.bind(this)}/><br/>
                </div>
                <div className="row"><h3>Parameters</h3></div>

                <div className="row">
                    <div className="col-md-2">
                        <h4>Name</h4>
                    </div>
                    <div className="col-md-3">
                        <h4>Type</h4>
                    </div>
                    <div className="col-md-1">
                        <h4>Required</h4>
                    </div>
                    <div className="col-md-4">
                        <h4>Prompt</h4>
                    </div>
                    <div className="col-md-2">
                    </div>
                </div>

                { this.state.parameters.map((object, index) => <Parameters indexId={index} object={object}
                                                                           onUpdate={this.onUpdate.bind(this)} onDeleteParam={this.onDeleteParam.bind(this)}/>) }
                <div className="row">
                <div className="col-md-2">
                    <input className="form-control" id="name" type="text"
                           />
                </div>
                <div className="col-md-3">
                    <select className="form-control" id="paramType">
                        <option value="mobile">Mobile number</option>
                        <option value="email">Email</option>
                        <option value="free_text" selected>Free Text</option>
                        <option value="number">Number</option>
                        <option value="list">List</option>
                    </select>
                </div>
                <div className="col-md-1">
                    <input className="form-control" id="required" type="checkbox"/>
                </div>
                <div className="col-md-4">
                    <textarea id="prompt" className="form-control"
                              ></textarea>
                </div>
                <div className="col-md-2">
                    <button className="btn btn-info" onClick={this.handleParameterSave.bind(this)}>Save</button>
                </div>
                <br/>
            </div>

                <br/>
                <div className="row">
                    <div className="col-md-1">
                        <div className="checkbox">
                            <label><input type="checkbox" id="apiTrigger"
                                          onChange={this.handleApiRequiredChange.bind(this)}
                                          checked={this.state.apiTrigger}/> API trigger </label>
                        </div>
                    </div>
                    <div className="col-md-1">
                        <div className="checkbox">
                            <label><input type="checkbox" id="isJson" onChange={this.handleIsJsonChange.bind(this)}
                                          checked={this.state.apiTrigger ? this.state.apiDetails.isJson : false}/>Json
                            </label>
                        </div>
                    </div>
                    <div className="col-md-8">
                        <input className="form-control" placeholder="API url" id="url" type="text"
                               value={this.state.apiTrigger ? this.state.apiDetails.url : ""}
                               disabled={!this.state.apiTrigger} onChange={this.handleApiValueChange.bind(this)}/>
                    </div>
                    <div className="col-md-2">
                        <select className="form-control" id="requestType"
                                value={this.state.apiTrigger ? this.state.apiDetails.requestType : "GET"}
                                disabled={!this.state.apiTrigger} onChange={this.handleApiValueChange.bind(this)}>
                            <option value="GET">GET</option>
                            <option value="POST">POST</option>
                            <option value="PUT">PUT</option>
                            <option value="DELETE">DELETE</option>
                        </select>
                    </div>
                </div>
                <br/>
                <div class="span4" id="jsoneditor">
                    <textarea id="jsonData" onChange={this.handleJsonDataChange.bind(this)}
                              value={ this.state.apiTrigger && this.state.apiDetails.isJson ? this.state.apiDetails.jsonData : ""}
                              style={jsonEditor}>{}</textarea>
                </div>
                <hr/>
                <b>Speech Response,</b><textarea onChange={this.handleChange.bind(this)}
                                                 value={ this.state.speechResponse}
                                                 className="form-control" id="speechResponse"> </textarea><br/>
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