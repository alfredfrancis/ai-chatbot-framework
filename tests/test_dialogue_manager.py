import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.bot.dialogue_manager.models import (
    IntentModel,
    ParameterModel,
    ApiDetailsModel,
    UserMessage,
)
from app.bot.memory import MemorySaver
from app.bot.memory.models import State
from app.bot.nlu.pipeline import NLUPipeline


@pytest.fixture
def mock_nlu_pipeline():
    pipeline = Mock(spec=NLUPipeline)
    pipeline.process.return_value = {
        "intent": {"intent": "greet", "confidence": 0.95},
        "entities": {},
    }
    return pipeline


@pytest.fixture
def mock_memory_saver():
    memory_saver = Mock(spec=MemorySaver)
    memory_saver.get.return_value = None
    memory_saver.init_state.return_value = State(
        thread_id="user1",
        user_message=UserMessage(text="", context={}, thread_id="user1"),
        complete=False,
        parameters=[],
        extracted_parameters={},
        missing_parameters=[],
        current_node="",
        intent={},
    )
    return memory_saver


@pytest.fixture
def sample_intents():
    greet_intent = IntentModel(
        name="Greeting",
        intent_id="greet",
        parameters=[],
        speech_response="Hello!",
        api_trigger=False,
        api_details=None,
    )

    order_pizza_intent = IntentModel(
        name="Order Pizza",
        intent_id="order_pizza",
        parameters=[
            ParameterModel(
                name="size",
                type="pizza_size",
                required=True,
                prompt="What size pizza would you like?",
            ),
            ParameterModel(
                name="toppings",
                type="pizza_topping",
                required=True,
                prompt="What toppings would you like?",
            ),
        ],
        speech_response="Your {{parameters.size}} pizza with {{parameters.toppings}} will be ready soon!",
        api_trigger=True,
        api_details=ApiDetailsModel(
            url="http://pizza-api/order",
            request_type="POST",
            headers=[{"headerKey": "Content-Type", "headerValue": "application/json"}],
            is_json=True,
            json_data='{"size": "{{parameters.size}}", "toppings": "{{parameters.toppings}}"}',
        ),
    )

    fallback_intent = IntentModel(
        name="Fallback",
        intent_id="fallback",
        parameters=[],
        speech_response="I'm not sure I understand.",
        api_trigger=False,
        api_details=None,
    )

    cancel_intent = IntentModel(
        name="Cancel",
        intent_id="cancel",
        parameters=[],
        speech_response="Operation cancelled.",
        api_trigger=False,
        api_details=None,
    )

    return [greet_intent, order_pizza_intent, fallback_intent, cancel_intent]


@pytest.fixture
def dialogue_manager(mock_nlu_pipeline, mock_memory_saver, sample_intents):
    return DialogueManager(
        intents=sample_intents,
        nlu_pipeline=mock_nlu_pipeline,
        fallback_intent_id="fallback",
        intent_confidence_threshold=0.90,
        memory_saver=mock_memory_saver,
    )


class TestDialogueManager:
    @pytest.mark.asyncio
    async def test_process_simple_intent(self, dialogue_manager, mock_memory_saver):
        message = UserMessage(text="hello", context={}, thread_id="user1")

        current_state = await dialogue_manager.process(message)

        # Verify state was initialized and saved
        mock_memory_saver.init_state.assert_called_once_with("user1")
        mock_memory_saver.save.assert_called_once()

        assert current_state.complete is True
        assert current_state.intent["id"] == "greet"
        assert current_state.nlu["intent"]["intent"] == "greet"

    @pytest.mark.asyncio
    async def test_process_intent_with_parameters(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }

        message = UserMessage(
            text="I want a large pizza", context={}, thread_id="user1"
        )

        current_state = await dialogue_manager.process(message)

        assert current_state.complete is False
        assert current_state.current_node == "toppings"
        assert "size" in current_state.extracted_parameters
        assert current_state.extracted_parameters["size"] == "large"
        assert "toppings" in current_state.missing_parameters

    @pytest.mark.asyncio
    async def test_fallback_intent_low_confidence(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "greet", "confidence": 0.85},
            "entities": {},
        }

        message = UserMessage(text="gibberish text", context={}, thread_id="user1")

        current_state = await dialogue_manager.process(message)
        assert current_state.complete is True
        assert current_state.intent["id"] == "fallback"
        assert current_state.nlu["intent"]["intent"] == "greet"

    @pytest.mark.asyncio
    async def test_cancel_active_intent(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        # First start an intent with parameters
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }

        # Setup initial state with an active order_pizza intent
        initial_state = State(
            thread_id="user1",
            user_message=UserMessage(
                text="I want a large pizza", context={}, thread_id="user1"
            ),
            complete=False,
            parameters=[{"name": "size", "type": "pizza_size", "required": True}],
            extracted_parameters={"size": "large"},
            missing_parameters=["toppings"],
            current_node="toppings",
            intent={"id": "order_pizza"},
        )
        initial_state.nlu = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }
        mock_memory_saver.get.return_value = initial_state

        # Then cancel it
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "cancel", "confidence": 1.0},
            "entities": {},
        }

        message = UserMessage(text="/cancel", context={}, thread_id="user1")

        current_state = await dialogue_manager.process(message)

        assert current_state.complete is True
        assert current_state.intent["id"] == "cancel"
        assert len(current_state.parameters) == 0
        assert current_state.current_node is None

    @pytest.mark.asyncio
    async def test_state_persistence(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        # Setup initial state
        initial_state = State(
            thread_id="user1",
            user_message=UserMessage(
                text="I want a pizza", context={}, thread_id="user1"
            ),
            complete=False,
            parameters=[{"name": "size", "type": "pizza_size", "required": True}],
            extracted_parameters={},
            missing_parameters=["size"],
            current_node="size",
            intent={"id": "order_pizza"},
        )
        initial_state.nlu = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {},
        }
        mock_memory_saver.get.return_value = initial_state

        # Send size parameter
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }

        message = UserMessage(text="large", context={}, thread_id="user1")

        current_state = await dialogue_manager.process(message)

        assert current_state.thread_id == "user1"
        assert current_state.intent["id"] == "order_pizza"
        assert current_state.extracted_parameters["size"] == "large"
        assert current_state.current_node == "toppings"
        assert not current_state.complete

    @pytest.mark.asyncio
    async def test_api_trigger(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        # Setup initial state with size parameter
        initial_state = State(
            thread_id="user1",
            user_message=UserMessage(
                text="I want a large pizza", context={}, thread_id="user1"
            ),
            complete=False,
            parameters=[
                {"name": "size", "type": "pizza_size", "required": True},
                {"name": "toppings", "type": "pizza_topping", "required": True},
            ],
            extracted_parameters={"size": "large"},
            missing_parameters=["toppings"],
            current_node="toppings",
            intent={"id": "order_pizza"},
        )
        initial_state.nlu = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }
        mock_memory_saver.get.return_value = initial_state

        # Mock API call
        with patch(
            "app.bot.dialogue_manager.dialogue_manager.call_api", new_callable=AsyncMock
        ) as mock_call_api:
            mock_call_api.return_value = {"status": "success"}

            # Send toppings parameter
            mock_nlu_pipeline.process.return_value = {
                "intent": {"intent": "order_pizza", "confidence": 0.95},
                "entities": {"pizza_topping": "pepperoni"},
            }

            message = UserMessage(text="pepperoni", context={}, thread_id="user1")

            current_state = await dialogue_manager.process(message)

            assert mock_call_api.called
            assert current_state.complete is True
            assert current_state.extracted_parameters["size"] == "large"
            assert current_state.extracted_parameters["toppings"] == "pepperoni"

    @pytest.mark.asyncio
    async def test_process_intent_with_missing_parameters(
        self, dialogue_manager, mock_nlu_pipeline, mock_memory_saver
    ):
        # handle missing size parameter

        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {},
        }

        message = UserMessage(text="I want a pizza", context={}, thread_id="user2")

        current_state = await dialogue_manager.process(message)

        assert current_state.bot_message == [
            {
                "text": "What size pizza would you like?",
            }
        ]

        assert current_state.complete is False
        assert current_state.intent["id"] == "order_pizza"
        assert current_state.current_node == "size"
        assert current_state.missing_parameters == ["size", "toppings"]
        assert current_state.extracted_parameters == {}

        # handle missing toppings parameter

        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "random_intent", "confidence": 0.40},
            "entities": {"pizza_size": "large"},
        }

        message = UserMessage(text="large", context={}, thread_id="user2")

        current_state = await dialogue_manager.process(message)

        assert current_state.bot_message == [
            {
                "text": "What toppings would you like?",
            }
        ]

        assert current_state.complete is False
        assert current_state.intent["id"] == "order_pizza"
        assert current_state.current_node == "toppings"
        assert current_state.missing_parameters == ["toppings"]
        assert current_state.extracted_parameters == {"size": "large"}

        # handle final response

        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "random_intent", "confidence": 0.40},
            "entities": {"pizza_topping": "pepperoni"},
        }

        message = UserMessage(text="pepperoni", context={}, thread_id="user2")

        with patch(
            "app.bot.dialogue_manager.dialogue_manager.call_api", new_callable=AsyncMock
        ) as mock_call_api:
            mock_call_api.return_value = {"status": "success"}

            current_state = await dialogue_manager.process(message)

            assert mock_call_api.called

            assert current_state.bot_message == [
                {
                    "text": "Your large pizza with pepperoni will be ready soon!",
                }
            ]

            assert current_state.complete is True
            assert current_state.intent["id"] == "order_pizza"
            assert current_state.extracted_parameters["size"] == "large"
            assert current_state.extracted_parameters["toppings"] == "pepperoni"
            assert current_state.missing_parameters == []
