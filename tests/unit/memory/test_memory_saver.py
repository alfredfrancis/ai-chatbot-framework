import pytest
from app.bot.memory import MemorySaverInMemory
from app.bot.memory.models import State
from app.bot.dialogue_manager.models import UserMessage


class TestMemorySaverInMemory:
    @pytest.fixture
    def memory_saver(self):
        """Fixture to create a fresh MemorySaverInMemory instance."""
        return MemorySaverInMemory()

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

    @pytest.mark.asyncio
    async def test_init(self, memory_saver):
        """Test MemorySaverInMemory initialization."""
        assert memory_saver.memory == {}
        assert hasattr(memory_saver, "save")
        assert hasattr(memory_saver, "get")
        assert hasattr(memory_saver, "get_all")

    @pytest.mark.asyncio
    async def test_init_state(self, memory_saver):
        """Test init_state method."""
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
    async def test_save_new_thread(self, memory_saver, sample_state):
        """Test saving state for a new thread."""
        await memory_saver.save(sample_state.thread_id, sample_state)

        assert sample_state.thread_id in memory_saver.memory
        assert len(memory_saver.memory[sample_state.thread_id]) == 1
        assert memory_saver.memory[sample_state.thread_id][0] == sample_state

    @pytest.mark.asyncio
    async def test_save_existing_thread(self, memory_saver, sample_state):
        """Test saving multiple states for the same thread."""
        # Save first state
        await memory_saver.save(sample_state.thread_id, sample_state)

        # Create and save second state
        second_state = State(
            thread_id=sample_state.thread_id,
            user_message=UserMessage(
                thread_id=sample_state.thread_id,
                text="How are you?",
                context={"user_id": "123"},
            ),
            context={"user_id": "123"},
        )
        await memory_saver.save(sample_state.thread_id, second_state)

        assert len(memory_saver.memory[sample_state.thread_id]) == 2
        assert memory_saver.memory[sample_state.thread_id][0] == sample_state
        assert memory_saver.memory[sample_state.thread_id][1] == second_state

    @pytest.mark.asyncio
    async def test_get_existing_thread(self, memory_saver, sample_state):
        """Test getting the latest state for an existing thread."""
        await memory_saver.save(sample_state.thread_id, sample_state)

        retrieved_state = await memory_saver.get(sample_state.thread_id)

        assert retrieved_state == sample_state
        assert retrieved_state.thread_id == sample_state.thread_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_thread(self, memory_saver):
        """Test getting state for a nonexistent thread."""
        retrieved_state = await memory_saver.get("nonexistent_thread")

        assert retrieved_state is None

    @pytest.mark.asyncio
    async def test_get_all_existing_thread(self, memory_saver, sample_state):
        """Test getting all states for an existing thread."""
        await memory_saver.save(sample_state.thread_id, sample_state)

        # Add another state
        second_state = State(thread_id=sample_state.thread_id)
        await memory_saver.save(sample_state.thread_id, second_state)

        all_states = await memory_saver.get_all(sample_state.thread_id)

        assert len(all_states) == 2
        assert all_states[0] == sample_state
        assert all_states[1] == second_state

    @pytest.mark.asyncio
    async def test_get_all_nonexistent_thread(self, memory_saver):
        """Test getting all states for a nonexistent thread."""
        all_states = await memory_saver.get_all("nonexistent_thread")

        assert all_states == []

    @pytest.mark.asyncio
    async def test_multiple_threads_isolation(self, memory_saver, sample_state):
        """Test that different threads maintain separate state."""
        # Create states for different threads
        thread1_state = sample_state
        thread2_state = State(
            thread_id="thread_456",
            user_message=UserMessage(
                thread_id="thread_456", text="Goodbye", context={"user_id": "456"}
            ),
        )

        await memory_saver.save(thread1_state.thread_id, thread1_state)
        await memory_saver.save(thread2_state.thread_id, thread2_state)

        # Verify isolation
        thread1_retrieved = await memory_saver.get(thread1_state.thread_id)
        thread2_retrieved = await memory_saver.get(thread2_state.thread_id)

        assert thread1_retrieved == thread1_state
        assert thread2_retrieved == thread2_state
        assert thread1_retrieved != thread2_retrieved

        # Verify get_all isolation
        thread1_all = await memory_saver.get_all(thread1_state.thread_id)
        thread2_all = await memory_saver.get_all(thread2_state.thread_id)

        assert len(thread1_all) == 1
        assert len(thread2_all) == 1
        assert thread1_all[0] == thread1_state
        assert thread2_all[0] == thread2_state
