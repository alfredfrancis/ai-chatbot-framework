import json
import logging
from typing import Dict, List, Optional, Tuple
from jinja2 import Template
from app.admin.bots.store import get_bot
from app.admin.intents.store import list_intents
from app.bot.memory.models import State
from app.bot.nlu.pipeline import NLUPipeline
from app.bot.nlu.featurizers import SpacyFeaturizer
from app.bot.nlu.intent_classifiers import SklearnIntentClassifier
from app.bot.nlu.entity_extractors import CRFEntityExtractor
from app.bot.dialogue_manager.utils import SilentUndefined, split_sentence
from app.admin.entities.store import list_synonyms
from app.bot.dialogue_manager.models import (
    ChatModel,
    IntentModel,
    ParameterModel,
    UserMessage,
)
from app.bot.dialogue_manager.http_client import call_api
from app.config import app_config
from app.bot.memory import MemorySaver, MemorySaverInMemory

logger = logging.getLogger("dialogue_manager")


class DialogueManager:
    def __init__(
        self,
        memory_saver: MemorySaver,
        intents: List[IntentModel],
        nlu_pipeline: NLUPipeline,
        fallback_intent_id: str,
        intent_confidence_threshold: float,
    ):
        self.memory_saver = memory_saver
        self.nlu_pipeline = nlu_pipeline
        self.intents = {
            intent.intent_id: intent for intent in intents
        }  # Map for faster lookup
        self.fallback_intent_id = fallback_intent_id
        self.confidence_threshold = intent_confidence_threshold

    @classmethod
    async def from_config(cls):
        """
        Initialize DialogueManager with all required dependencies
        """

        synonyms = await list_synonyms()

        # Initialize pipeline with components
        nlu_pipeline = NLUPipeline(
            [
                SpacyFeaturizer(app_config.SPACY_LANG_MODEL),
                SklearnIntentClassifier(),
                CRFEntityExtractor(synonyms),
            ]
        )

        # Load all intents and convert to domain models
        db_intents = await list_intents()
        intents = [IntentModel.from_db(intent) for intent in db_intents]

        # Get configuration
        fallback_intent_id = app_config.DEFAULT_FALLBACK_INTENT_NAME

        # Get bot configuration
        bot = await get_bot("default")
        confidence_threshold = bot.config.get("confidence_threshold", 0.90)

        memory_saver = MemorySaverInMemory()

        return cls(
            memory_saver,
            intents,
            nlu_pipeline,
            fallback_intent_id,
            confidence_threshold,
        )

    def update_model(self, models_dir):
        """
        Signal hook to be called after training is completed.
        Reloads ML models and synonyms.
        """
        # Load models
        self.nlu_pipeline.load(models_dir)
        logger.info("NLU Pipeline models updated")

    async def process(self, message: UserMessage) -> State:
        """
        Single entry point to process the dialogue request.

        :param chat_model: The ChatModel instance containing the request data.
        :return: Processed ChatModel instance.
        """

        # get the current state of the conversation
        current_state = self.memory_saver.get(message.thread_id)

        # if there is no current state, create a new one
        if not current_state:
            logger.debug(
                f"No current state found for thread_id: {message.thread_id}, creating new state"
            )
            current_state = self.memory_saver.init_state(
                thread_id=message.thread_id, user_message=message
            )
        else:
            current_state.update(message)

        try:
            # Step 1: Process through NLU pipeline
            nlu_result = self.nlu_pipeline.process(
                {"text": current_state.user_message.text}
            )

            # Step 2: Get intent ID and confidence
            query_intent_id, _ = self._get_intent_id_and_confidence(
                current_state, nlu_result
            )

            # Step 3: Retrieve the intent object
            query_intent = self._get_intent(query_intent_id)
            if query_intent is None:
                query_intent = self._get_fallback_intent()

            current_state.nlu = {
                "entities": nlu_result.get("entities"),
                "intent": nlu_result.get("intent"),
            }

            print(current_state.nlu)

            # if query_intent is not the same as active intent,
            # fetch active intent as well
            active_intent_id = current_state.get_active_intent_id()
            if active_intent_id and query_intent_id != active_intent_id:
                active_intent = self._get_intent(current_state.intent["id"])
            else:
                active_intent = query_intent

            # Step 4: Process the intent
            current_state, active_intent = self._process_intent(
                query_intent,
                active_intent,
                current_state,
            )
            current_state.intent = {"id": active_intent.intent_id}

            # Step 5: Handle API trigger if the intent is complete
            if current_state.complete:
                current_state = await self._handle_api_trigger(
                    active_intent, current_state
                )

            logger.debug(
                f"Processed input: {current_state.thread_id}",
                extra=current_state.to_dict(),
            )

            self.memory_saver.save(message.thread_id, current_state)

            print(current_state.to_dict())

            return current_state

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    def _get_intent_id_and_confidence(
        self, current_state: State, nlu_result: Dict
    ) -> Tuple[str, float]:
        """
        Determine the intent ID and confidence based on the request input.
        """
        input_text = current_state.user_message.text
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

    def _process_intent(
        self,
        query_intent: IntentModel,
        active_intent: IntentModel,
        current_state: State,
    ) -> Tuple[State, IntentModel]:
        """
        Process the intent and update the result model
        with extracted parameters and other details.
        """
        # cancel intent should cancel active intent and reset chat model
        if query_intent.intent_id == "cancel":
            active_intent = query_intent
            current_state.complete = True
            current_state.parameters = []
            current_state.extracted_parameters = {}
            current_state.missing_parameters = []
            current_state.current_node = None
            return current_state, active_intent

        parameters = active_intent.parameters

        if parameters:
            # Get entities from NLU pipeline result
            extracted_entities = current_state.nlu.get("entities", {})

            # Group entities by type
            entities_by_type = {}
            for entity_name, entity_value in extracted_entities.items():
                if entity_name not in entities_by_type:
                    entities_by_type[entity_name] = []
                entities_by_type[entity_name].append(entity_value)

            # populate parameters
            if len(current_state.parameters) == 0:
                for param in parameters:
                    current_state.parameters.append(
                        {
                            "name": param.name,
                            "type": param.type,
                            "required": param.required,
                        }
                    )

            # Match extracted entities with parameters based on type
            for param in parameters:
                # For free_text parameters being prompted
                if (
                    param.type == "free_text"
                    and current_state.current_node == param.name
                ):
                    current_state.extracted_parameters[param.name] = (
                        current_state.user_message.text
                    )
                    continue
                else:
                    # Get all entities of matching type
                    if param.type in entities_by_type and entities_by_type[param.type]:
                        # Take the next available entity of this type
                        current_state.extracted_parameters[param.name] = (
                            entities_by_type[param.type].pop(0)
                        )

            # Update context with extracted_parameters
            current_state.context["parameters"] = current_state.extracted_parameters

            # Handle missing parameters
            current_state = self._handle_missing_parameters(parameters, current_state)

        # Check if there are no missing parameters
        # to mark the intent as complete
        current_state.complete = not current_state.missing_parameters
        return current_state, active_intent

    def _handle_missing_parameters(
        self, parameters: List[ParameterModel], current_state: State
    ) -> State:
        """
        Handle missing parameters in the result model.

        :param parameters: List of parameters from the intent.
        :param chat_model_response: The ChatModel instance to be updated.
        :return: Updated ChatModel instance.
        """
        missing_parameters = []
        current_state.missing_parameters = []

        # clear current node
        current_state.current_node = None
        current_state.bot_message = []

        for parameter in parameters:
            if (
                parameter.required
                and parameter.name not in current_state.extracted_parameters
            ):
                current_state.missing_parameters.append(parameter.name)
                missing_parameters.append(parameter)

        if missing_parameters:
            current_node = missing_parameters[0]
            current_state.current_node = current_node.name
            current_state.bot_message = [
                {"text": msg} for msg in split_sentence(current_node.prompt)
            ]
        return current_state

    async def _handle_api_trigger(
        self, intent: IntentModel, current_state: State
    ) -> ChatModel:
        """
        Handle API trigger if the intent requires it.
        """
        if intent.api_trigger and intent.api_details:
            try:
                result = await self._call_intent_api(intent, current_state.context)
                current_state.context["result"] = result
                template = Template(
                    intent.speech_response,
                    undefined=SilentUndefined,
                    enable_async=True,
                )
                rendered_text = await template.render_async(**current_state.context)
                current_state.bot_message = [
                    {"text": msg} for msg in split_sentence(rendered_text)
                ]
            except Exception as e:
                logger.warning(f"API call failed: {e}")
                current_state.bot_message = [
                    {"text": "Service is not available. Please try again later."}
                ]
        else:
            current_state.context["result"] = {}
            template = Template(
                intent.speech_response,
                undefined=SilentUndefined,
                enable_async=True,
            )
            rendered_text = await template.render_async(**current_state.context)
            current_state.bot_message = [
                {"text": msg} for msg in split_sentence(rendered_text)
            ]

        return current_state

    async def _call_intent_api(self, intent: IntentModel, context: Dict):
        """
        Call the API associated with the intent.
        """
        api_details = intent.api_details
        headers = api_details.get_headers()
        url_template = Template(api_details.url, undefined=SilentUndefined)
        rendered_url = url_template.render(**context)

        if api_details.is_json:
            request_template = Template(
                api_details.json_data, undefined=SilentUndefined
            )
            parameters = json.loads(request_template.render(**context))
        else:
            parameters = context.get("parameters", {})

        return await call_api(
            rendered_url,
            api_details.request_type,
            headers,
            parameters,
            api_details.is_json,
        )
