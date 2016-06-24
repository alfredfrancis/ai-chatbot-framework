from iky_server import app
from flask import Flask, jsonify, render_template, request, Response
import json
from predict import predict
from interface import execute_action

@app.route('/ikyParseAndExecute',methods=['POST','GET'])
def ikyParseAndExecute():
    if request.method == 'POST':
        user_say = request.form['user_say']
    else:
        user_say = request.args.get('user_say')

    predicted = predict(user_say)
    if "error_code" not in predicted:
        result = execute_action(predicted['action_type'], predicted['intent'], predicted["labels"])
    else:
        result = "Sorry im not trained to handle this."
    return result

# Request Handler
@app.route('/iky_parse', methods=['POST', 'GET'])
def iky_parse(user_say=None):
    if request.method == 'POST':
        user_say = request.form['user_say']
    else:
        user_say = request.args.get('user_say')

    if user_say == None or user_say == "":
        result = json.dumps({"error_code": "2", "error_msg": "empty string"})
    else:
        result = json.dumps(predict(user_say))

    return Response(response=result, status=200, mimetype="application/json")


# mattermost integration
@app.route('/mm', methods=['POST'])
def mm():
    """
    channel_id=hawos4dqtby53pd64o4a4cmeoo&
    channel_name=town-square&
    team_domain=someteam&
    team_id=kwoknj9nwpypzgzy78wkw516qe&
    text=some+text+here&
    timestamp=1445532266&
    token=zmigewsanbbsdf59xnmduzypjc&
    trigger_word=some&
    user_id=rnina9994bde8mua79zqcg5hmo&
    user_name=somename
    """
    return flask.jsonify(**request.form['text'])
