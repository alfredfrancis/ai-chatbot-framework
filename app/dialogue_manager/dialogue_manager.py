import json
import logging
from jinja2 import Template
from app.agents.models import Bot
from app.intents.models import Intent
from app.nlu.pipeline import NLUPipeline, IntentClassifier, EntityExtractor
from app.chat.utils import SilentUndefined, call_api, get_synonyms, split_sentence
from app.dialogue_manager.models import ChatModel

logger = logging.getLogger('dialogue_manager')

class DialogueManager:
    def __init__(self):
        self.nlu_pipeline = NLUPipeline()
        
    def update_model(self, models_dir):
        """
        Signal hook to be called after training is completed.
        Reloads ML models and synonyms.
        """
        synonyms = get_synonyms()
        
        # Initialize pipeline with components
        self.nlu_pipeline = NLUPipeline([
            IntentClassifier(),
            EntityExtractor(synonyms)
        ])
        
        # Load models
        self.nlu_pipeline.load(models_dir)
        logger.info("NLU Pipeline models updated")

    def process(self, app, chat_model: ChatModel) -> ChatModel:
        """
        Single entry point to process the dialogue request.

        :param chat_model: The ChatModel instance containing the request data.
        :return: Processed ChatModel instance.
        """
        logger.debug(f"Received request: {chat_model.to_json()}")
        chat_model_response = chat_model.clone()
        context = {"context": chat_model.context}

        # reset intent and parameters of already completed conversation
        if chat_model_response.complete:
            chat_model_response.reset()



        try:
            # Step 1: Process through NLU pipeline
            nlu_result = self.nlu_pipeline.process({"text": chat_model_response.input_text})
            
            # Step 2: Get intent ID and confidence
            query_intent_id, intent_confidence = self._get_intent_id_and_confidence(app, chat_model_response, nlu_result)

            # Step 3: Retrieve the intent object
            query_intent = self._get_intent(query_intent_id)
            if query_intent is None:
                query_intent = self._get_fallback_intent(app)
            
            chat_model_response.nlu = nlu_result

            # if query_intent is not the same as acitve intent, fetch active intent as well
            active_intent_id = chat_model_response.intent.get("id")
            if active_intent_id and  query_intent_id != active_intent_id:
                active_intent = self._get_intent(chat_model_response.intent["id"])
            else:
                active_intent = query_intent

            # Step 4: Process the intent
            chat_model_response, active_intent = self._process_intent(query_intent, active_intent, chat_model_response, context, nlu_result)
            chat_model_response.intent = {
                "id": active_intent.intentId
            }

            # Step 5: Handle API trigger if the intent is complete
            if chat_model_response.complete:
                chat_model_response = self._handle_api_trigger(active_intent, chat_model_response, context)

            logger.info(f"Processed input: {chat_model_response.input_text}", extra=chat_model_response.to_json())
            return chat_model_response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    def _get_intent_id_and_confidence(self, app, chat_model, nlu_result):
        """
        Determine the intent ID and confidence based on the request input.

        :param chat_model: The ChatModel instance containing the request data.
        :param nlu_result: The result from NLU pipeline processing.
        :return: Tuple of (intent_id, confidence).
        """
        input_text = chat_model.input_text
        if input_text.startswith("/"):
            intent_id = input_text.split("/")[1]
            confidence = 1.0
        else:
            predicted = nlu_result["intent"]
            bot = Bot.objects.get(name="default")
            
            if predicted["confidence"] < bot.config.get("confidence_threshold", 0.90):
                intent = Intent.objects.get(intentId=app.config["DEFAULT_FALLBACK_INTENT_NAME"])
                return intent.intentId, 1.0
            else:
                return predicted["intent"], predicted["confidence"]
        return intent_id, confidence

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

    def _process_intent(self, query_intent, active_intent, chat_model_response, context, nlu_result):
        """
        Process the intent and update the result model with extracted parameters and other details.

        :param query_intent: The Intent object representing the current query.
        :param confidence: The confidence score of the intent prediction.
        :param chat_model: The original ChatModel instance.
        :param chat_model_response: The ChatModel instance to be updated.
        :param context: The context dictionary.
        :param nlu_result: The result from NLU pipeline processing.
        :return: Updated ChatModel instance.
        """

        # cancel intent should cancel active intent and reset chat model
        if query_intent.intentId == "cancel":
            active_intent = query_intent
            chat_model_response.complete = True
            chat_model_response.parameters = []
            chat_model_response.extracted_parameters = {}
            chat_model_response.missing_parameters = {}
            chat_model_response.current_node = None
            return chat_model_response, active_intent


        parameters = active_intent.parameters or []

        if parameters:
            # Get entities from NLU pipeline result
            extracted_entities = nlu_result.get("entities", {})

            # Group entities by type
            entities_by_type = {}
            for entity_name, entity_value in extracted_entities.items():
                if entity_name not in entities_by_type:
                    entities_by_type[entity_name] = []
                entities_by_type[entity_name].append(entity_value)

            # populate parameters
            if len(chat_model_response.parameters) == 0:
                for param in parameters:
                    chat_model_response.parameters.append({
                        "name": param.name,
                        "type": param.type,
                        "required": param.required
                    })
                    
            # Match extracted entities with parameters based on type
            for param in parameters:
                # For free_text parameters being prompted
                if param.type == "free_text" and chat_model_response.current_node == param.name:
                    chat_model_response.extracted_parameters[param.name] = chat_model_response.input_text
                    continue
                else:
                    # Get all entities of matching type
                    if param.type in entities_by_type and entities_by_type[param.type]:
                        # Take the next available entity of this type
                        chat_model_response.extracted_parameters[param.name] = entities_by_type[param.type].pop(0)

            # Update context with extracted_parameters
            context["parameters"] = chat_model_response.extracted_parameters

            # Handle missing parameters
            chat_model_response = self._handle_missing_parameters(parameters, chat_model_response)

        # Check if there are no missing parameters to mark the intent as complete
        chat_model_response.complete = not chat_model_response.missing_parameters
        return chat_model_response, active_intent

    def _handle_missing_parameters(self, parameters, chat_model_response):
        """
        Handle missing parameters in the result model.

        :param parameters: List of parameters from the intent.
        :param chat_model_response: The ChatModel instance to be updated.
        :param intent: The Intent object.
        :return: Updated ChatModel instance.
        """
        missing_parameters = []
        chat_model_response.missing_parameters = []

        # clear current node
        chat_model_response.current_node = None
        chat_model_response.speech_response = None

        for parameter in parameters:
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
