from flask import request
import html2text

from ikyCore.intentClassifier import IntentClassifier
from ikyCore import sequenceLabeler
from ikyCore import nlp
from ikyCore.packResult import packResult
from ikyCore.interface import executeAction

from ikyCommons import errorCodes

from ikyWebServer import app, buildResponse

import requests


@app.route('/ikyParseAndExecute', methods=['POST'])
def ikyParseAndExecute(userQuery=None):
    result = {}
    if not userQuery:
        webRequest = True
        userQuery = request.form['userQuery']
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

    if webRequest:
	print("hello")
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
    TOKEN = "c1yad6jwrb8n5be4ojfqy35ayw"
    if (request.form['token'] == TOKEN):
        userQuery = request.form['text']
        resultDictonary = ikyParseAndExecute(userQuery)
        if resultDictonary.get("errorCode") == 801:
            result = "Can you be little more specific ?"
        elif resultDictonary.get("errorCode") == 701:
            result = "Sorry! I'm not able to do that yet."
        else:
            result = resultDictonary["output"]
        response = requests.post("http://172.17.0.3:8065/hooks/uzmrc9txn38ytgxtkmfp7rzwwe",json={"username": "iky", "text": result})
        return  buildResponse.sentOk()
    return "This can only be accessed from Mattermost"
