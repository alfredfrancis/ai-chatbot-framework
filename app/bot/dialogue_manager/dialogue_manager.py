import json
import logging
from typing import Dict, List, Optional, Tuple
from jinja2 import Template
from app.admin.bots.store import get_bot
from app.admin.intents.store import list_intents
from app.bot.nlu.pipeline import NLUPipeline
from app.bot.nlu.featurizers import SpacyFeaturizer
from app.bot.nlu.intent_classifiers import IntentClassifier
from app.bot.nlu.entity_extractors import EntityExtractor
from app.bot.dialogue_manager.utils import SilentUndefined, split_sentence
from app.admin.entities.store import list_synonyms
from app.bot.dialogue_manager.models import ChatModel, IntentModel, ParameterModel
from app.bot.dialogue_manager.http_client import call_api
from app.config import app_config

logger = logging.getLogger('dialogue_manager')

class DialogueManager:
    def __init__(self,
                 intents: List[IntentModel],
                 nlu_pipeline: NLUPipeline,
                 fallback_intent_id: str,
                 intent_confidence_threshold: float,
                 ):
        self.nlu_pipeline = nlu_pipeline
        self.intents = {intent.intent_id: intent for intent in intents}  # Map for faster lookup
        self.fallback_intent_id = fallback_intent_id
        self.confidence_threshold = intent_confidence_threshold

    @classmethod
    async def from_config(cls):
        """
        Initialize DialogueManager with all required dependencies
        """

        synonyms = await list_synonyms()

        # Initialize pipeline with components
        nlu_pipeline = NLUPipeline([
            SpacyFeaturizer(app_config.SPACY_LANG_MODEL),
            IntentClassifier(),
            EntityExtractor(synonyms)
        ])
        
        # Load all intents and convert to domain models
        db_intents = await list_intents()
        intents = [IntentModel.from_db(intent) for intent in db_intents]
        
        # Get configuration
        fallback_intent_id = app_config.DEFAULT_FALLBACK_INTENT_NAME
        
        # Get bot configuration
        bot = await get_bot("default")
        confidence_threshold = bot.config.get("confidence_threshold", 0.90)
        
        return cls(intents, nlu_pipeline, fallback_intent_id, confidence_threshold)
        
    def update_model(self, models_dir):
        """
        Signal hook to be called after training is completed.
        Reloads ML models and synonyms.
        """
        # Load models
        self.nlu_pipeline.load(models_dir)
        logger.info("NLU Pipeline models updated")

    async def process(self, chat_model: ChatModel) -> ChatModel:
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
            query_intent_id, intent_confidence = self._get_intent_id_and_confidence(chat_model_response, nlu_result)

            # Step 3: Retrieve the intent object
            query_intent = self._get_intent(query_intent_id)
            if query_intent is None:
                query_intent = self._get_fallback_intent()
            
            chat_model_response.nlu = {
                "entities": nlu_result.get("entities"),
                "intent": nlu_result.get("intent"),
            }

            # if query_intent is not the same as active intent, fetch active intent as well
            active_intent_id = chat_model_response.intent.get("id")
            if active_intent_id and query_intent_id != active_intent_id:
                active_intent = self._get_intent(chat_model_response.intent["id"])
            else:
                active_intent = query_intent

            # Step 4: Process the intent
            chat_model_response, active_intent = self._process_intent(query_intent, active_intent, chat_model_response, context, nlu_result)
            chat_model_response.intent = {
                "id": active_intent.intent_id
            }

            # Step 5: Handle API trigger if the intent is complete
            if chat_model_response.complete:
                chat_model_response = await self._handle_api_trigger(active_intent, chat_model_response, context)

            logger.info(f"Processed input: {chat_model_response.input_text}", extra=chat_model_response.to_json())
            return chat_model_response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    def _get_intent_id_and_confidence(self, chat_model: ChatModel, nlu_result: Dict) -> Tuple[str, float]:
        """
        Determine the intent ID and confidence based on the request input.
        """
        input_text = chat_model.input_text
        if input_text.startswith("/"):
            intent_id = input_text.split("/")[1]
            confidence = 1.0
        else:
            predicted = nlu_result["intent"]
            if predicted["confidence"] < self.confidence_threshold:
                return self.fallback_intent_id, 1.0
            else:
                return predicted["intent"], predicted["confidence"]
        return intent_id, confidence

    def _get_intent(self, intent_id: str) -> Optional[IntentModel]:
        """
        Retrieve the intent object by its ID.
        """
        return self.intents.get(intent_id)

    def _get_fallback_intent(self) -> IntentModel:
        """
        Retrieve the fallback intent.
        """
        return self.intents[self.fallback_intent_id]

    def _process_intent(self, query_intent: IntentModel, active_intent: IntentModel, 
                       chat_model_response: ChatModel, context: Dict, nlu_result: Dict) -> (ChatModel, IntentModel):
        """
        Process the intent and update the result model with extracted parameters and other details.
        """
        # cancel intent should cancel active intent and reset chat model
        if query_intent.intent_id == "cancel":
            active_intent = query_intent
            chat_model_response.complete = True
            chat_model_response.parameters = []
            chat_model_response.extracted_parameters = {}
            chat_model_response.missing_parameters = {}
            chat_model_response.current_node = None
            return chat_model_response, active_intent

        parameters = active_intent.parameters

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

    def _handle_missing_parameters(self, parameters: List[ParameterModel], chat_model_response: ChatModel) -> ChatModel:
        """
        Handle missing parameters in the result model.

        :param parameters: List of parameters from the intent.
        :param chat_model_response: The ChatModel instance to be updated.
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

    async def _handle_api_trigger(self, intent: IntentModel, chat_model_response: ChatModel, context: Dict) -> ChatModel:
        """
        Handle API trigger if the intent requires it.
        """
        if intent.api_trigger and intent.api_details:
            try:
                result = await self._call_intent_api(intent, context)
                context["result"] = result
                template = Template(intent.speech_response, undefined=SilentUndefined, enable_async=True)
                chat_model_response.speech_response = split_sentence(await template.render_async(**context))
            except Exception as e:
                logger.warning(f"API call failed: {e}")
                chat_model_response.speech_response = ["Service is not available. Please try again later."]
        else:
            context["result"] = {}
            template = Template(intent.speech_response, undefined=SilentUndefined, enable_async=True)
            chat_model_response.speech_response = split_sentence(await template.render_async(**context))

        return chat_model_response

    async def _call_intent_api(self, intent: IntentModel, context: Dict):
        """
        Call the API associated with the intent.
        """
        api_details = intent.api_details
        headers = api_details.get_headers()
        url_template = Template(api_details.url, undefined=SilentUndefined)
        rendered_url = url_template.render(**context)

        if api_details.is_json:
            request_template = Template(api_details.json_data, undefined=SilentUndefined)
            parameters = json.loads(request_template.render(**context))
        else:
            parameters = context.get("parameters", {})

        return await call_api(rendered_url, api_details.request_type, headers, parameters, api_details.is_json)
