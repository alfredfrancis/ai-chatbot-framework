import os
import ast
from bson.objectid import ObjectId

from flask import request
from ikyWebServer import app

from ikyCore.models import User,Story,LabeledSentences
from ikyCore.intentClassifier import IntentClassifier

import buildResponse

@app.route('/insertLabeledSentence', methods=['POST'])
def insertLabeledSentence():
    story = Story.objects.get(id=ObjectId(request.form['storyId']))
    labeledSentence = LabeledSentences()
    print(ast.literal_eval(request.form['labeledSentence']))
    labeledSentence.data = ast.literal_eval(request.form['labeledSentence'])
    story.labeledSentences.append(labeledSentence)
    try:
        story.save()
    except Exception as e:
        return {"error": e}
    return buildResponse.sentOk()


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
    try:
        story.update(**data)
    except Exception as e:
        return {"error": e}
    return buildResponse.sentOk()


@app.route('/getStories', methods=['POST'])
def getStories():
    stories = Story.objects(user=User.objects(email="iky@pealdatadirect.com")[0])
    return buildResponse.sentJson(stories.to_json())


@app.route('/deleteStory', methods=['POST'])
def deleteStory():
    Story.objects.get(id=ObjectId(request.form['storyId'])).delete()

    try:
        intentClassifier = IntentClassifier()
        intentClassifier.train()
    except:
        pass

    try:
        os.remove("models/%s.model" % request.form['storyId'])
    except OSError:
        pass
    return buildResponse.sentOk()


@app.route('/deleteLabeledSentences', methods=['POST'])
def deleteLabeledSentences():
    story = Story.objects.get(id=ObjectId(request.form['storyId']))
    story.labeledSentences.filter(id=ObjectId(request.form['sentenceId'])).delete()
    story.save()
    return buildResponse.sentOk()

"""
@app.route("/saveToRepo", methods=['POST'])
def saveToRepo():

    data = {
        "story_id": request.form['story_id'],
        "raw_data": request.form['raw_data']
    }

    print(data)
    return _insert("repo", data)
"""