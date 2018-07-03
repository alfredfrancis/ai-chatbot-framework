# -*- coding: utf-8 -*-

import json

from flask import Blueprint, request, abort
from jinja2 import Template

from app import app
from app.agents.models import Bot
from app.commons import build_response
from app.endpoint.utils import SilentUndefined
from app.endpoint.utils import call_api
from app.endpoint.utils import get_synonyms
from app.endpoint.utils import split_sentence
from app.intents.models import Intent
from app.nlu.classifiers.starspace_intent_classifier import \
    EmbeddingIntentClassifier
from app.nlu.entity_extractor import EntityExtractor
from app.nlu.tasks import model_updated_signal

endpoint = Blueprint('api', __name__, url_prefix='/api')

sentence_classifier = None
synonyms = None
entity_extraction = None


# Request Handler
@endpoint.route('/v1', methods=['POST'])
def api():
    """
    Endpoint to converse with chatbot.
    Chat context is maintained by exchanging the payload between client and bot.

    sample input/output payload =>

    {
      "currentNode": "",
      "complete": false,
      "parameters": [],
      "extractedParameters": {},
      "missingParameters": [],
      "intent": {
      },
      "context": {},
      "input": "hello",
      "speechResponse": [
      ]
    }

    :param json:
    :return json:
    """
    request_json = request.get_json(silent=True)
    result_json = request_json

    if request_json:

        context = {"context": request_json["context"]}

        if app.config["DEFAULT_WELCOME_INTENT_NAME"] in request_json.get(
                "input"):
            intent = Intent.objects(
                intentId=app.config["DEFAULT_WELCOME_INTENT_NAME"]).first()
            result_json["complete"] = True
            result_json["intent"]["object_id"] = str(intent.id)
            result_json["intent"]["id"] = str(intent.intentId)
            result_json["input"] = request_json.get("input")
            template = Template(
                intent.speechResponse,
                undefined=SilentUndefined)
            result_json["speechResponse"] = split_sentence(template.render(**context))

            app.logger.info(request_json.get("input"), extra=result_json)
            return build_response.build_json(result_json)

        intent_id, confidence, suggestions = predict(request_json.get("input"))
        app.logger.info("intent_id => %s" % intent_id)
        intent = Intent.objects.get(intentId=intent_id)

        if intent.parameters:
            parameters = intent.parameters
        else:
            parameters = []

        if ((request_json.get("complete") is None) or (
                request_json.get("complete") is True)):
            result_json["intent"] = {
                "object_id": str(intent.id),
                "confidence": confidence,
                "id": str(intent.intentId.encode('utf8'))
            }

            if parameters:
                # Extract NER entities
                extracted_parameters = entity_extraction.predict(
                    intent_id, request_json.get("input"))

                missing_parameters = []
                result_json["missingParameters"] = []
                result_json["extractedParameters"] = {}
                result_json["parameters"] = []
                for parameter in parameters:
                    result_json["parameters"].append({
                        "name": parameter.name,
                        "type": parameter.type,
                        "required": parameter.required
                    })

                    if parameter.required:
                        if parameter.name not in extracted_parameters.keys():
                            result_json["missingParameters"].append(
                                parameter.name)
                            missing_parameters.append(parameter)

                result_json["extractedParameters"] = extracted_parameters

                if missing_parameters:
                    result_json["complete"] = False
                    current_node = missing_parameters[0]
                    result_json["currentNode"] = current_node["name"]
                    result_json["speechResponse"] = split_sentence(current_node["prompt"])
                else:
                    result_json["complete"] = True
                    context["parameters"] = extracted_parameters
            else:
                result_json["complete"] = True

        elif request_json.get("complete") is False:
            if "cancel" not in intent.name:
                intent_id = request_json["intent"]["id"]
                intent = Intent.objects.get(intentId=intent_id)

                extracted_parameter = entity_extraction.replace_synonyms({
                    request_json.get("currentNode"): request_json.get("input")
                })

                # replace synonyms for entity values
                result_json["extractedParameters"].update(extracted_parameter)

                result_json["missingParameters"].remove(
                    request_json.get("currentNode"))

                if len(result_json["missingParameters"]) == 0:
                    result_json["complete"] = True
                    context = {"parameters": result_json["extractedParameters"],
                               "context": request_json["context"]}
                else:
                    missing_parameter = result_json["missingParameters"][0]
                    result_json["complete"] = False
                    current_node = [
                        node for node in intent.parameters if missing_parameter in node.name][0]
                    result_json["currentNode"] = current_node.name
                    result_json["speechResponse"] = split_sentence(current_node.prompt)
            else:
                result_json["currentNode"] = None
                result_json["missingParameters"] = []
                result_json["parameters"] = {}
                result_json["intent"] = {}
                result_json["complete"] = True

        if result_json["complete"]:
            if intent.apiTrigger:
                isJson = False
                parameters = result_json["extractedParameters"]
                headers = intent.apiDetails.get_headers()
                app.logger.info("headers %s" % headers)
                url_template = Template(
                    intent.apiDetails.url, undefined=SilentUndefined)
                rendered_url = url_template.render(**context)
                if intent.apiDetails.isJson:
                    isJson = True
                    request_template = Template(
                        intent.apiDetails.jsonData, undefined=SilentUndefined)
                    parameters = json.loads(request_template.render(**context))

                try:
                    result = call_api(rendered_url,
                                      intent.apiDetails.requestType, headers,
                                      parameters, isJson)
                except Exception as e:
                    app.logger.warn("API call failed", e)
                    result_json["speechResponse"] = ["Service is not available. Please try again later."]
                else:
                    context["result"] = result
                    template = Template(
                        intent.speechResponse, undefined=SilentUndefined)
                    result_json["speechResponse"] = split_sentence(template.render(**context))
            else:
                context["result"] = {}
                template = Template(intent.speechResponse,
                                    undefined=SilentUndefined)
                result_json["speechResponse"] = split_sentence(template.render(**context))
        app.logger.info(request_json.get("input"), extra=result_json)
        return build_response.build_json(result_json)
    else:
        return abort(400)


def update_model(app, message, **extra):
    """
    Signal hook to be called after training is completed.
    Reloads ml models and synonyms.
    :param app:
    :param message:
    :param extra:
    :return:
    """
    global sentence_classifier

    sentence_classifier = EmbeddingIntentClassifier.load(
        app.config["MODELS_DIR"], app.config["USE_WORD_VECTORS"])

    synonyms = get_synonyms()

    global entity_extraction

    entity_extraction = EntityExtractor(synonyms)

    app.logger.info("Intent Model updated")


with app.app_context():
    update_model(app, "Models updated")

model_updated_signal.connect(update_model, app)


def predict(sentence):
    """
    Predict Intent using Intent classifier
    :param sentence:
    :return:
    """
    bot = Bot.objects.get(name="default")
    predicted, intents = sentence_classifier.process(sentence)
    app.logger.info("predicted intent %s", predicted)
    if predicted["confidence"] < bot.config.get("confidence_threshold", .90):
        intents = Intent.objects(intentId=app.config["DEFAULT_FALLBACK_INTENT_NAME"])
        intents = intents.first().intentId
        return intents, 1.0, []
    else:
        return predicted["intent"], predicted["confidence"], intents[1:]
