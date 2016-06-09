from iky_server import app
from flask import Flask,jsonify,render_template, request,Response
import json
from predict import predict

# Request Handler
@app.route('/iky_parse', methods=['POST','GET'])
def iky_parse(user_say=None):
    if request.method == 'POST':
        user_say = request.form['user_say']
    else:
        user_say = request.args.get('user_say')
    #return jsonify(**predict(user_say))
    return Response(response=json.dumps(predict(user_say)),status=200,mimetype="application/json")


#mattermost integration
@app.route('/mm',methods=['POST'])
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