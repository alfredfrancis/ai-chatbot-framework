import json
import logging
from jinja2 import Template
from bson.objectid import ObjectId
from app.database import find_one
from app.main import app
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

    async def update_model(self):
        """
        Signal hook to be called after training is completed.
        Reloads ML models and synonyms.
        """
        self.sentence_classifier.load(app.state.config["MODELS_DIR"])
        self.synonyms = await get_synonyms()
        self.entity_extraction = EntityExtractor(self.synonyms)
        logger.info("Intent Model updated")

    async def process(self, chat_model: ChatModel) -> ChatModel:
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
            intent_id, confidence = await self._get_intent_id_and_confidence(chat_model)

            # Step 2: Retrieve the intent object
            intent = await self._get_intent(intent_id)
            if intent is None:
                intent = await self._get_fallback_intent()

            # Step 3: Process the intent
            chat_model_response = await self._process_intent(intent, confidence, chat_model, chat_model_response, context)

            # Step 4: Handle API trigger if the intent is complete
            if chat_model_response.complete:
                chat_model_response = await self._handle_api_trigger(intent, chat_model_response, context)

            logger.info(f"Processed input: {chat_model.input_text}", extra=chat_model_response.to_json())
            return chat_model_response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    async def _get_intent_id_and_confidence(self, chat_model):
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
            intent_id, confidence, _ = await self._predict(input_text)
        logger.info(f"Predicted intent_id: {intent_id}")
        return intent_id, confidence

    async def _predict(self, sentence):
        """
        Predict the intent using the intent classifier.

        :param sentence: The input sentence to classify.
        :return: Tuple of (predicted intent ID, confidence, other intents).
        """
        bot = await find_one("bots", {"name": "default"})
        predicted, intents = self.sentence_classifier.process(sentence)
        logger.info(f"Predicted intent: {predicted}")
        logger.info(f"Other intents: {intents}")

        if predicted["confidence"] < bot.get("config", {}).get("confidence_threshold", 0.90):
            fallback_intent = await self._get_fallback_intent()
            return fallback_intent["intentId"], 1.0, []
        else:
            return predicted["intent"], predicted["confidence"], intents[1:]

    async def _get_intent(self, intent_id):
        """
        Retrieve the intent object by its ID.

        :param intent_id: The ID of the intent.
        :return: The Intent object.
        """
        try:
            return await find_one("intents", {"intentId": intent_id})
        except Exception as e:
            logger.warning(f"Intent not found: {intent_id}")
            return None

    async def _get_fallback_intent(self):
        """
        Retrieve the fallback intent from the app configuration.

        :return: The fallback Intent object.
        """
        fallback_intent_id = app.state.config.get("DEFAULT_FALLBACK_INTENT_NAME")
        return await find_one("intents", {"intentId": fallback_intent_id})

    async def _process_intent(self, intent, confidence, chat_model, chat_model_response, context):
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
            "object_id": str(intent["_id"]),
            "confidence": confidence,
            "id": intent["intentId"]
        }

        parameters = intent.get("parameters", [])
        chat_model_response.extracted_parameters = chat_model.extracted_parameters

        if parameters:
            # Extract entities and update extracted_parameters
            extracted_entities = self.entity_extraction.predict(intent["intentId"], chat_model.input_text)

            # Replace synonyms in the extracted parameters
            extracted_entities = self.entity_extraction.replace_synonyms(extracted_entities)

            # Group entities by type
            entities_by_type = {}
            for entity_name, entity_value in extracted_entities.items():
                if entity_name not in entities_by_type:
                    entities_by_type[entity_name] = []
                entities_by_type[entity_name].append(entity_value)

            # Match extracted entities with parameters based on type
            for param in parameters:
                if param["type"] != "free_text":  # Skip free_text parameters
                    # Get all entities of matching type
                    if param["type"] in entities_by_type and entities_by_type[param["type"]]:
                        # Take the next available entity of this type
                        chat_model_response.extracted_parameters[param["name"]] = entities_by_type[param["type"]].pop(0)

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
                "name": parameter["name"],
                "type": parameter["type"],
                "required": parameter["required"]
            })

            # For free_text parameters being prompted
            if parameter["type"] == "free_text" and chat_model_response.current_node == parameter["name"]:
                chat_model_response.extracted_parameters[parameter["name"]] = chat_model_response.input_text
                continue

            if parameter["required"] and parameter["name"] not in chat_model_response.extracted_parameters:
                chat_model_response.missing_parameters.append(parameter["name"])
                missing_parameters.append(parameter)

        if missing_parameters:
            current_node = missing_parameters[0]
            chat_model_response.current_node = current_node["name"]
            chat_model_response.speech_response = split_sentence(current_node["prompt"])

        return chat_model_response

    async def _handle_api_trigger(self, intent, chat_model_response, context):
        """
        Handle API trigger if the intent requires it.

        :param intent: The Intent object.
        :param chat_model_response: The ChatModel instance to be updated.
        :param context: The context dictionary.
        :return: Updated ChatModel instance.
        """
        if intent.get("apiTrigger"):
            try:
                result = await self._call_intent_api(intent, context)
                context["result"] = result
                template = Template(intent["speechResponse"], undefined=SilentUndefined)
                chat_model_response.speech_response = split_sentence(template.render(**context))
            except Exception as e:
                logger.warning(f"API call failed: {e}")
                chat_model_response.speech_response = ["Service is not available. Please try again later."]
        else:
            context["result"] = {}
            template = Template(intent["speechResponse"], undefined=SilentUndefined)
            chat_model_response.speech_response = split_sentence(template.render(**context))

        return chat_model_response

    async def _call_intent_api(self, intent, context):
        """
        Call the API associated with the intent.

        :param intent: The Intent object.
        :param context: The context dictionary.
        :return: The result of the API call.
        """
        api_details = intent.get("apiDetails", {})
        headers = {}
        for header in api_details.get("headers", []):
            headers[header["headerKey"]] = header["headerValue"]

        url_template = Template(api_details["url"], undefined=SilentUndefined)
        rendered_url = url_template.render(**context)

        if api_details.get("isJson"):
            request_template = Template(api_details["jsonData"], undefined=SilentUndefined)
            parameters = json.loads(request_template.render(**context))
        else:
            parameters = context.get("parameters", {})

        return await call_api(rendered_url, api_details["requestType"], headers, parameters, api_details.get("isJson", False))
