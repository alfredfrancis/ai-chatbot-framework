
from iky_server import app
from flask import Flask, render_template, request
import os


# Index
@app.route('/')
def home():
    return render_template('index.html')

# Request Handler
@app.route('/req', methods=['GET', 'POST'])
def req():
    botsay = request.form['user_say']
    return botsay

# Resource Handlers.
@app.route('/<path:resource>')
def serveStaticResource(resource):
    return send_from_directory('static/', resource)    

# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    #db_session.rollback()
    return "internal server error - iky"

@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"