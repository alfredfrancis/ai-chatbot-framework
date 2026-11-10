"""Sub-agents: the `agent` tool starts helpers with a fresh context, in parallel, on a model the main agent picks."""

import asyncio
import json
import time

from acf import config
from acf.db import Message, session_scope
from acf.llm import LLMConfig
from tests.acp_client import acp_connect
from tests.conftest import prompt, send


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def agent(description: str, prompt: str, model: str | None = None) -> str:
    args = {"description": description, "prompt": prompt, **({"model": model} if model else {})}
    return f"tool: agent {json.dumps(args)}"


def agent_meta(turn, call_id: str) -> dict:
    """The sub-agent details on the update that finished the call."""
    done = [u for u in turn.of("tool_call_update") if u["toolCallId"] == call_id and u["status"] != "in_progress"]
    return done[-1]["_meta"]["acf"]["agent"]


async def test_sub_agents_run_in_parallel_and_report_back(client, user):
    chat_id = await new_chat(client)
    script = "\n".join(agent(f"Job {n}", f"run: sleep 1.5; echo {n}") for n in ("one", "two", "three"))
    t0 = time.monotonic()
    turn = await send(client, chat_id, script)
    assert time.monotonic() - t0 < 4  # one after the other would take 4.5 s
    calls = turn.of("tool_call")
    assert [c["title"] for c in calls] == ["Sub-agent: Job one", "Sub-agent: Job two", "Sub-agent: Job three"]
    assert [c["_meta"]["acf"]["tool"] for c in calls] == ["agent"] * 3
    # each result is that sub-agent's final answer
    by_call = {r["id"]: r for r in turn.results}
    texts = [by_call[c["toolCallId"]]["text"] for c in calls]
    assert [t.split()[:2] for t in texts] == [["Result:", "one"], ["Result:", "two"], ["Result:", "three"]]
    assert all(r["status"] == "completed" for r in turn.results)
    assert turn.final.startswith("Result: Result: three")  # the main agent goes on with the reports
    assert turn.stop_reason == "end_turn"


async def test_a_sub_agent_starts_with_a_fresh_context(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "the secret word is pineapple")
    turn = await send(client, chat_id, agent("Look around", "show messages"))
    assert turn.results[0]["text"] == "Messages: show messages"  # none of the chat's history
    # ...and what it did stays out of the chat's history: one call, one result
    with session_scope() as db:
        rows = db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
        assert [m.role for m in rows] == ["user", "assistant", "user", "assistant", "tool", "assistant"]
    turn = await send(client, chat_id, "show messages")
    assert "pineapple" in turn.final and "Messages: show messages" not in turn.final


async def test_the_main_agent_picks_each_sub_agents_model(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "subagent_fast_model", "quick-model")
    with session_scope() as db:
        from acf.db import User

        own = LLMConfig.for_user(db.get(User, user["id"])).model
    chat_id = await new_chat(client)
    script = "\n".join(
        [
            agent("Same", "show model"),
            agent("Inherit", "show model", "inherit"),
            agent("Fast", "show model", "fast"),
            agent("Named", "show model", "claude-sonnet-5-5"),
        ]
    )
    turn = await send(client, chat_id, script)
    models = [own, own, "quick-model", "claude-sonnet-5-5"]
    by_call = {r["id"]: r["text"] for r in turn.results}
    ids = [c["toolCallId"] for c in turn.of("tool_call")]
    assert [by_call[i] for i in ids] == [f"Model: {m}" for m in models]
    assert [agent_meta(turn, i)["model"] for i in ids] == models


async def test_sub_agents_have_the_tools_but_cannot_start_sub_agents(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "list tools")
    assert "agent" in turn.final.removeprefix("Tools: ").split(", ")
    turn = await send(client, chat_id, agent("Tools", "list tools"))
    names = turn.results[0]["text"].removeprefix("Tools: ").split(", ")
    assert {"read", "write", "edit", "bash", "mcp_call"} <= set(names) and "agent" not in names
    turn = await send(client, chat_id, agent("Prompt", "show system"))
    assert "You are a sub-agent" in turn.results[0]["text"]
    assert "<skills>" in turn.results[0]["text"]  # it knows the user's skills and context like the main agent


async def test_progress_is_live_and_survives_a_reload(client, user):
    chat_id = await new_chat(client)
    sid = str(chat_id)
    turn = await send(client, chat_id, agent("Say hi", "run: echo hi-from-sub"))
    call_id = turn.of("tool_call")[0]["toolCallId"]
    live = [
        u["_meta"]["acf"]["agent"]
        for u in turn.of("tool_call_update")
        if u["status"] == "in_progress" and u.get("_meta", {}).get("acf", {}).get("agent")
    ]
    assert live[0]["steps"] == [] and live[0]["model"]  # it started: the model is known at once
    assert live[1]["steps"] == [{"title": "Ran echo hi-from-sub", "ok": None}]  # a step, while it runs
    meta = agent_meta(turn, call_id)
    assert meta["steps"] == [{"title": "Ran echo hi-from-sub", "ok": True}]
    assert meta["tokens"] > 0 and meta["model"]
    assert turn.results[0]["text"].startswith("Result: hi-from-sub")

    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        ups = acp.updates(sid)
    final = [u for u in ups if u["sessionUpdate"] == "tool_call_update" and u["toolCallId"] == call_id][-1]
    assert final["status"] == "completed" and final["_meta"]["acf"]["agent"] == meta


async def test_stop_ends_the_sub_agents(client, user):
    chat_id = await new_chat(client)
    sid = str(chat_id)
    async with acp_connect(client) as acp:
        task = asyncio.create_task(prompt(acp, chat_id, agent("Long", "run: sleep 30; echo never")))
        await acp.wait_for(lambda n: "agent" in n.get("params", {}).get("update", {}).get("_meta", {}).get("acf", {}))
        t0 = time.monotonic()
        await acp.notify("session/cancel", {"sessionId": sid})
        turn = await task
    assert time.monotonic() - t0 < 5 and turn.stop_reason == "cancelled"
    # the history stays valid and the model hears about it next turn
    turn = await send(client, chat_id, "show messages")
    assert turn.stop_reason == "end_turn"
    with session_scope() as db:
        result = db.query(Message).filter_by(chat_id=chat_id, role="tool").one()
        assert result.is_error and "Stopped" in result.content


async def test_a_failing_sub_agent_is_an_error_result_not_a_failed_run(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, agent("Broken", "show model", "missing-model"))
    assert turn.error is None and turn.stop_reason == "end_turn"
    assert turn.results[0]["status"] == "failed" and "sub-agent" in turn.results[0]["text"].lower()
    assert turn.final.startswith("Result: ")  # the main agent carries on


async def test_at_most_the_configured_number_run_at_once(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "subagents", 1)
    chat_id = await new_chat(client)
    t0 = time.monotonic()
    turn = await send(client, chat_id, "\n".join(agent(f"Job {n}", "run: sleep 1; echo ok") for n in range(2)))
    assert time.monotonic() - t0 >= 2 and [r["status"] for r in turn.results] == ["completed"] * 2


async def test_sub_agents_can_be_switched_off(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "subagents", 0)
    turn = await send(client, await new_chat(client), "list tools")
    assert "agent" not in turn.final.removeprefix("Tools: ").split(", ")


async def test_each_sub_agent_has_its_own_read_only_session(client, user):
    from tests.acp_client import RpcError

    chat_id = await new_chat(client)
    turn = await send(client, chat_id, agent("Say hi", "run: echo hi-from-sub"))
    sub = agent_meta(turn, turn.of("tool_call")[0]["toolCallId"])["session"]
    assert sub != str(chat_id)

    async with acp_connect(client) as acp:
        # opening it replays what the sub-agent was asked, did and answered
        loaded = await acp.request("session/load", {"sessionId": sub, "cwd": "/", "mcpServers": []})
        assert loaded["_meta"]["acf"]["running"] is False and loaded["_meta"]["acf"]["title"] == "Say hi"
        assert loaded["_meta"]["acf"]["parent"]["sessionId"] == str(chat_id)
        ups = [u for u in acp.updates(sub) if u["sessionUpdate"] != "agent_message_chunk"]
        assert [u["sessionUpdate"] for u in ups] == ["user_message_chunk", "tool_call", "tool_call_update"]
        assert ups[0]["content"]["text"] == "run: echo hi-from-sub"
        assert ups[1]["title"] == "Ran echo hi-from-sub"
        assert ups[2]["status"] == "completed" and "hi-from-sub" in ups[2]["content"][0]["content"]["text"]
        assert acp.updates(sub)[-1]["content"]["text"].startswith("Result: hi-from-sub")
        # ...but nobody can send to it, and the chat lists leave it out
        for text in ("hello", "show messages"):
            try:
                await acp.request("session/prompt", {"sessionId": sub, "prompt": [{"type": "text", "text": text}]})
                raise AssertionError("a sub-agent's session took a message")
            except RpcError as e:
                assert "read-only" in e.message
        listed = [s["sessionId"] for s in (await acp.request("session/list", {}))["sessions"]]
        assert listed == [str(chat_id)]
    assert [c["id"] for c in (await client.get("/api/chats")).json()] == [chat_id]
    assert (await client.get(f"/api/chats/{sub}")).json()["parent_id"] == chat_id
    with session_scope() as db:
        assert [m.role for m in db.query(Message).filter_by(chat_id=int(sub)).order_by(Message.id)] == [
            "user",
            "assistant",
            "tool",
            "assistant",
        ]
    # it goes when its chat goes
    assert (await client.delete(f"/api/chats/{chat_id}")).status_code == 200
    assert (await client.get(f"/api/chats/{sub}")).status_code == 404


async def test_a_sub_agents_session_can_be_watched_while_it_works(client, user):
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp, acp_connect(client) as viewer:
        task = asyncio.create_task(prompt(acp, chat_id, agent("Slow", "run: sleep 1.5; echo slow-done")))
        meta = lambda n: n.get("params", {}).get("update", {}).get("_meta", {}).get("acf", {})  # noqa: E731
        note = await acp.wait_for(lambda n: meta(n).get("agent", {}).get("steps"))
        sub = note["params"]["update"]["_meta"]["acf"]["agent"]["session"]
        loaded = await viewer.request("session/load", {"sessionId": sub, "cwd": "/", "mcpServers": []})
        assert loaded["_meta"]["acf"]["running"] is True
        end = await viewer.wait_for(lambda n: n.get("method") == "_acf/turn_end")
        assert end["params"] == {"sessionId": sub, "stopReason": "end_turn"}
        kinds = [u["sessionUpdate"] for u in viewer.updates(sub)]
        assert kinds.count("user_message_chunk") == 1 and kinds.count("tool_call") == 1
        done = [u for u in viewer.updates(sub) if u["sessionUpdate"] == "tool_call_update"][-1]
        assert done["status"] == "completed" and "slow-done" in done["content"][0]["content"]["text"]
        assert viewer.updates(sub)[-1]["content"]["text"].startswith("Result: slow-done")
        await task


async def test_a_failed_sub_agents_session_says_why(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, agent("Broken", "show model", "missing-model"))
    sub = agent_meta(turn, turn.of("tool_call")[0]["toolCallId"])["session"]
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sub, "cwd": "/", "mcpServers": []})
        notices = [n["params"]["text"] for n in acp.notifications if n.get("method") == "_acf/notice"]
    assert len(notices) == 1 and notices[0].startswith("The sub-agent could not finish")
