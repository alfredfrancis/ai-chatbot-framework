
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.dialogue_manager.models import UserMessage
from app.bot.memory.memory_saver_mongo import MemorySaverMongo
from app.bot.memory.models import State


@pytest.fixture
def mock_collection():
    return Mock()


@pytest.fixture
def memory_saver(mock_collection):
    client = Mock()
    client.get_database.return_value.get_collection.return_value = (
        mock_collection
    )
    return MemorySaverMongo(client)


@pytest.fixture
def sample_state():
    return State(
        thread_id="thread-1",
        user_message=UserMessage(
            text="hello",
            context={},
            thread_id="thread-1",
        ),
        context={"source": "test"},
        intent={"id": "greet"},
        complete=True,
    )


@pytest.mark.asyncio
async def test_save_inserts_serialized_state(
    memory_saver, mock_collection, sample_state
):
    mock_collection.insert_one = AsyncMock()

    await memory_saver.save("thread-1", sample_state)

    mock_collection.insert_one.assert_awaited_once_with(
        sample_state.to_dict()
    )


@pytest.mark.asyncio
async def test_get_returns_state_when_found(
    memory_saver, mock_collection, sample_state
):
    mock_collection.find_one = AsyncMock(
        return_value=sample_state.to_dict()
    )

    result = await memory_saver.get("thread-1")

    assert isinstance(result, State)
    assert result.thread_id == "thread-1"
    assert result.context == {"source": "test"}
    mock_collection.find_one.assert_awaited_once_with(
        {"thread_id": "thread-1"},
        {
            "_id": 0,
            "nlu": 0,
            "date": 0,
            "user_message": 0,
            "bot_message": 0,
        },
        sort=[("$natural", -1)],
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found(
    memory_saver, mock_collection
):
    mock_collection.find_one = AsyncMock(return_value=None)

    result = await memory_saver.get("unknown-thread")

    assert result is None


@pytest.mark.asyncio
async def test_get_all_returns_states(
    memory_saver, mock_collection, sample_state
):
    cursor = Mock()
    cursor.to_list = AsyncMock(
        return_value=[
            sample_state.to_dict(),
            sample_state.to_dict(),
        ]
    )
    mock_collection.find.return_value = cursor

    results = await memory_saver.get_all("thread-1")

    assert len(results) == 2
    assert all(isinstance(state, State) for state in results)
    assert all(state.thread_id == "thread-1" for state in results)
    mock_collection.find.assert_called_once_with(
        {"thread_id": "thread-1"},
        sort=[("$natural", -1)],
    )
    cursor.to_list.assert_awaited_once_with()

