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
        userQuery = request.form['userQuery']

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
    if request.form['userQuery']:
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
    """
      channel_id=hawos4dqtby53pd64o4a4cmeoo&
      channel_name=town-square&
      team_domain=someteam&
      team_id=kwoknj9nwpypzgzy78wkw516qe&
      post_id=axdygg1957njfe5pu38saikdho&
      text=some+text+here&
      timestamp=1445532266&
      token=zmigewsanbbsdf59xnmduzypjc&
      trigger_word=some&
      user_id=rnina9994bde8mua79zqcg5hmo&
      user_name=somename
    """
    TOKEN = "zdb17ppgwpr178ja68wseghswr"
    if (request.form['token'] == TOKEN):

        userQuery = request.form['text']
        resultDictonary = ikyParseAndExecute(userQuery)
        if "errorCode" not in resultDictonary:
            result = resultDictonary["output"]
        else:
            result = resultDictonary["description"]
        try:
            requests.post("http://172.30.10.119:8075/hooks/nfsshnro73f9xproni3uazib7h",
                          json={"username": "iky", "text": result})
        except:
            pass
        return "Sucess"
    return "This can only be accessed from Mattermost"
