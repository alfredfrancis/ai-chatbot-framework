from bson.objectid import ObjectId
from flask import render_template, request

from ikyWareHouse.mongo import _retrieve
from ikyWebServer import app


# Index
@app.route('/')
def home():
    return render_template('index.html')


# Create Stories
@app.route('/stories')
def stories():
    return render_template('stories.html')

# Create Stories
@app.route('/repo')
def repo():
    return render_template('repo.html')


@app.route('/editStory', methods=['GET'])
def editStory():
    _id = request.args.get("story_id")
    query = {"_id": ObjectId(_id)}
    story_detail = _retrieve("stories", query)
    return render_template('editStory.html', story_id=_id, story_details=story_detail)


# Training UI
@app.route('/train', methods=['GET'])
def train():
    _id = request.args.get("story_id")
    query = {"story_id": _id}
    test_set = _retrieve("labled_queries", query)

    query = {"_id": ObjectId(_id)}
    story_detail = _retrieve("stories", query)
    return render_template('train.html', story_id=_id, test_sets=test_set, story_details=story_detail)

@app.route('/logs', methods=['GET'])
def logs():
    query = {}
    logs = _retrieve("logs", query)
    return render_template('predictionLogs.html', logs=logs)


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    return "internal server error - iky"


@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"
