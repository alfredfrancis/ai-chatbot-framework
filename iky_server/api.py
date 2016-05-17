from iky_server import app
from flask import Flask, render_template, request

from functions import *

from ner import predict

# Request Handler
@app.route('/req', methods=['POST'])
def req():
	user_say = request.form['user_say']
	return predict(user_say)
	

