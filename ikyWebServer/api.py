from flask import request, send_file
import html2text
import os
from ikyCore.intentClassifier import IntentClassifier
from ikyCore import sequenceLabeler
from ikyCore import nlp
from ikyCore.packResult import packResult
from ikyCore.interface import executeAction

from ikyCommons import errorCodes

from ikyWebServer import app, buildResponse

import requests

# logging begins
import logging

import json_log_formatter

formatter = json_log_formatter.JSONFormatter()
json_handler = logging.FileHandler(filename='log.json')
json_handler.setFormatter(formatter)

logger = logging.getLogger('my_json')
logger.addHandler(json_handler)
logger.setLevel(logging.INFO)
# logging ends

@app.route('/ikyParseAndExecute', methods=['POST'])
def ikyParseAndExecute(userQuery=None):
    userId = "Alfred"
    extractedEntities = {}
    result = {}
    if not userQuery:
        webRequest = True
        userId =  request.form['userId']
        userQuery = request.form.get('userQuery')
    else:
        webRequest = False
    if userQuery:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(userQuery)
        if storyId:
            extractedEntities = sequenceLabeler.predict(storyId, userQuery)
            resultDictonary = packResult(storyId, extractedEntities)
            if "errorCode" not in resultDictonary:
                result["output"] = executeAction(resultDictonary['actionType'], resultDictonary['actionName'],
                                                 resultDictonary["entities"])
            else:
                result = errorCodes.UnableToextractentities
        else:
            result = errorCodes.UnidentifiedIntent
    else:
        result = errorCodes.emptyInpurt
    logger.info(userQuery, extra={'userId': userId,
                                  'extractedEntities': extractedEntities,
                                  'result': result})
    if webRequest:
        return buildResponse.buildJson(result)
    return result


# Request Handler
@app.route('/ikyParse', methods=['POST'])
def ikyParse():
    userQuery = request.form['userQuery']

    if userQuery:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(userQuery)
        if storyId:
            extractedEntities = sequenceLabeler.predict(storyId, userQuery)

            if "errorCode" not in extractedEntities:
                result = packResult(storyId, extractedEntities)
            else:
                result = errorCodes.UnableToExtractEntities
        else:
            result = errorCodes.UnidentifiedIntent
    else:
        result = errorCodes.EmptyInput
    return buildResponse.buildJson(result)


@app.route('/buildModel', methods=['POST'])
def buildModel():
    try:
        sequenceLabeler.train(request.form['storyId'])
        IntentClassifier().train()
    except Exception, e:
        result = errorCodes.NotEnoughData
        return buildResponse.buildJson(result)
    return buildResponse.sentOk()


@app.route('/sentenceTokenize', methods=['POST'])
def sentenceTokenize():
    sentences = html2text.html2text(request.form['sentences'])
    result = nlp.sentenceTokenize(sentences)
    return buildResponse.sentPlainText(result)


@app.route('/posTagAndLabel', methods=['POST'])
def posTagAndLabel():
    sentences = request.form['sentences']
    cleanSentences = html2text.html2text(sentences)
    result = nlp.posTagAndLabel(cleanSentences)
    return buildResponse.buildJson(result)


@app.route('/mattermost/incoming/', methods=['POST'])
def mattermost():
    TOKEN = "sgh9ymndefgs8bopuao3xd8r3y"
    if (request.form['token'] == TOKEN):
        userQuery = request.form['text']
        resultDictonary = ikyParseAndExecute(userQuery)
        if resultDictonary.get("errorCode") == 801:
            result = "Can you be little more specific ?"
        elif resultDictonary.get("errorCode") == 701:
            result = "Sorry! I'm not able to do that yet."
        else:
            result = resultDictonary["output"]
        response = requests.post("https://chat.luluone.com/hooks/opyufr1qsibcjqqhgkt93e149h",
                                 json={"username": "iky", "text": result})
        return buildResponse.sentOk()
    return "This can only be accessed from Mattermost"


@app.route('/tts')
def tts():
    voices = {"american": "file://cmu_us_eey.flitevox",
              "indian": "file://cmu_us_axb.flitevox"
              }
    os.system("echo \"" + request.args.get("text") + "\" | flite -voice " + voices[
        request.args.get("country")] + "  -o sound.wav")
    path_to_file = "../sound.wav"
    return send_file(
        path_to_file,
        mimetype="audio/wav",
        as_attachment=True,
        attachment_filename="sound.wav")
