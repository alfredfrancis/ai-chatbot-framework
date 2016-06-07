from iky_server import app
import os

from flask import request, jsonify, Response

# DB stuff
import json
from bson.objectid import ObjectId
from mongo import _get_tagged,_insert,_retrieve,_delete

# Iky's tools
from intent_classifier import Intent_classifier

@app.route('/create_story', methods=['POST'])
def create_story():
    data={
    "user_id" : request.form['user_id'],
    "labels": request.form['labels'].split(","),
    "action_type":request.form['action_type'],
    "action":request.form['action_name'],
    "story_name" : request.form['story_name'],
    }
    return _insert("stories",data)

@app.route('/get_stories', methods=['POST'])
def get_stories():
    query= { "user_id":"1"}
    return _retrieve("stories",query)

@app.route('/delete_story', methods=['POST'])
def delete_story():
    query= { "_id":ObjectId(request.form['story_id'])}
    _delete("stories",query);

    query= { "story_id":request.form['story_id']}
    _delete("labled_queries",query);

    Intent_classifier().context_train()

    try:
        os.remove("models/%s.model"%request.form['story_id'])
    except OSError:
        pass
    return "1"

@app.route('/delete_sent', methods=['POST'])
def delete_sent():
    query= { "_id":ObjectId(request.form['sent_id'])}
    _delete("labled_queries",query);
    return "1"