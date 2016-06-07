from iky_server import app
from flask import Flask, render_template, request,jsonify
import os
import json 
from mongo import _retrieve
from bson.objectid import ObjectId
import ast
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
	query= { "story_id":_id}
	test_set= ast.literal_eval(_retrieve("labled_queries",query))

	query= { "_id":ObjectId(_id)}
	story_detail = json.loads(_retrieve("stories",query))
	return render_template('train.html',story_id =_id,test_sets = test_set,story_details=story_detail ) 


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    return "internal server error - iky"

@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"