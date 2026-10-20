"""Exercise intent loading, dispatch, the real MCP SDK and reply consumption."""

import asyncio
import json
from copy import deepcopy
from unittest.mock import Mock, AsyncMock, patch
from uuid import UUID

import httpx
import pytest

from app.admin.intents.schemas import Intent
from app.bot.dialogue_manager import web_search
from app.bot.dialogue_manager.dialogue_manager import DialogueManager
from app.bot.dialogue_manager.models import IntentModel, UserMessage, ApiDetailsModel
from app.bot.memory import MemorySaver
from app.bot.memory.models import State


class StoredMemory(MemorySaver):
    """Use the same serialized state contract as Mongo, without a database."""

    def __init__(self):
        self.states = {}

    async def get(self, thread_id):
        data = self.states.get(thread_id)
        return State.from_dict(deepcopy(data)) if data else None

    async def save(self, thread_id, state):
        self.states[thread_id] = deepcopy(state.to_dict())


@pytest.fixture
def manager():
    intents = [
        IntentModel.from_db(
            Intent(
                name=tool,
                intentId=tool,
                speechResponse="{% for page in result.results %}{{ page.title }}: {{ page.url }} {{ page.excerpts | join(' ') }}{% endfor %}",
                webSearch={"enabled": True, "tool": tool},
            )
        )
        for tool in ("web_search", "web_fetch")
    ]
    intents += [
        IntentModel(name=name, intent_id=name, speech_response="Ready")
        for name in ("fallback", "init_conversation", "cancel")
    ]
    nlu = Mock()
    nlu.process.return_value = {
        "intent": {"intent": "web_search", "confidence": 1},
        "entities": {},
    }
    return DialogueManager(StoredMemory(), intents, nlu, "fallback", 0.5)


@pytest.fixture
def wire(monkeypatch):
    """Keep the production SDK transport; inspect every actual HTTP request."""
    calls = []
    behavior = {"kind": "success", "sse": False}
    real_client = httpx.AsyncClient

    async def handler(request):
        assert str(request.url) == "https://search.parallel.ai/mcp"
        assert request.headers["user-agent"] == web_search.USER_AGENT
        assert "authorization" not in request.headers
        assert "x-api-key" not in request.headers
        data = json.loads(request.content)
        calls.append(data)
        method = data["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": data["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fixture", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [
                    {"name": name, "inputSchema": {"type": "object"}}
                    for name in ("web_search", "web_fetch")
                ]
            }
            if behavior["kind"] == "missing_tool":
                result = {"tools": []}
        else:
            assert method == "tools/call"
            assert UUID(data["params"]["arguments"]["session_id"])
            if behavior["kind"] == "hang":
                await asyncio.Event().wait()
            if behavior["kind"] == "http_error":
                return httpx.Response(503, text="temporarily unavailable")
            payload = {
                "results": [
                    {
                        "title": "Python <script>",
                        "url": "https://www.python.org/?a=1&b=2",
                        "excerpts": ["Current <b>documentation</b>"],
                    },
                    {"title": "Unsafe", "url": "javascript:alert(1)", "excerpts": []},
                ]
            }
            result = {
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "isError": False,
            }
            if behavior["kind"] != "legacy":
                result["structuredContent"] = payload
            if behavior["kind"] in ("tool_error", "quota"):
                result = {
                    "isError": True,
                    "content": [
                        {"type": "text", "text": "free anonymous quota exceeded"}
                    ],
                }
            if behavior["kind"] == "malformed":
                result = {"content": [{"type": "text", "text": "invalid json"}]}
        response = {"jsonrpc": "2.0", "id": data["id"], "result": result}
        if behavior["sse"]:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text="event: message\ndata: " + json.dumps(response) + "\n\n",
            )
        return httpx.Response(200, json=response)

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(web_search.httpx, "AsyncClient", factory)
    for name in ("PARALLEL_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(name, "ambient-credential-must-not-be-sent")
    return calls, behavior


async def converse(
    manager, text="Python documentation tutorials", thread="one", tool="web_search"
):
    manager.nlu_pipeline.process.return_value["intent"]["intent"] = tool
    return await manager.process(UserMessage(thread, text, {}))


def tool_calls(wire):
    return [call["params"] for call in wire[0] if call["method"] == "tools/call"]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy,sse", [(False, False), (True, False), (False, True)])
async def test_real_sdk_dispatch_and_escaped_reply(manager, wire, legacy, sse):
    wire[1].update(kind="legacy" if legacy else "success", sse=sse)
    state = await converse(manager)
    params = tool_calls(wire)[0]
    assert params["name"] == "web_search"
    assert params["arguments"]["objective"] == "Python documentation tutorials"
    assert params["arguments"]["search_queries"] == ["Python documentation tutorials"]
    assert state.complete
    text = state.bot_message[0]["text"]
    assert "Python &lt;script&gt;" in text
    assert "https://www.python.org/?a=1&amp;b=2" in text
    assert "Current &lt;b&gt;documentation&lt;/b&gt;" in text
    assert "Unsafe" not in text
    assert {"initialize", "tools/list", "tools/call"} <= {c["method"] for c in wire[0]}


@pytest.mark.asyncio
async def test_persisted_conversations_followups_fetch_and_reset(manager, wire):
    await converse(manager)
    await converse(manager, "https://www.python.org/", tool="web_fetch")
    await converse(manager, "Python language release notes")
    ids = [c["arguments"]["session_id"] for c in tool_calls(wire)]
    assert len(set(ids)) == 1
    assert tool_calls(wire)[1]["arguments"]["urls"] == ["https://www.python.org/"]
    assert ids[0] != "one"
    await manager.process(UserMessage("one", "/init_conversation", {}))
    await converse(manager)
    assert tool_calls(wire)[-1]["arguments"]["session_id"] != ids[0]


@pytest.mark.asyncio
async def test_concurrent_threads_keep_their_own_ids(manager, wire):
    await asyncio.gather(
        converse(manager, thread="alice"), converse(manager, thread="bob")
    )
    first_ids = {
        thread: manager.memory_saver.states[thread]["web_session_id"]
        for thread in ("alice", "bob")
    }
    assert first_ids["alice"] != first_ids["bob"]
    await asyncio.gather(
        converse(manager, thread="bob"), converse(manager, thread="alice")
    )
    assert [c["arguments"]["session_id"] for c in tool_calls(wire)].count(
        first_ids["alice"]
    ) == 2
    assert [c["arguments"]["session_id"] for c in tool_calls(wire)].count(
        first_ids["bob"]
    ) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["tool_error", "quota", "http_error", "malformed", "missing_tool"]
)
async def test_failure_is_graceful_and_retry_keeps_id(manager, wire, kind):
    wire[1]["kind"] = kind
    failed = await converse(manager)
    assert failed.bot_message == [
        {"text": "Service is not available. Please try again later."}
    ]
    old_id = failed.web_session_id
    wire[1]["kind"] = "success"
    passed = await converse(manager)
    assert passed.web_session_id == old_id
    assert "python.org" in passed.bot_message[0]["text"]


@pytest.mark.asyncio
async def test_timeout_and_cancellation(manager, wire, monkeypatch):
    wire[1]["kind"] = "hang"
    monkeypatch.setattr(web_search, "TIMEOUT_SECONDS", 0.1)
    timed_out = await converse(manager)
    assert timed_out.bot_message == [
        {"text": "Service is not available. Please try again later."}
    ]
    monkeypatch.setattr(web_search, "TIMEOUT_SECONDS", 30)
    started = len(tool_calls(wire))
    task = asyncio.create_task(converse(manager))
    async with asyncio.timeout(2):
        while len(tool_calls(wire)) == started:
            await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (
        tool_calls(wire)[0]["arguments"]["session_id"]
        == tool_calls(wire)[-1]["arguments"]["session_id"]
    )


@pytest.mark.asyncio
async def test_disabled_access_and_existing_rest_precedence(manager, wire, monkeypatch):
    intent = manager.intents["web_search"]
    intent.web_search.enabled = False
    await converse(manager)
    assert not wire[0]
    intent.web_search.enabled = True
    monkeypatch.setattr(
        "app.bot.dialogue_manager.dialogue_manager.app_config.WEB_SEARCH_ENABLED", False
    )
    await converse(manager)
    assert not wire[0]
    intent.api_trigger = True
    intent.api_details = ApiDetailsModel(
        "https://existing.example/api",
        "POST",
        [{"headerKey": "Authorization", "headerValue": "saved-key"}],
    )
    with patch(
        "app.bot.dialogue_manager.dialogue_manager.call_api", new_callable=AsyncMock
    ) as api:
        api.return_value = {"results": []}
        await converse(manager)
        assert api.call_args.args[0:3] == (
            "https://existing.example/api",
            "POST",
            {"Authorization": "saved-key"},
        )
    assert not wire[0]


@pytest.mark.asyncio
async def test_explicit_rest_failure_never_falls_back(manager, wire):
    intent = manager.intents["web_search"]
    intent.api_trigger = True
    intent.api_details = ApiDetailsModel("https://existing.example/api", "GET", [])
    from app.bot.dialogue_manager.http_client import APICallExcetion

    with patch(
        "app.bot.dialogue_manager.dialogue_manager.call_api",
        side_effect=APICallExcetion("failure"),
    ):
        state = await converse(manager)
    assert "Service is not available" in state.bot_message[0]["text"]
    assert not wire[0]


@pytest.mark.asyncio
async def test_query_template_and_invalid_fetch_url(manager, wire):
    manager.intents[
        "web_search"
    ].web_search.query = "{{ context.topic }} language documentation"
    await manager.process(UserMessage("one", "ignored", {"topic": "Python"}))
    assert tool_calls(wire)[0]["arguments"]["search_queries"] == [
        "Python language documentation"
    ]
    wire[0].clear()
    state = await converse(manager, "file:///etc/passwd", tool="web_fetch")
    assert "Service is not available" in state.bot_message[0]["text"]
    assert not wire[0]


def test_old_intent_and_state_need_no_migration():
    intent = Intent(name="old", intentId="old", speechResponse="Hello")
    assert IntentModel.from_db(intent).web_search is None
    state = State("old")
    state.user_message = UserMessage("old", "hello", {})
    data = state.to_dict()
    del data["web_session_id"]
    restored = State.from_dict(data)
    assert UUID(restored.web_session_id)
    restored.update(UserMessage("old", "follow up", {}))
    assert State.from_dict(restored.to_dict()).web_session_id == restored.web_session_id


@pytest.mark.asyncio
async def test_documented_parameter_collection_without_keys(manager, wire, monkeypatch):
    from app.bot.dialogue_manager.models import ParameterModel

    for name in ("PARALLEL_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    intent = manager.intents["web_search"]
    intent.parameters = [
        ParameterModel(
            name="query",
            type="free_text",
            required=True,
            prompt="What would you like to search for?",
        )
    ]
    intent.web_search.query = "{{ parameters.query }}"
    state = await converse(manager, "/web_search")
    assert not state.complete
    assert state.bot_message == [{"text": "What would you like to search for?"}]
    assert not wire[0]
    state = await converse(manager, "Python release schedule")
    assert state.complete
    assert tool_calls(wire)[0]["arguments"]["search_queries"] == [
        "Python release schedule"
    ]
    assert "python.org" in state.bot_message[0]["text"]


@pytest.mark.asyncio
async def test_first_call_cancellation_retains_session_for_retry(manager, wire):
    wire[1]["kind"] = "hang"
    task = asyncio.create_task(converse(manager))
    async with asyncio.timeout(2):
        while not tool_calls(wire):
            await asyncio.sleep(0)
    session_id = tool_calls(wire)[0]["arguments"]["session_id"]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    wire[1]["kind"] = "success"
    await converse(manager)
    assert tool_calls(wire)[-1]["arguments"]["session_id"] == session_id
