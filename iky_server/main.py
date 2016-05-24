from iky_server import app
from flask import Flask, render_template, request,jsonify
import os
import json 
from mongo import _retrieve
#from bson.objectid import ObjectId
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
	_id=request.args.get("story_id");
	print(_id)
	query= { "story_id":_id}
	test_set= json.loads(_retrieve("labled_queries",query))
	return render_template('train.html',story_id =_id,test_sets = test_set ) 


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    #db_session.rollback()
    return "internal server error - iky"

@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"