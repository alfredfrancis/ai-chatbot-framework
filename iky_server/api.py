from iky_server import app
from flask import Flask,jsonify,render_template, request

from predict import predict

# Request Handler
@app.route('/req', methods=['POST','GET'])
def req():
    if request.method == 'POST':
        user_say = request.form['user_say']
    else:
        user_say = request.args.get('user_say')
    #return jsonify(result=predict(user_say))
    return predict(user_say)


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