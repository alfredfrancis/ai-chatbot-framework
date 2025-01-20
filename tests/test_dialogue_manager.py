import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.bot.dialogue_manager.models import (
    ChatModel,
    IntentModel,
    ParameterModel,
    ApiDetailsModel,
)
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
def dialogue_manager(mock_nlu_pipeline, sample_intents):
    return DialogueManager(
        intents=sample_intents,
        nlu_pipeline=mock_nlu_pipeline,
        fallback_intent_id="fallback",
        intent_confidence_threshold=0.90,
    )


class TestDialogueManager:
    @pytest.mark.asyncio
    async def test_process_simple_intent(self, dialogue_manager):
        chat_model = ChatModel(
            input_text="hello", context={}, complete=False, owner="user1"
        )

        result = await dialogue_manager.process(chat_model)

        assert result.complete is True
        assert result.speech_response == ["Hello!"]
        assert result.intent["id"] == "greet"

    @pytest.mark.asyncio
    async def test_process_intent_with_parameters(
        self, dialogue_manager, mock_nlu_pipeline
    ):
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }

        chat_model = ChatModel(
            input_text="I want a large pizza", context={}, complete=False, owner="user1"
        )

        result = await dialogue_manager.process(chat_model)

        assert result.complete is False
        assert result.current_node == "toppings"
        assert "size" in result.extracted_parameters
        assert result.extracted_parameters["size"] == "large"
        assert "toppings" in result.missing_parameters

    @pytest.mark.asyncio
    async def test_fallback_intent_low_confidence(
        self, dialogue_manager, mock_nlu_pipeline
    ):
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "greet", "confidence": 0.85},
            "entities": {},
        }

        chat_model = ChatModel(
            input_text="gibberish text", context={}, complete=False, owner="user1"
        )

        result = await dialogue_manager.process(chat_model)

        assert result.complete is True
        assert result.intent["id"] == "fallback"
        assert result.speech_response == ["I'm not sure I understand."]

    @pytest.mark.asyncio
    async def test_cancel_active_intent(self, dialogue_manager, mock_nlu_pipeline):
        # First start an intent with parameters
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "order_pizza", "confidence": 0.95},
            "entities": {"pizza_size": "large"},
        }

        chat_model = ChatModel(
            input_text="I want a large pizza", context={}, complete=False, owner="user1"
        )

        result = await dialogue_manager.process(chat_model)
        assert not result.complete

        # Then cancel it
        mock_nlu_pipeline.process.return_value = {
            "intent": {"intent": "cancel", "confidence": 1.0},
            "entities": {},
        }

        result.input_text = "/cancel"
        result = await dialogue_manager.process(result)

        assert result.complete is True
        assert result.intent["id"] == "cancel"
        assert len(result.parameters) == 0
        assert result.current_node is None

    @pytest.mark.asyncio
    async def test_free_text_parameter(self, dialogue_manager, mock_nlu_pipeline):
        # Setup an intent with a free text parameter
        chat_model = ChatModel(
            input_text="some text",
            context={},
            complete=False,
            current_node="free_text_param",
            owner="user1",
        )

        # Mock the intent to have a free text parameter
        dialogue_manager.intents["test_intent"] = IntentModel(
            name="Test Intent",
            intent_id="test_intent",
            parameters=[
                ParameterModel(
                    name="free_text_param",
                    type="free_text",
                    required=True,
                    prompt="Enter some text",
                )
            ],
            speech_response="You entered: {{parameters.free_text_param}}",
            api_trigger=False,
            api_details=None,
        )

        chat_model.intent = {"id": "test_intent"}

        result = await dialogue_manager.process(chat_model)

        assert "free_text_param" in result.extracted_parameters
        assert result.extracted_parameters["free_text_param"] == "some text"

    @pytest.mark.asyncio
    async def test_api_trigger(self, dialogue_manager, mock_nlu_pipeline):
        # Mock API call
        with patch(
            "app.bot.dialogue_manager.dialogue_manager.call_api", new_callable=AsyncMock
        ) as mock_call_api:
            mock_call_api.return_value = {"status": "success"}

            # Setup chat model with all required parameters
            chat_model = ChatModel(
                input_text="pepperoni",
                context={},
                complete=False,
                current_node="toppings",
                intent={"id": "order_pizza"},
                extracted_parameters={"size": "large"},
                owner="user1",
            )

            mock_nlu_pipeline.process.return_value = {
                "intent": {"intent": "order_pizza", "confidence": 0.95},
                "entities": {"pizza_topping": "pepperoni"},
            }

            result = await dialogue_manager.process(chat_model)

            assert result.complete is True
            assert mock_call_api.called
            assert (
                "Your large pizza with pepperoni will be ready soon!"
                in result.speech_response
            )

    @pytest.mark.asyncio
    async def test_update_model(self, dialogue_manager):
        models_dir = "path/to/models"
        dialogue_manager.update_model(models_dir)
        dialogue_manager.nlu_pipeline.load.assert_called_once_with(models_dir)
