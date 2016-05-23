from iky_server import app
from flask import Flask, render_template, request
import os


# Index
@app.route('/')
def home():
    return render_template('index.html')

# Create Stories
@app.route('/stories')
def stories():
    return render_template('stories.html')   

# Training UI
@app.route('/train', methods=['GET'])
def train():
	return render_template('train.html',story_id =request.args.get("story_id") ) 


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    #db_session.rollback()
    return "internal server error - iky"

@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"