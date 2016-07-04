from flask import request
import html2text

from ikyCore.packResult import packResult
from ikyCore.intentClassifier import IntentClassifier
from ikyCore.interface import executeAction
from ikyCore import sequenceLabeler
from ikyCore import nlp

from ikyCommons import errorCodes

from ikyWebServer import app, buildResponse


@app.route('/ikyParseAndExecute', methods=['POST'])
def ikyParseAndExecute():
    result = {}
    userQuery = request.form['userQuery']
    if userQuery:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(userQuery)
        if storyId:
            extractedEntities = sequenceLabeler.predict(storyId,userQuery)
            resultDictonary = packResult(storyId,extractedEntities)
            if "errorCode" not in resultDictonary:
                result["output"] = executeAction(resultDictonary['actionType'], resultDictonary['actionName'], resultDictonary["entities"])
            else:
                result = errorCodes.UnableToextractentities
        else:
            result = errorCodes.UnidentifiedIntent
    else:
        result = errorCodes.EmptyInput
    return buildResponse.buildJson(result)


# Request Handler
@app.route('/ikyParse', methods=['POST'])
def ikyParse():
    userQuery = request.form['userQuery']

    if userQuery:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(userQuery)
        if storyId:
            extractedEntities = sequenceLabeler.predict(storyId,userQuery)

            if "errorCode" not in extractedEntities:
                result = packResult(storyId,extractedEntities)
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
