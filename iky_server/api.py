from iky_server import app
from flask import Flask, render_template, request

from functions import re_check
from functions import context_check


# Request Handler
@app.route('/req', methods=['POST'])
def req():
	user_say = request.form['user_say']
	bot_say = re_check(user_say)
	if not bot_say:
		bot_say = context_check(user_say)
	if bot_say:
		return "%s"%bot_say
	else:
		return "Sorry, I'm just learning things."

