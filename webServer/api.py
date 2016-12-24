from flask import request, send_file
import html2text
import os
from core.intentClassifier import IntentClassifier
from core import sequenceLabeler
from core import nlp
from core.packResult import packResult
from core.interface import executeAction

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
    extractedEntities = {}
    userQuery = request.form['userQuery']
    print (userQuery)

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
