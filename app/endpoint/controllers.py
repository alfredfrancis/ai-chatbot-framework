import copy
import json
from flask import Blueprint, request, abort, current_app as app
from jinja2 import Template
from app.agents.models import Bot
from app.commons import build_response
from app.endpoint.utils import SilentUndefined, call_api, get_synonyms, split_sentence
from app.intents.models import Intent
from app.nlu.classifiers.sklearn_intent_classifer import SklearnIntentClassifier
from app.nlu.entity_extractor import EntityExtractor

endpoint = Blueprint('api', __name__, url_prefix='/api')

# Global instances (to be initialized)
sentence_classifier = SklearnIntentClassifier()
synonyms = None
entity_extraction = None

@endpoint.route('/v1', methods=['POST'])
def api():
    """
    Endpoint to converse with the chatbot.
    Maintains chat context by exchanging the payload between client and bot.

    :return: JSON response with the chatbot's reply and context.
    """
    request_json = request.get_json(silent=True)
    if not request_json:
        app.logger.error("Invalid request: No JSON payload")
        return abort(400)

    app.logger.debug(f"Received request: {request_json}")
    result_json = copy.deepcopy(request_json)
    context = {"context": request_json.get("context", {})}

    try:
        intent_id, confidence = _get_intent_id_and_confidence(request_json)
        intent = _get_intent(intent_id)

        if intent is None:
            intent = _get_fallback_intent()

        result_json = _process_intent(intent, confidence, request_json, result_json, context)

        if result_json.get("complete", True):
            result_json = _handle_api_trigger(intent, result_json, context)

        app.logger.info(f"Processed input: {request_json.get('input')}", extra=result_json)
        return build_response.build_json(result_json)

    except Exception as e:
        app.logger.error(f"Error processing request: {e}", exc_info=True)
        return abort(500)

def _get_intent_id_and_confidence(request_json):
    """
    Determine the intent ID and confidence based on the request input.

    :param request_json: The JSON payload from the request.
    :return: Tuple of (intent_id, confidence).
    """
    input_text = request_json.get("input", "")
    if input_text.startswith("/"):
        intent_id = input_text.split("/")[1]
        confidence = 1.0
    else:
        intent_id, confidence, _ = predict(input_text)
    app.logger.info(f"Predicted intent_id: {intent_id}")
    return intent_id, confidence

def _get_intent(intent_id):
    """
    Retrieve the intent object by its ID.

    :param intent_id: The ID of the intent.
    :return: The Intent object.
    """
    try:
        return Intent.objects.get(intentId=intent_id)
    except Intent.DoesNotExist:
        app.logger.warning(f"Intent not found: {intent_id}")
        return None

def _get_fallback_intent():
    """
    Retrieve the fallback intent from the app configuration.

    :return: The fallback Intent object.
    """
    fallback_intent_id = app.config.get("DEFAULT_FALLBACK_INTENT_NAME")
    return Intent.objects.get(intentId=fallback_intent_id)

def _process_intent(intent, confidence, request_json, result_json, context):
    """
    Process the intent and update the result JSON with extracted parameters and other details.

    :param intent: The Intent object.
    :param confidence: The confidence score of the intent prediction.
    :param request_json: The original request JSON.
    :param result_json: The result JSON to be updated.
    :param context: The context dictionary.
    :return: Updated result JSON.
    """
    result_json["intent"] = {
        "object_id": str(intent.id),
        "confidence": confidence,
        "id": intent.intentId
    }

    parameters = intent.parameters or []
    result_json["extractedParameters"] = request_json.get("extractedParameters", {})

    if parameters:
        # Extract entities and update extractedParameters
        extracted_parameters = entity_extraction.predict(intent.intentId, request_json.get("input", ""))

        # replace synonyms in the extracted parameters
        extracted_parameters = entity_extraction.replace_synonyms(extracted_parameters)

        result_json["extractedParameters"].update(extracted_parameters)

        # Update context with extractedParameters (matching original logic)
        context["parameters"] = result_json["extractedParameters"]

        # Handle missing parameters
        result_json = _handle_missing_parameters(parameters, result_json, intent)

    # Check if there are no missing parameters to mark the intent as complete
    result_json["complete"] = not result_json.get("missingParameters", [])
    return result_json

def _handle_missing_parameters(parameters, result_json, intent):
    """
    Handle missing parameters in the result JSON.

    :param parameters: List of parameters from the intent.
    :param result_json: The result JSON to be updated.
    :param intent: The Intent object.
    :return: Updated result JSON.
    """
    missing_parameters = []
    result_json["missingParameters"] = []
    result_json["parameters"] = []

    for parameter in parameters:
        result_json["parameters"].append({
            "name": parameter.name,
            "type": parameter.type,
            "required": parameter.required
        })

        if parameter.required and parameter.name not in result_json["extractedParameters"]:
            result_json["missingParameters"].append(parameter.name)
            missing_parameters.append(parameter)

    if missing_parameters:
        current_node = missing_parameters[0]
        result_json["currentNode"] = current_node.name
        result_json["speechResponse"] = split_sentence(current_node.prompt)

    return result_json

def _handle_api_trigger(intent, result_json, context):
    """
    Handle API trigger if the intent requires it.

    :param intent: The Intent object.
    :param result_json: The result JSON to be updated.
    :param context: The context dictionary.
    :return: Updated result JSON.
    """
    if intent.apiTrigger:
        try:
            result = _call_intent_api(intent, context)
            context["result"] = result
            template = Template(intent.speechResponse, undefined=SilentUndefined)
            result_json["speechResponse"] = split_sentence(template.render(**context))
        except Exception as e:
            app.logger.warning(f"API call failed: {e}")
            result_json["speechResponse"] = ["Service is not available. Please try again later."]
    else:
        context["result"] = {}
        template = Template(intent.speechResponse, undefined=SilentUndefined)
        result_json["speechResponse"] = split_sentence(template.render(**context))

    return result_json

def _call_intent_api(intent, context):
    """
    Call the API associated with the intent.

    :param intent: The Intent object.
    :param context: The context dictionary.
    :return: The result of the API call.
    """
    headers = intent.apiDetails.get_headers()
    url_template = Template(intent.apiDetails.url, undefined=SilentUndefined)
    rendered_url = url_template.render(**context)

    if intent.apiDetails.isJson:
        request_template = Template(intent.apiDetails.jsonData, undefined=SilentUndefined)
        parameters = json.loads(request_template.render(**context))
    else:
        parameters = context.get("parameters", {})

    return call_api(rendered_url, intent.apiDetails.requestType, headers, parameters, intent.apiDetails.isJson)

def update_model():
    """
    Signal hook to be called after training is completed.
    Reloads ML models and synonyms.
    """
    global sentence_classifier, synonyms, entity_extraction

    sentence_classifier.load(app.config["MODELS_DIR"])
    synonyms = get_synonyms()
    entity_extraction = EntityExtractor(synonyms)
    app.logger.info("Intent Model updated")

def predict(sentence):
    """
    Predict the intent using the intent classifier.

    :param sentence: The input sentence to classify.
    :return: Tuple of (predicted intent ID, confidence, other intents).
    """
    bot = Bot.objects.get(name="default")
    predicted, intents = sentence_classifier.process(sentence)
    app.logger.info(f"Predicted intent: {predicted}")
    app.logger.info(f"Other intents: {intents}")

    if predicted["confidence"] < bot.config.get("confidence_threshold", 0.90):
        intent = Intent.objects.get(intentId=app.config["DEFAULT_FALLBACK_INTENT_NAME"])
        return intent.intentId, 1.0, []
    else:
        return predicted["intent"], predicted["confidence"], intents[1:]