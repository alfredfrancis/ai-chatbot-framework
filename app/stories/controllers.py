import os
from bson.json_util import dumps,loads
from bson.objectid import ObjectId

from flask import Blueprint, request, render_template,Response

import app.commons.buildResponse as buildResponse
from app.stories.models import Story,Parameter,update_document
from app.core.intentClassifier import IntentClassifier

stories = Blueprint('auth', __name__, url_prefix='/stories')

# Create Stories
@stories.route('/manage')
def stories():
    return render_template('story/manage_stories.html')

@stories.route('/createStory', methods=['POST'])
def createStory():
    content = request.get_json(silent=True)

    story = Story()
    story.storyName = content.get("storyName")
    story.intentName = content.get("intentName")
    story.speechResponse = content.get("speechResponse")

    if content.get("parameters"):
        for param in content.get("parameters"):
            parameter = Parameter()
            update_document(parameter,param)
            story.parameters.append(parameter)
    try:
        story.save()
    except Exception as e:
        return {"error": e}
    return buildResponse.sentOk()

@stories.route('/edit', methods=['GET'])
def editStory():
    _id = request.args.get("storyId")
    return render_template('story/edit_story.html',
                           storyId=_id,
                           )

@stories.route('/stories/<storyId>')
def getStory(storyId):
    return Response(response=dumps(
        Story.objects.get(
            id=ObjectId(
                storyId)).to_mongo().to_dict()),
    status=200,
    mimetype="application/json")

@stories.route('/stories/<storyId>',methods=['PUT'])
def updateStory(storyId):
    jsondata = loads(request.get_data())
    print(jsondata)
    story = Story.objects.get(id=ObjectId(storyId))
    story = update_document(story,jsondata)
    story.save()
    return 'success', 200

@stories.route('/getStories', methods=['POST'])
def getStories():
    stories = Story.objects
    return buildResponse.sentJson(stories.to_json())


@stories.route('/deleteStory', methods=['POST'])
def deleteStory():
    Story.objects.get(id=ObjectId(request.form['storyId'])).delete()
    try:
        intentClassifier = IntentClassifier()
        intentClassifier.train()
    except:
        pass

    try:
        os.remove("model_files/%s.model" % request.form['storyId'])
    except OSError:
        pass
    return buildResponse.sentOk()