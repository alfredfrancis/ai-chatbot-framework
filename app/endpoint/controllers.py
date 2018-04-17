from bson import ObjectId
import json
import requests

from jinja2 import Undefined, Template

from flask import Blueprint, request, abort
from app import app

from app.commons.logger import logger
from app.commons import build_response
from app.nlu.entity_extractor import EntityExtractor
from app.intents.models import Intent


endpoint = Blueprint('api', __name__, url_prefix='/api')


class SilentUndefined(Undefined):
    """
    Class to suppress jinja2 errors and warnings
    """

    def _fail_with_undefined_error(self, *args, **kwargs):
        return 'undefined'

    __add__ = __radd__ = __mul__ = __rmul__ = __div__ = __rdiv__ = \
        __truediv__ = __rtruediv__ = __floordiv__ = __rfloordiv__ = \
        __mod__ = __rmod__ = __pos__ = __neg__ = __call__ = \
        __getitem__ = __lt__ = __le__ = __gt__ = __ge__ = __int__ = \
        __float__ = __complex__ = __pow__ = __rpow__ = \
        _fail_with_undefined_error


def call_api(url, type, parameters, is_json=False):
    """
    Call external API
    :param url:
    :param type:
    :param parameters:
    :param is_json:
    :return:
    """
    print(url, type, parameters, is_json)

    if "GET" in type:
        if is_json:
            print(parameters)
            response = requests.get(url, json=json.loads(parameters))

        else:
            response = requests.get(url, params=parameters)
    elif "POST" in type:
        if is_json:
            response = requests.post(url, json=json.loads(parameters))
        else:
            response = requests.post(url, data=parameters)
    elif "PUT" in type:
        if is_json:
            response = requests.put(url, json=json.loads(parameters))
        else:
            response = requests.put(url, data=parameters)
    elif "DELETE" in type:
        response = requests.delete(url)
    else:
        raise Exception("unsupported request method.")
    result = json.loads(response.text)
    print(result)
    return result


from app.nlu.intent_classifer import IntentClassifier


def predict(sentence):
    """
    Predict Intent using Intent classifier
    :param sentence:
    :return:
    """

    PATH = "{}/{}".format(app.config["MODELS_DIR"],
                          app.config["INTENT_MODEL_NAME"])

    sentence_classifier = IntentClassifier()
    predicted = sentence_classifier.predict(sentence, PATH)

    if not predicted:
        return Intent.objects(
            intentName=app.config["DEFAULT_FALLBACK_INTENT_NAME"]).first().id
    else:
        return predicted["class"]


# Request Handler
@endpoint.route('/v1', methods=['POST'])
def api():
    """
    Endpoint to converse with chatbot
    :param json:
    :return:
    """
    request_json = request.get_json(silent=True)
    result_json = request_json

    if request_json:

        context = {}
        context["context"] = request_json["context"]

        if app.config["DEFAULT_WELCOME_INTENT_NAME"] in request_json.get(
                "input"):
            intent = Intent.objects(
                intentId=app.config["DEFAULT_WELCOME_INTENT_NAME"]).first()
            result_json["complete"] = True
            result_json["intent"]["intentId"] = intent.intentId
            result_json["intent"]["id"] = str(intent.id)
            result_json["input"] = request_json.get("input")
            template = Template(
                intent.speechResponse,
                undefined=SilentUndefined)
            result_json["speechResponse"] = template.render(**context)

            logger.info(request_json.get("input"), extra=result_json)
            return build_response.build_json(result_json)

        intent_id = predict(request_json.get("input"))
        intent = Intent.objects.get(id=ObjectId(intent_id))

        if intent.parameters:
            parameters = intent.parameters
        else:
            parameters = []

        if ((request_json.get("complete") is None) or (
                request_json.get("complete") is True)):
            result_json["intent"] = {
                "name": intent.name,
                "id": str(intent.id)
            }

            if parameters:
                # Extract NER entities
                entity_extraction = EntityExtractor()
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
                    result_json["speechResponse"] = current_node["prompt"]
                else:
                    result_json["complete"] = True
                    context["parameters"] = extracted_parameters
            else:
                result_json["complete"] = True

        elif request_json.get("complete") is False:
            if "cancel" not in intent.name:
                intent_id = request_json["intent"]["id"]
                intent = Intent.objects.get(id=ObjectId(intent_id))
                result_json["extractedParameters"][request_json.get(
                    "currentNode")] = request_json.get("input")

                result_json["missingParameters"].remove(
                    request_json.get("currentNode"))

                if len(result_json["missingParameters"]) == 0:
                    result_json["complete"] = True
                    context = {}
                    context["parameters"] = result_json["extractedParameters"]
                    context["context"] = request_json["context"]
                else:
                    missing_parameter = result_json["missingParameters"][0]
                    result_json["complete"] = False
                    current_node = [
                        node for node in intent.parameters if missing_parameter in node.name][0]
                    result_json["currentNode"] = current_node.name
                    result_json["speechResponse"] = current_node.prompt
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

                url_template = Template(
                    intent.apiDetails.url, undefined=SilentUndefined)
                rendered_url = url_template.render(**context)
                if intent.apiDetails.isJson:
                    isJson = True
                    request_template = Template(
                        intent.apiDetails.jsonData, undefined=SilentUndefined)
                    parameters = request_template.render(**context)

                try:
                    result = call_api(rendered_url,
                                      intent.apiDetails.requestType,
                                      parameters, isJson)
                except Exception as e:
                    print(e)
                    result_json["speechResponse"] = "Service is not available. "
                else:
                    print(result)
                    context["result"] = result
                    template = Template(
                        intent.speechResponse, undefined=SilentUndefined)
                    result_json["speechResponse"] = template.render(**context)
            else:
                context["result"] = {}
                template = Template(intent.speechResponse,
                                    undefined=SilentUndefined)
                result_json["speechResponse"] = template.render(**context)
        logger.info(request_json.get("input"), extra=result_json)
        return build_response.build_json(result_json)
    else:
        return abort(400)
