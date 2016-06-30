import os

from flask import request

from ikyWebServer import app
# DB stuff
from bson.objectid import ObjectId
from bson.json_util import dumps
from ikyWareHouse.mongo import _insert, _retrieve, _delete,_update

# Iky's tools
from ikyCore.intentClassifier import Intent_classifier


@app.route('/_insert_tagged', methods=['POST'])
def _insert_tagged():
    data = {
        "item": request.form['labeled_info'],
        "user_id": "1",
        "story_id": request.form['story_id']
    }
    return _insert("labled_queries", data)


@app.route('/create_story', methods=['POST'])
def create_story():
    data = {
        "user_id": request.form['user_id'],
        "labels": request.form['labels'].split(","),
        "action_type": request.form['action_type'],
        "action": request.form['action_name'],
        "story_name": request.form['story_name'],
    }
    return _insert("stories", data)

@app.route('/saveEditStory', methods=['POST'])
def saveEditStory():
    condition = {
        "_id":ObjectId(request.form['_id'])
    }
    data = {
        "user_id": request.form['user_id'],
        "labels": request.form['labels'].split(","),
        "action_type": request.form['action_type'],
        "action": request.form['action_name'],
        "story_name": request.form['story_name'],
    }
    return _update("stories",condition, data)


@app.route('/get_stories', methods=['POST'])
def get_stories():
    query = {"user_id": "1"}
    return dumps(_retrieve("stories", query))


@app.route('/delete_story', methods=['POST'])
def delete_story():
    query = {"_id": ObjectId(request.form['story_id'])}
    _delete("stories", query);

    query = {"story_id": request.form['story_id']}
    _delete("labled_queries", query);

    Intent_classifier().train()

    try:
        os.remove("models/%s.model" % request.form['story_id'])
    except OSError:
        pass
    return "1"


@app.route('/delete_sent', methods=['POST'])
def delete_sent():
    query = {"_id": ObjectId(request.form['sent_id'])}
    _delete("labled_queries", query)
    return "1"


@app.route("/saveToRepo", methods=['POST'])
def saveToRepo():

    data = {
        "story_id": request.form['story_id'],
        "raw_data": request.form['raw_data']
    }

    print(data)
    return _insert("repo", data)
