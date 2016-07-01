import os

from flask import request

from ikyCore.models import User,Story
from ikyCore.intentClassifier import IntentClassifier
from ikyWebServer import app

# DB stuff
from bson.objectid import ObjectId
from ikyWareHouse.mongo import _insert, _retrieve, _delete,_update

# Iky's tools
import buildResponse

@app.route('/_insert_tagged', methods=['POST'])
def _insert_tagged():

    data = {
        "item": request.form['labeled_info'],
        "user_id": "1",
        "story_id": request.form['story_id']
    }
    return _insert("labled_queries", data)


@app.route('/createStory', methods=['POST'])
def createStory():
    story = Story()
    story.user = User.objects(email="iky@pealdatadirect.com")[0]
    story.storyName = request.form['storyName']
    story.actionName = request.form['actionName']
    story.actionType = request.form['actionType']
    story.labels = request.form['labels'].split(",")
    try:
        story.save()
    except Exception as e:
        return {"error": e}
    return buildResponse.sentOk()

@app.route('/saveEditStory', methods=['POST'])
def saveEditStory():
    story = Story.objects.get(id=ObjectId(request.form['_id']))
    data = {
        "labels": request.form['labels'].split(","),
        "actionType": request.form['actionType'],
        "actionName": request.form['actionName'],
        "storyName": request.form['storyName'],
    }
    story.update(**data)
    return buildResponse.sentOk()


@app.route('/getStories', methods=['POST'])
def getStories():
    stories = Story.objects(user=User.objects(email="iky@pealdatadirect.com")[0])
    print (stories.to_json())
    return buildResponse.sentJson(stories.to_json())


@app.route('/deleteStory', methods=['POST'])
def delete_story():
    Story.objects.get(id=ObjectId(request.form['storyId'])).delete()
    IntentClassifier().train()
    try:
        os.remove("models/%s.model" % request.form['storyId'])
    except OSError:
        pass
        return buildResponse.sentOk()


@app.route('/deleteLabeledSentences', methods=['POST'])
def delete_sent():
    story=Story.objects.get(id=ObjectId(request.form['storyId']))
    labeledSentence=story.labeledSentences.update_one( pull__id=ObjectId(request.form['sentenceId']) )
    labeledSentence.delete()
    return buildResponse.sentOk()


@app.route("/saveToRepo", methods=['POST'])
def saveToRepo():

    data = {
        "story_id": request.form['story_id'],
        "raw_data": request.form['raw_data']
    }

    print(data)
    return _insert("repo", data)
