from iky_server import app
from flask import Flask, render_template, request

from functions import *

from ner import predict

# Request Handler
@app.route('/req', methods=['POST'])
def req():
	user_say = request.form['user_say']
	return predict(user_say)

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
@app.route('/mm',methods=['POST'])
def mm():
	return 1