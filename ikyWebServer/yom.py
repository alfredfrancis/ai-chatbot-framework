from flask import request
from ikyCore.intentClassifier import IntentClassifier
from ikyCore import sequenceLabeler
from ikyCore.packResult import packResult
from ikyCore.interface import executeAction

from ikyCommons import errorCodes

from ikyWebServer import app, buildResponse

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

@app.route('/renderChat', methods=['POST'])
def renderChat():
    extractedEntities = {}
    result = {}
    userId =  request.form['userId']
    userQuery = request.form.get('userQuery')

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
                result = "Can you please rephrase that ?"
        else:
            result = "Sorry, i'm not able to understand that yet."
    else:
        result = errorCodes.emptyInput
    logger.info(userQuery, extra={'userId': userId,
                                  'extractedEntities': extractedEntities,
                                  'result': result})
    return buildResponse.buildJson(result)

@app.route('/pingUser', methods=['POST'])
def pingUser():
    return buildResponse.sentOk()
