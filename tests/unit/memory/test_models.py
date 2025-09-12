import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock
from app.bot.memory.models import State
from app.bot.dialogue_manager.models import UserMessage


class TestState:
    @pytest.fixture
    def sample_user_message(self):
        """Fixture to create a sample UserMessage."""
        return UserMessage(
            thread_id="thread_123",
            text="Hello, I want to book a flight",
            context={"user_id": "user123", "session_id": "session456"},
        )

    @pytest.fixture
    def sample_state(self, sample_user_message):
        """Fixture to create a sample State object."""
        return State(
            thread_id="thread_123",
            user_message=sample_user_message,
            bot_message=[{"text": "I'd be happy to help you book a flight!"}],
            context={"user_id": "user123", "session_id": "session456"},
            intent={"name": "book_flight", "confidence": 0.95},
            parameters=[
                {"name": "destination", "value": "New York", "required": True},
                {"name": "departure_date", "required": True},
            ],
            extracted_parameters={"destination": "New York"},
            missing_parameters=["departure_date"],
            complete=False,
            current_node="collect_departure_date",
        )

    def test_init_minimal(self):
        """Test State initialization with minimal parameters."""
        thread_id = "test_thread"
        state = State(thread_id=thread_id)

        assert state.thread_id == thread_id
        assert state.user_message is None
        assert state.bot_message is None
        assert state.context == {}
        assert state.intent == {}
        assert state.parameters == []
        assert state.extracted_parameters == {}
        assert state.missing_parameters == []
        assert state.complete is False
        assert state.current_node == ""
        assert isinstance(state.date, datetime)

    def test_init_full(self, sample_user_message):
        """Test State initialization with all parameters."""
        thread_id = "thread_123"
        custom_date = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

        state = State(
            thread_id=thread_id,
            user_message=sample_user_message,
            bot_message=[{"text": "Hello!"}],
            context={"key": "value"},
            intent={"name": "test_intent"},
            parameters=[{"name": "param1"}],
            extracted_parameters={"param1": "value1"},
            missing_parameters=["param2"],
            complete=True,
            current_node="test_node",
            date=custom_date,
        )

        assert state.thread_id == thread_id
        assert state.user_message == sample_user_message
        assert state.bot_message == [{"text": "Hello!"}]
        assert state.context == {"key": "value"}
        assert state.intent == {"name": "test_intent"}
        assert state.parameters == [{"name": "param1"}]
        assert state.extracted_parameters == {"param1": "value1"}
        assert state.missing_parameters == ["param2"]
        assert state.complete is True
        assert state.current_node == "test_node"
        assert state.date == custom_date

    def test_to_dict(self, sample_state):
        """Test converting State to dictionary."""
        state_dict = sample_state.to_dict()

        assert isinstance(state_dict, dict)
        assert state_dict["thread_id"] == sample_state.thread_id
        assert state_dict["context"] == sample_state.context
        assert state_dict["intent"] == sample_state.intent
        assert state_dict["parameters"] == sample_state.parameters
        assert state_dict["extracted_parameters"] == sample_state.extracted_parameters
        assert state_dict["missing_parameters"] == sample_state.missing_parameters
        assert state_dict["complete"] == sample_state.complete
        assert state_dict["current_node"] == sample_state.current_node
        assert "date" in state_dict
        assert "user_message" in state_dict
        assert "bot_message" in state_dict
        assert "nlu" in state_dict

    def test_from_dict_minimal(self):
        """Test creating State from minimal dictionary."""
        state_dict = {
            "thread_id": "thread_123",
            "context": {},
            "intent": {},
            "parameters": [],
            "extracted_parameters": {},
            "missing_parameters": [],
            "complete": False,
            "current_node": "",
        }

        state = State.from_dict(state_dict)

        assert isinstance(state, State)
        assert state.thread_id == "thread_123"
        assert state.context == {}
        assert state.intent == {}
        assert state.parameters == []
        assert state.extracted_parameters == {}
        assert state.missing_parameters == []
        assert state.complete is False
        assert state.current_node == ""

    def test_from_dict_full(self, sample_user_message):
        """Test creating State from full dictionary."""
        state_dict = {
            "thread_id": "thread_123",
            "user_message": sample_user_message.to_dict(),
            "bot_message": [{"text": "Response"}],
            "nlu": {"tokens": ["hello"]},
            "context": {"user_id": "123"},
            "intent": {"name": "greet", "confidence": 0.9},
            "parameters": [{"name": "location"}],
            "extracted_parameters": {"location": "NYC"},
            "missing_parameters": ["date"],
            "complete": True,
            "current_node": "confirmation",
            "date": datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC),
        }

        state = State.from_dict(state_dict)

        assert isinstance(state, State)
        assert state.thread_id == "thread_123"
        assert state.context == {"user_id": "123"}
        assert state.intent == {"name": "greet", "confidence": 0.9}
        assert state.parameters == [{"name": "location"}]
        assert state.extracted_parameters == {"location": "NYC"}
        assert state.missing_parameters == ["date"]
        assert state.complete is True
        assert state.current_node == "confirmation"

    def test_update_incomplete_state(self, sample_user_message):
        """Test updating an incomplete state."""
        state = State(thread_id="thread_123", complete=False)
        original_date = state.date

        # Wait a bit to ensure date difference
        import time

        time.sleep(0.001)

        state.update(sample_user_message)

        assert state.user_message == sample_user_message
        assert state.context == sample_user_message.context
        assert state.date > original_date  # Date should be updated

    def test_update_complete_state(self, sample_user_message):
        """Test updating a complete state (should reset completion status)."""
        state = State(
            thread_id="thread_123",
            complete=True,
            intent={"name": "old_intent"},
            parameters=[{"name": "old_param"}],
            extracted_parameters={"old": "value"},
            missing_parameters=["old_missing"],
            current_node="old_node",
            bot_message=[{"text": "old message"}],
        )

        state.update(sample_user_message)

        # Complete state should be reset
        assert state.complete is False
        assert state.intent is None
        assert state.parameters == []
        assert state.extracted_parameters == {}
        assert state.missing_parameters == []
        assert state.current_node is None
        assert state.bot_message == []
        assert state.user_message == sample_user_message
        assert state.context == sample_user_message.context

    def test_get_active_intent_id_with_intent(self):
        """Test getting active intent ID when intent exists."""
        state = State(thread_id="thread_123")
        state.intent = {"id": "intent_123", "name": "test_intent"}

        active_intent_id = state.get_active_intent_id()

        assert active_intent_id == "intent_123"

    def test_get_active_intent_id_without_intent(self):
        """Test getting active intent ID when no intent exists."""
        state = State(thread_id="thread_123")

        active_intent_id = state.get_active_intent_id()

        assert active_intent_id is None

    def test_get_active_intent_id_empty_intent(self):
        """Test getting active intent ID when intent is empty."""
        state = State(thread_id="thread_123")
        state.intent = {}

        active_intent_id = state.get_active_intent_id()

        assert active_intent_id is None

    def test_date_auto_generation(self):
        """Test that date is automatically generated if not provided."""
        before_creation = datetime.now(UTC)
        state = State(thread_id="thread_123")
        after_creation = datetime.now(UTC)

        assert before_creation <= state.date <= after_creation

    def test_nlu_initialization(self):
        """Test that NLU is initialized as empty dict."""
        state = State(thread_id="thread_123")

        assert state.nlu == {}

    def test_context_initialization(self):
        """Test context initialization."""
        # Test with None
        state1 = State(thread_id="thread_123", context=None)
        assert state1.context == {}

        # Test with provided context
        context = {"key": "value"}
        state2 = State(thread_id="thread_123", context=context)
        assert state2.context == context

    def test_parameters_initialization(self):
        """Test parameters initialization."""
        # Test with None
        state1 = State(thread_id="thread_123", parameters=None)
        assert state1.parameters == []

        # Test with provided parameters
        parameters = [{"name": "test"}]
        state2 = State(thread_id="thread_123", parameters=parameters)
        assert state2.parameters == parameters

    def test_extracted_parameters_initialization(self):
        """Test extracted_parameters initialization."""
        # Test with None
        state1 = State(thread_id="thread_123", extracted_parameters=None)
        assert state1.extracted_parameters == {}

        # Test with provided extracted_parameters
        extracted = {"key": "value"}
        state2 = State(thread_id="thread_123", extracted_parameters=extracted)
        assert state2.extracted_parameters == extracted

    def test_missing_parameters_initialization(self):
        """Test missing_parameters initialization."""
        # Test with None
        state1 = State(thread_id="thread_123", missing_parameters=None)
        assert state1.missing_parameters == []

        # Test with provided missing_parameters
        missing = ["param1", "param2"]
        state2 = State(thread_id="thread_123", missing_parameters=missing)
        assert state2.missing_parameters == missing
