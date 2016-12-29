from bson.objectid import ObjectId
from flask import render_template, request

from webServer import app

from core.models import Story

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
    return render_template('editStory.html',
                           storyId=_id,
                           )


# Training UI
@app.route('/train', methods=['GET'])
def train():
    _id = request.args.get("storyId")
    story = Story.objects.get(id=ObjectId(_id))
    labeledSentences = story.labeledSentences
    return render_template('train.html',
                           storyId=_id,
                           labeledSentences=labeledSentences,
                           story=story.to_mongo().to_dict(),
                           parameters=[parameter.name for parameter in story.parameters]
                           )

# log management Page
@app.route('/logs', methods=['GET'])
def logs():
    return "".join(open("log.json").readlines())


# Error handlers.
@app.errorhandler(500)
def internal_error(error):
    return "internal server error - iky"


@app.errorhandler(404)
def not_found_error(error):
    return "not found - iky"
