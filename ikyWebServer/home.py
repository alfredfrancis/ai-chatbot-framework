from bson.objectid import ObjectId
from flask import render_template, request

from ikyWebServer import app

from ikyCore.models import Story,Logs

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

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/editStory', methods=['GET'])
def editStory():
    _id = request.args.get("storyId")
    story = Story.objects.get(id=ObjectId(_id))
    return render_template('editStory.html', storyId=_id, storyDetails=story.to_mongo().to_dict())


# Training UI
@app.route('/train', methods=['GET'])
def train():
    _id = request.args.get("storyId")
    story = Story.objects.get(id=ObjectId(_id))
    labeledSentences = story.labeledSentences
    return render_template('train.html', storyId=_id, labeledSentences=labeledSentences, story=story.to_mongo().to_dict())

@app.route('/logs', methods=['GET'])
def logs():
    logs = Logs.objects
    return render_template('predictionLogs.html', logs=logs.to_mongo().to_dict())


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    return "internal server error - iky"


@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"
