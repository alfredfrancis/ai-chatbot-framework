import os
from bson.json_util import dumps, loads
from bson.objectid import ObjectId
from flask import Blueprint, request, render_template, Response
from flask import current_app as app
import app.commons.buildResponse as buildResponse
from app.stories.models import Story, Parameter, ApiDetails, update_document, Bot
from app.core.intentClassifier import IntentClassifier


stories = Blueprint('stories_blueprint', __name__,
                    url_prefix='/stories',
                    template_folder='templates')

# Create Stories


@stories.route('/home')
def home():
    return render_template('home.html')


@stories.route('/edit/<storyId>', methods=['GET'])
def edit(storyId):
    return render_template('edit.html',
                           storyId=storyId,
                           )


@stories.route('/', methods=['POST'])
def createStory():
    content = request.get_json(silent=True)

    story = Story()
    story.storyName = content.get("storyName")
    story.intentName = content.get("intentName")
    story.speechResponse = content.get("speechResponse")

    if content.get("apiTrigger") is True:
        story.apiTrigger = True
        apiDetails = ApiDetails()
        isJson = content.get("apiDetails").get("isJson")
        apiDetails.isJson = isJson
        if isJson:
            apiDetails.jsonData = content.get("apiDetails").get("jsonData")

        apiDetails.url = content.get("apiDetails").get("url")
        apiDetails.requestType = content.get("apiDetails").get("requestType")
        story.apiDetails = apiDetails
    else:
        story.apiTrigger = False

    if content.get("parameters"):
        for param in content.get("parameters"):
            parameter = Parameter()
            update_document(parameter, param)
            story.parameters.append(parameter)
    try:
        story.save()
    except Exception as e:
        return buildResponse.buildJson({"error": str(e)})
    return buildResponse.sentOk()

import json
@stories.route('/')
def readStories():
    botId=request.args.get('botId')
    if botId:
        stories = Story.objects(bot= botId)
        
    else:
        stories = Story.objects
        #stories = [a.to_json() for a in stories if not a.bot]
    return buildResponse.sentJson(stories.to_json())


@stories.route('/<storyId>')
def readStory(storyId):
    return Response(response=dumps(
        Story.objects.get(
            id=ObjectId(
                storyId)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@stories.route('/<storyId>', methods=['PUT'])
def updateStory(storyId):
    jsondata = loads(request.get_data())
    story = Story.objects.get(id=ObjectId(storyId))
    story = update_document(story, jsondata)
    story.save()
    return 'success', 200


@stories.route('/<storyId>', methods=['DELETE'])
def deleteStory(storyId):
    Story.objects.get(id=ObjectId(storyId)).delete()
    try:
        intentClassifier = IntentClassifier()
        botId='default'
        if request.args.get('botId'):
            botId=request.args.get('botId')
        intentClassifier.setBotId(botId)
        intentClassifier.train()
    except BaseException:
        pass

    try:
        botId='default'
        if request.args.get('botId'):
            botId=request.args.get('botId')
        os.remove("{}/{},{}.model".format(app.config["MODELS_DIR"],botId, storyId))
    except OSError:
        pass
    return buildResponse.sentOk()


@stories.route('/bot')
def readBots():
    bots = Bot.objects
    return buildResponse.sentJson(bots.to_json())

@stories.route('/bot', methods=['POST'])
def createBot():
    content = request.get_json(silent=True)

    bot = Bot()
    bot.botName = content.get("botName")

    try:
        bot.save()
    except Exception as e:
        return buildResponse.buildJson({"error": str(e)})
    return buildResponse.sentOk()

@stories.route('/bot/<botId>', methods=['PUT'])
def updateBot(botId):
    jsondata = loads(request.get_data())
    bot = Bot.objects.get(id=ObjectId(botId))
    bot = update_document(bot, jsondata)
    bot.save()
    return 'success', 200
