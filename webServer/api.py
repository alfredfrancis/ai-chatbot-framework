from flask import request, send_file
import html2text
import os
from bson import ObjectId
from core.intentClassifier import IntentClassifier
from core import sequenceLabeler
from core import nlp
from core.packResult import packResult
from core.models import Story
from commons import errorCodes

from webServer import app, buildResponse

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


# Request Handler
@app.route('/api/v1', methods=['POST'])
def api():
    requestJson = request.get_json(silent=True)
    resultJson = requestJson

    if requestJson:
        intentClassifier = IntentClassifier()
        storyId = intentClassifier.predict(requestJson.get("input"))
        print (storyId)
        story = Story.objects.get(id=ObjectId(storyId))
        if story.parameters:
            parameters = story.parameters
        else:
            parameters=[]

        if ((requestJson.get("complete") is None) or (requestJson.get("complete") is True)):
            resultJson["intent"] = {
                "name":story.intentName,
                "storyId":str(story.id)
            }

            if parameters:
                extractedParameters= sequenceLabeler.predict(storyId,
                                                            requestJson.get("input")
                                                            )
                missingParameters = []
                resultJson["missingParameters"] =[]
                resultJson["extractedParameters"] = {}
                resultJson["parameters"]=[]
                for parameter in parameters:
                    resultJson["parameters"].append({
                        "name": parameter.name,
                        "required": parameter.required
                    })

                    if parameter.required:
                        if parameter.name not in  extractedParameters.keys():
                            resultJson["missingParameters"].append(parameter.name)
                            missingParameters.append(parameter)


                if missingParameters:
                    resultJson["complete"] = False
                    currentNode = missingParameters[0]
                    resultJson["currentNode"] = currentNode["name"]
                    resultJson["speechResponse"] = currentNode["prompt"]
                else:
                    resultJson["extractedParameters"] = extractedParameters
                    resultJson["complete"] = True
                    resultJson["speechResponse"] = story.speechResponse
            else:
                resultJson["complete"] = True
                resultJson["speechResponse"] = story.speechResponse

        elif (requestJson.get("complete") is False):
            if "cancel" not in story.intentName:
                storyId = requestJson["intent"]["storyId"]
                story = Story.objects.get(id=ObjectId(storyId))
                resultJson["extractedParameters"][requestJson.get("currentNode")] = requestJson.get("input")

                resultJson["missingParameters"].remove(requestJson.get("currentNode"))

                if len(resultJson["missingParameters"])==0:
                    resultJson["complete"] = True
                    resultJson["speechResponse"] = story.speechResponse
                else:
                    missingParameter = resultJson["missingParameters"][0]
                    resultJson["complete"] = False
                    currentNode = [node for node in story.parameters if missingParameter in node.name][0]
                    resultJson["currentNode"] = currentNode.name
                    resultJson["speechResponse"] = currentNode.prompt
            else:
                resultJson["currentNode"] = None
                resultJson["missingParameters"] = []
                resultJson["parameters"] = {}
                resultJson["intent"] = {}
                resultJson["complete"] = True
                resultJson["speechResponse"] = story.speechResponse

    else:
        resultJson = errorCodes.emptyInput
    return buildResponse.buildJson(resultJson)


@app.route('/buildModel', methods=['POST'])
def buildModel():
    sequenceLabeler.train(request.form['storyId'])
    IntentClassifier().train()
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


# Text To Speech
@app.route('/tts')
def tts():
    voices = {
              "american": "file://commons/fliteVoices/cmu_us_eey.flitevox"
              }
    os.system("echo \"" + request.args.get("text") + "\" | flite -voice " + voices["american"] + "  -o sound.wav")
    path_to_file = "../sound.wav"
    return send_file(
        path_to_file,
        mimetype="audio/wav",
        as_attachment=True,
        attachment_filename="sound.wav")
