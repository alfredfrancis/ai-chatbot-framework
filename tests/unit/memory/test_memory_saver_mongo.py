import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from motor.motor_asyncio import AsyncIOMotorClient
from app.bot.memory.memory_saver_mongo import MemorySaverMongo
from app.bot.memory.models import State
from app.bot.dialogue_manager.models import UserMessage


class TestMemorySaverMongo:
    @pytest.fixture
    def mock_client(self):
        """Fixture to create a mocked MongoDB client."""
        client = MagicMock(spec=AsyncIOMotorClient)
        db = MagicMock()
        collection = MagicMock()

        client.get_database.return_value = db
        db.get_collection.return_value = collection

        return client

    @pytest.fixture
    def memory_saver(self, mock_client):
        """Fixture to create a MemorySaverMongo instance with mocked client."""
        return MemorySaverMongo(mock_client)

    @pytest.fixture
    def sample_state(self):
        """Fixture to create a sample State object."""
        user_message = UserMessage(
            thread_id="thread_123", text="Hello", context={"user_id": "123"}
        )
        return State(
            thread_id="thread_123",
            user_message=user_message,
            bot_message=[{"text": "Hi there!"}],
            context={"user_id": "123"},
            intent={"name": "greet", "confidence": 0.9},
            parameters=[{"name": "location", "value": "New York"}],
            extracted_parameters={"location": "New York"},
            missing_parameters=[],
            complete=True,
            current_node="greet_node",
        )

    def test_init(self, mock_client):
        """Test MemorySaverMongo initialization."""
        saver = MemorySaverMongo(mock_client)

        assert saver.client == mock_client
        mock_client.get_database.assert_called_once_with("chatbot")
        mock_client.get_database.return_value.get_collection.assert_called_once_with(
            "state"
        )

    @pytest.mark.asyncio
    async def test_save(self, memory_saver, sample_state):
        """Test saving state to MongoDB."""
        # Mock the insert_one method
        memory_saver.collection.insert_one = AsyncMock()

        await memory_saver.save(sample_state.thread_id, sample_state)

        memory_saver.collection.insert_one.assert_called_once()
        call_args = memory_saver.collection.insert_one.call_args[0][0]

        # Verify the document structure
        assert call_args["thread_id"] == sample_state.thread_id
        assert "user_message" in call_args
        assert "bot_message" in call_args
        assert call_args["context"] == sample_state.context
        assert call_args["intent"] == sample_state.intent
        assert call_args["parameters"] == sample_state.parameters
        assert call_args["complete"] == sample_state.complete
        assert call_args["current_node"] == sample_state.current_node

    @pytest.mark.asyncio
    async def test_get_existing_state(self, memory_saver, sample_state):
        """Test getting existing state from MongoDB."""
        # Mock the find_one method to return state data
        mock_result = {
            "thread_id": sample_state.thread_id,
            "context": sample_state.context,
            "intent": sample_state.intent,
            "parameters": sample_state.parameters,
            "extracted_parameters": sample_state.extracted_parameters,
            "missing_parameters": sample_state.missing_parameters,
            "complete": sample_state.complete,
            "current_node": sample_state.current_node,
        }
        memory_saver.collection.find_one = AsyncMock(return_value=mock_result)

        result = await memory_saver.get(sample_state.thread_id)

        assert isinstance(result, State)
        assert result.thread_id == sample_state.thread_id
        assert result.context == sample_state.context
        assert result.intent == sample_state.intent
        assert result.parameters == sample_state.parameters
        assert result.complete == sample_state.complete
        assert result.current_node == sample_state.current_node

        # Verify the query parameters
        memory_saver.collection.find_one.assert_called_once()
        call_args = memory_saver.collection.find_one.call_args
        assert call_args[0][0] == {"thread_id": sample_state.thread_id}
        assert call_args[0][1] == {
            "_id": 0,
            "nlu": 0,
            "date": 0,
            "user_message": 0,
            "bot_message": 0,
        }
        assert call_args[1] == {"sort": [("$natural", -1)]}

    @pytest.mark.asyncio
    async def test_get_nonexistent_state(self, memory_saver):
        """Test getting state that doesn't exist in MongoDB."""
        memory_saver.collection.find_one = AsyncMock(return_value=None)

        result = await memory_saver.get("nonexistent_thread")

        assert result is None
        memory_saver.collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_states(self, memory_saver, sample_state):
        """Test getting all states for a thread from MongoDB."""
        mock_results = [
            {
                "thread_id": sample_state.thread_id,
                "context": sample_state.context,
                "intent": sample_state.intent,
                "parameters": sample_state.parameters,
                "extracted_parameters": sample_state.extracted_parameters,
                "missing_parameters": sample_state.missing_parameters,
                "complete": sample_state.complete,
                "current_node": sample_state.current_node,
            },
            {
                "thread_id": sample_state.thread_id,
                "context": {"user_id": "456"},
                "intent": {"name": "bye", "confidence": 0.8},
                "parameters": [],
                "extracted_parameters": {},
                "missing_parameters": [],
                "complete": False,
                "current_node": "bye_node",
            },
        ]

        # Mock the find method to return an async cursor
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=mock_results)
        memory_saver.collection.find = MagicMock(return_value=mock_cursor)

        results = await memory_saver.get_all(sample_state.thread_id)

        assert len(results) == 2
        assert all(isinstance(state, State) for state in results)
        assert results[0].thread_id == sample_state.thread_id
        assert results[1].thread_id == sample_state.thread_id

        # Verify the query
        memory_saver.collection.find.assert_called_once_with(
            {"thread_id": sample_state.thread_id}, sort=[("$natural", -1)]
        )

    @pytest.mark.asyncio
    async def test_get_all_empty_results(self, memory_saver):
        """Test getting all states when no states exist."""
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        memory_saver.collection.find = MagicMock(return_value=mock_cursor)

        results = await memory_saver.get_all("empty_thread")

        assert results == []
        memory_saver.collection.find.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_state(self, memory_saver):
        """Test init_state method (inherited from base class)."""
        thread_id = "test_thread"
        state = await memory_saver.init_state(thread_id)

        assert isinstance(state, State)
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

    @pytest.mark.asyncio
    async def test_database_error_handling(self, memory_saver, sample_state):
        """Test error handling for database operations."""
        # Test save error
        memory_saver.collection.insert_one = AsyncMock(
            side_effect=Exception("DB Error")
        )

        with pytest.raises(Exception, match="DB Error"):
            await memory_saver.save(sample_state.thread_id, sample_state)

        # Test get error
        memory_saver.collection.find_one = AsyncMock(side_effect=Exception("DB Error"))

        with pytest.raises(Exception, match="DB Error"):
            await memory_saver.get("thread_123")

        # Test get_all error
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(side_effect=Exception("DB Error"))
        memory_saver.collection.find = MagicMock(return_value=mock_cursor)

        with pytest.raises(Exception, match="DB Error"):
            await memory_saver.get_all("thread_123")
