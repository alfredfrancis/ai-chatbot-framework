from flask import request
from ikyCommons import errorCodes
from ikyCore.intentClassifier import IntentClassifier
from ikyCore.interface import executeAction
from ikyCore.sequenceLabeler import predict
from ikyWebServer import app, buildResponse


@app.route('/ikyParseAndExecute', methods=['POST'])
def ikyParseAndExecute():
    result = {}
    userQuery = request.form['userQuery']
    if userQuery:
        intentClassifier = IntentClassifier()
        intent = intentClassifier.predict(userQuery)
        if intent:
            predicted = predict(userQuery)
            if "errorCode" not in predicted:
                result["output"] = executeAction(predicted['action_type'], predicted['intent'], predicted["labels"])
            else:
                result = errorCodes.UnableToExtractEntities
        else:
            result = errorCodes.UnidentifiedIntent
    else:
        result = errorCodes.EmptyInput
    return buildResponse.buildJson(result)


# Request Handler
@app.route('/ikyParse', methods=['POST'])
def ikyParse():
    result = {}
    userQuery = request.form['userQuery']
    if userQuery:
        intentClassifier = IntentClassifier()
        result["intent"] = intentClassifier.predict(userQuery)
        if result["intent"]:
            result["entities"] = predict(userQuery)
        else:
            result = errorCodes.UnidentifiedIntent
    else:
        result = errorCodes.EmptyInput
    return buildResponse.buildJson(result)


