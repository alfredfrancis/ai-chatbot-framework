import json
import logging
from jinja2 import Template
from app.agents.models import Bot
from app.intents.models import Intent
from app.nlu.classifiers.sklearn_intent_classifer import SklearnIntentClassifier
from app.nlu.entity_extractors.crf_entity_extractor import EntityExtractor
from app.chat.utils import SilentUndefined, call_api, get_synonyms, split_sentence
from app.dialogue_manager.models import ChatModel

logger = logging.getLogger('dialogue_manager')

class DialogueManager:
    def __init__(self):
        self.sentence_classifier = SklearnIntentClassifier()
        self.synonyms = None
        self.entity_extraction = None

    def update_model(self, app):
        """
        Signal hook to be called after training is completed.
        Reloads ML models and synonyms.
        """
        self.sentence_classifier.load(app.config["MODELS_DIR"])
        self.synonyms = get_synonyms()
        self.entity_extraction = EntityExtractor(self.synonyms)
        logger.info("Intent Model updated")

    def process(self, app, chat_model: ChatModel) -> ChatModel:
        """
        Single entry point to process the dialogue request.

        :param chat_model: The ChatModel instance containing the request data.
        :return: Processed ChatModel instance.
        """
        logger.debug(f"Received request: {chat_model.to_json()}")
        chat_model_response = chat_model.clone()
        context = {"context": chat_model.context}

        try:
            # Step 1: Get intent ID and confidence
            intent_id, confidence = self._get_intent_id_and_confidence(app, chat_model)

            # Step 2: Retrieve the intent object
            intent = self._get_intent(intent_id)
            if intent is None:
                intent = self._get_fallback_intent(app)

            # Step 3: Process the intent
            chat_model_response = self._process_intent(intent, confidence, chat_model, chat_model_response, context)

            # Step 4: Handle API trigger if the intent is complete
            if chat_model_response.complete:
                chat_model_response = self._handle_api_trigger(intent, chat_model_response, context)

            logger.info(f"Processed input: {chat_model.input_text}", extra=chat_model_response.to_json())
            return chat_model_response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    def _get_intent_id_and_confidence(self, app, chat_model):
        """
        Determine the intent ID and confidence based on the request input.

        :param chat_model: The ChatModel instance containing the request data.
        :return: Tuple of (intent_id, confidence).
        """
        input_text = chat_model.input_text
        if input_text.startswith("/"):
            intent_id = input_text.split("/")[1]
            confidence = 1.0
        else:
            intent_id, confidence, _ = self._predict(app, input_text)
        logger.info(f"Predicted intent_id: {intent_id}")
        return intent_id, confidence

    def _predict(self, app, sentence):
        """
        Predict the intent using the intent classifier.

        :param sentence: The input sentence to classify.
        :return: Tuple of (predicted intent ID, confidence, other intents).
        """
        bot = Bot.objects.get(name="default")
        predicted, intents = self.sentence_classifier.process(sentence)
        logger.info(f"Predicted intent: {predicted}")
        logger.info(f"Other intents: {intents}")

        if predicted["confidence"] < bot.config.get("confidence_threshold", 0.90):
            intent = Intent.objects.get(intentId=app.config["DEFAULT_FALLBACK_INTENT_NAME"])
            return intent.intentId, 1.0, []
        else:
            return predicted["intent"], predicted["confidence"], intents[1:]

    def _get_intent(self, intent_id):
        """
        Retrieve the intent object by its ID.

        :param intent_id: The ID of the intent.
        :return: The Intent object.
        """
        try:
            return Intent.objects.get(intentId=intent_id)
        except Intent.DoesNotExist:
            logger.warning(f"Intent not found: {intent_id}")
            return None

    def _get_fallback_intent(self, app):
        """
        Retrieve the fallback intent from the app configuration.

        :return: The fallback Intent object.
        """
        fallback_intent_id = app.config.get("DEFAULT_FALLBACK_INTENT_NAME")
        return Intent.objects.get(intentId=fallback_intent_id)

    def _process_intent(self, intent, confidence, chat_model, chat_model_response, context):
        """
        Process the intent and update the result model with extracted parameters and other details.

        :param intent: The Intent object.
        :param confidence: The confidence score of the intent prediction.
        :param chat_model: The original ChatModel instance.
        :param chat_model_response: The ChatModel instance to be updated.
        :param context: The context dictionary.
        :return: Updated ChatModel instance.
        """
        chat_model_response.intent = {
            "object_id": str(intent.id),
            "confidence": confidence,
            "id": intent.intentId
        }

        parameters = intent.parameters or []
        chat_model_response.extracted_parameters = chat_model.extracted_parameters

        if parameters:
            # Extract entities and update extracted_parameters
            extracted_parameters = self.entity_extraction.predict(intent.intentId, chat_model.input_text)

            # Replace synonyms in the extracted parameters
            extracted_parameters = self.entity_extraction.replace_synonyms(extracted_parameters)

            chat_model_response.extracted_parameters.update(extracted_parameters)

            # Update context with extracted_parameters
            context["parameters"] = chat_model_response.extracted_parameters

            # Handle missing parameters
            chat_model_response = self._handle_missing_parameters(parameters, chat_model_response, intent)

        # Check if there are no missing parameters to mark the intent as complete
        chat_model_response.complete = not chat_model_response.missing_parameters
        return chat_model_response

    def _handle_missing_parameters(self, parameters, chat_model_response, intent):
        """
        Handle missing parameters in the result model.

        :param parameters: List of parameters from the intent.
        :param chat_model_response: The ChatModel instance to be updated.
        :param intent: The Intent object.
        :return: Updated ChatModel instance.
        """
        missing_parameters = []
        chat_model_response.missing_parameters = []
        chat_model_response.parameters = []

        for parameter in parameters:
            chat_model_response.parameters.append({
                "name": parameter.name,
                "type": parameter.type,
                "required": parameter.required
            })

            if parameter.required and parameter.name not in chat_model_response.extracted_parameters:
                chat_model_response.missing_parameters.append(parameter.name)
                missing_parameters.append(parameter)

        if missing_parameters:
            current_node = missing_parameters[0]
            chat_model_response.current_node = current_node.name
            chat_model_response.speech_response = split_sentence(current_node.prompt)

        return chat_model_response

    def _handle_api_trigger(self, intent, chat_model_response, context):
        """
        Handle API trigger if the intent requires it.

        :param intent: The Intent object.
        :param chat_model_response: The ChatModel instance to be updated.
        :param context: The context dictionary.
        :return: Updated ChatModel instance.
        """
        if intent.apiTrigger:
            try:
                result = self._call_intent_api(intent, context)
                context["result"] = result
                template = Template(intent.speechResponse, undefined=SilentUndefined)
                chat_model_response.speech_response = split_sentence(template.render(**context))
            except Exception as e:
                logger.warning(f"API call failed: {e}")
                chat_model_response.speech_response = ["Service is not available. Please try again later."]
        else:
            context["result"] = {}
            template = Template(intent.speechResponse, undefined=SilentUndefined)
            chat_model_response.speech_response = split_sentence(template.render(**context))

        return chat_model_response

    def _call_intent_api(self, intent, context):
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
