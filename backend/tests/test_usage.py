"""Context usage: every model call reports how full the context window is and what fills it."""

from langchain_core.messages import AIMessage, HumanMessage

from acf import config
from acf.agent import usage
from tests.acp_client import acp_connect
from tests.conftest import prompt


def _usage(updates):
    return [u for u in updates if u["sessionUpdate"] == "usage_update"]


def _parts(u):
    return {p["name"]: p for p in u["_meta"]["acf"]["parts"]}


async def test_each_model_call_reports_context_usage(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        turn = await prompt(acp, sid, "run: echo hi")
    reports = _usage(turn.updates)
    assert len(reports) == 2  # the tool call, then the answer
    last = reports[-1]
    meta = last["_meta"]["acf"]
    assert last["size"] == 1_000_000  # the default model's window, from its LangChain profile
    assert meta["measured"] is True  # the fake Anthropic API reports input tokens
    assert last["used"] > reports[0]["used"] > 0  # the context grows with the tool result
    assert meta["percent"] == round(100 * last["used"] / last["size"], 1)
    parts = _parts(last)
    assert list(parts) == ["System prompt", "Tools", "Skills", "Messages"]
    assert {"read", "write", "edit", "bash"} <= set(parts["Tools"]["items"])
    assert {"skill-creator", "personal-apps"} <= set(parts["Skills"]["items"])
    assert parts["Messages"]["count"] == 4  # user, tool call, tool result, answer
    assert all(p["tokens"] > 0 for p in parts.values())


async def test_load_replays_the_latest_usage(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        live = _usage((await prompt(acp, sid, "hello")).updates)[-1]
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        updates = acp.updates(sid)
    assert updates[-1] == live


async def test_context_window_setting_overrides_the_model(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "context_window", 50_000)
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        u = _usage((await prompt(acp, sid, "hello")).updates)[-1]
    assert u["size"] == 50_000 and u["_meta"]["acf"]["percent"] == round(100 * u["used"] / 50_000, 1)


def test_estimates_when_the_provider_reports_nothing():
    sections = [("instructions", "x" * 400), ("skills", "y" * 40), ("apps", "z" * 80), ("memory", "m" * 400)]
    tools = [{"type": "function", "function": {"name": "bash", "description": "d", "parameters": {}}}]
    history = [HumanMessage("h" * 40), AIMessage("a" * 40)]
    u = usage.measure(sections, tools, ["notes"], {"github": ["list_issues"]}, history, history[-1], 1000)
    parts = {p["name"]: p for p in u["parts"]}
    assert u["measured"] is False and u["used"] == sum(p["tokens"] for p in u["parts"])
    assert parts["System prompt"]["tokens"] == 200 and parts["Skills"] == {
        "name": "Skills",
        "tokens": 10,
        "items": ["notes"],
    }
    assert parts["Tools"]["items"] == ["bash", "github: list_issues"] and parts["Messages"]["count"] == 2
    assert u["percent"] == round(100 * u["used"] / 1000, 1)


def test_window_falls_back_when_the_model_is_unknown():
    class Unknown:
        profile = None

    assert usage.window(Unknown()) == usage.DEFAULT_WINDOW
