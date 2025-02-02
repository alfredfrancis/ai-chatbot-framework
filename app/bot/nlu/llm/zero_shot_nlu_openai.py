import logging
from typing import Any, Dict, List, Optional
from app.bot.nlu.pipeline import NLUComponent
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class ZeroShotNLUOpenAI(NLUComponent):
    """
    Zero-shot NLU component using OpenAI compactible language model api to extract intents and entities.
    """

    PROMPT_TEMPLATE_NAME = "ZERO_SHOT_LEARNING_PROMPT.md"

    def __init__(
        self,
        intents: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Args:
            intents (Optional[List[str]]): List of intents to recognize.
            entities (Optional[List[str]]): List of entities to extract.
            **kwargs: Additional arguments for OpenAI configuration.
        """
        self.intents = intents or []
        self.entities = entities or []

        # Initialize the OpenAI LLM
        self.llm = ChatOpenAI(
            base_url=kwargs.get("base_url", "http://127.0.0.1:11434/v1"),
            api_key=kwargs.get("api_key", "not-need-for-local-models"),
            model_name=kwargs.get("model_name", "not-need-for-local-models"),
            temperature=kwargs.get("temperature", 0),
            extra_body={"max_tokens": kwargs.get("max_tokens", 4096)},
        )

        # Load and render the prompt template
        env = Environment(loader=FileSystemLoader("app/bot/nlu/llm/prompts"))
        template = env.get_template(self.PROMPT_TEMPLATE_NAME)
        system_prompt = template.render(
            {"intents": self.intents, "entities": self.entities}
        )

        # Define the prompt template
        prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{text}"),
            ]
        )

        # Define the processing chain
        self.chain = prompt_template | self.llm | JsonOutputParser()

    def train(self, training_data: List[Dict[str, Any]], model_path: str) -> None:
        """
        Placeholder for training functionality. Not implemented for zero-shot learning.
        """
        pass

    def load(self, model_path: str) -> bool:
        """
        Placeholder for loading a pre-trained model. Not implemented for zero-shot learning.
        """
        return True

    def process(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a message and extract intents and entities using the OpenAI model.

        Args:
            message (Dict[str, Any]): The input message containing the text to process.

        Returns:
            Dict[str, Any]: The processed message with extracted intents and entities.
        """
        if not message.get("text"):
            logger.warning("Message does not contain 'text' key. Skipping processing.")
            return message

        try:
            result = self.chain.invoke({"text": message.get("text")})

            # Extract intent
            intent_value = result.get("intent")
            if intent_value:
                intent = {
                    "intent": intent_value,
                    "confidence": 1.0,  # Zero-shot models don't provide confidence scores
                }
                message["intent"] = intent
                message["intent_ranking"] = [intent]  # Single intent in ranking
            else:
                message["intent"] = {"intent": None, "confidence": 0.0}

            # Extract and filter entities
            entities = result.get("entities", {})
            message["entities"] = {k: v for k, v in entities.items() if v is not None}

        except Exception as e:
            logger.error(f"Error processing message with LLM: {e}", exc_info=True)
            message["intent"] = {"intent": None, "confidence": 0.0}
            message["intent_ranking"] = []
            message["entities"] = {}

        return message
