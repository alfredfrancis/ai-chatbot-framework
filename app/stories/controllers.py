import os
from bson.json_util import dumps, loads
from bson.objectid import ObjectId
from flask import Blueprint, request, render_template, Response, g
from flask import current_app as app
import app.commons.buildResponse as buildResponse
from app.stories.models import Story, Parameter, ApiDetails, update_document, Bot
from app.core.intentClassifier import IntentClassifier
from app.core.controllers import requires_auth

stories = Blueprint('stories_blueprint', __name__,
                    url_prefix='/stories',
                    template_folder='templates')

# Create Stories


@stories.route('/home')
@requires_auth
def home():
    return render_template('home.html')


@stories.route('/edit/<storyId>', methods=['GET'])
@requires_auth
def edit(storyId):
    return render_template('edit.html',
                           storyId=storyId,
                           )


@stories.route('/', methods=['POST'])
@requires_auth
def createStory():
    content = request.get_json(silent=True)

    story = Story()
    story.storyName = content.get("storyName")
    story.intentName = content.get("intentName")
    story.speechResponse = content.get("speechResponse")

    if g.botId:
      story.bot = g.botId
    elif content.get("bot"):
      story.bot = content.get("bot")

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
@requires_auth
def readStories():
  botId=None
  if g.botId:
    botId=g.botId
  elif request.args.get('botId'):
    botId=request.args.get('botId')
  
  if botId:
      stories = Story.objects(bot = botId)
  else:
      stories = Story.objects
      #stories = [a.to_json() for a in stories if not a.bot]
  return buildResponse.sentJson(stories.to_json())


@stories.route('/<storyId>')
@requires_auth
def readStory(storyId):
    return Response(response=dumps(
        Story.objects.get(
            id=ObjectId(
                storyId)).to_mongo().to_dict()),
        status=200,
        mimetype="application/json")


@stories.route('/<storyId>', methods=['PUT'])
@requires_auth
def updateStory(storyId):
    jsondata = loads(request.get_data())
    story = Story.objects.filter(id=ObjectId(storyId))
    if g.botId:
      story=story.filter(bot=g.botId)
    story = update_document(story.get(), jsondata)
    story.save()
    return 'success', 200


@stories.route('/<storyId>', methods=['DELETE'])
@requires_auth
def deleteStory(storyId):
  story = Story.objects.filter(id=ObjectId(storyId))
  if g.botId:
      story=story.filter(bot=g.botId)
      botId=g.botId
  else:
      botId='default'
  story.get().delete()
  try:
      intentClassifier = IntentClassifier()
      intentClassifier.setBotId(g.botId)
      intentClassifier.train()
  except BaseException:
      pass

  try:
      os.remove("{}/{},{}.model".format(app.config["MODELS_DIR"],botId, storyId))
  except OSError:
      pass
  return buildResponse.sentOk()


@stories.route('/bot')
@requires_auth
def readBots():
  if g.botId:
    bots = Bot.objects(_id=g.botId)
  else:
    bots = Bot.objects()
  return buildResponse.sentJson(bots.to_json())

@stories.route('/bot', methods=['POST'])
def createBot():
    content = request.get_json(silent=True)

    bot = Bot()
    bot.botName = content.get("botName")
    bot.username = content.get("username")
    bot.password = content.get("password")

    try:
        bot.save()
    except Exception as e:
        return buildResponse.buildJson({"error": str(e)})
    return buildResponse.sentOk()

@stories.route('/bot/<botId>', methods=['PUT'])
@requires_auth
def updateBot(botId):
    jsondata = loads(request.get_data())
    
    bot = Bot.objects.get(id=ObjectId(botId))
    bot = update_document(bot, jsondata)
    bot.save()
    return 'success', 200
