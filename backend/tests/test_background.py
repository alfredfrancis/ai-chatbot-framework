"""Parallel tool calls and background commands within a chat."""

import asyncio
import json
import time

from acf import workspace
from tests.acp_client import acp_connect
from tests.conftest import prompt


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def bash(command: str, background: bool = False) -> str:
    args = {"command": command, **({"background": True} if background else {})}
    return f"tool: bash {json.dumps(args)}"


def _run_and_tools(user_id: int):
    from acf.agent.loop import Run
    from acf.agent.tools import Tool, ToolResult
    from acf.db import Chat, User, session_scope

    with session_scope() as db:
        u = db.get(User, user_id)
        chat = Chat(user_id=u.id)
        db.add(chat)
        db.flush()
        chat_id = chat.id

    async def slow(args, ctx):
        await asyncio.sleep(0.3)
        return ToolResult(args["x"])

    path = lambda a: a.get("path")  # noqa: E731
    tools = {
        "ro": Tool("ro", "", {}, slow, read_only=lambda a: True, resource=path),
        "rw": Tool("rw", "", {}, slow, resource=path),
    }
    return Run(u, chat_id), tools


async def test_independent_calls_run_at_the_same_time(user):
    run, tools = _run_and_tools(user["id"])
    calls = [
        {"id": f"c{i}", "name": n, "args": {"x": str(i), "path": f"f{i}"}} for i, n in enumerate(["ro", "rw", "rw"])
    ]
    t0 = time.monotonic()
    out = await run._execute(calls, tools, None)
    assert time.monotonic() - t0 < 0.6  # writers to different files don't wait for each other
    assert [m.content for m in out] == ["0", "1", "2"]  # results keep the order of the calls


async def test_calls_on_the_same_file_keep_their_order(user):
    run, tools = _run_and_tools(user["id"])
    calls = [{"id": f"c{i}", "name": n, "args": {"x": str(i), "path": "same.md"}} for i, n in enumerate(["rw", "ro"])]
    t0 = time.monotonic()
    await run._execute(calls, tools, None)
    assert time.monotonic() - t0 >= 0.6  # the read waits for the write to the same file
    reads = [{"id": f"r{i}", "name": "ro", "args": {"x": str(i), "path": "same.md"}} for i in range(3)]
    t0 = time.monotonic()
    await run._execute(reads, tools, None)
    assert time.monotonic() - t0 < 0.6  # reads of one file don't conflict


async def test_parallel_commands_in_one_chat(client, user):
    chat_id = await new_chat(client)
    script = "\n".join([bash("sleep 1; echo one"), bash("sleep 1; echo two"), bash("sleep 1; echo three")])
    t0 = time.monotonic()
    async with acp_connect(client) as acp:
        turn = await prompt(acp, chat_id, script)
    assert time.monotonic() - t0 < 2.5
    assert sorted(r["text"].split()[0] for r in turn.results) == ["one", "three", "two"]
    assert all(r["status"] == "completed" for r in turn.results)


async def test_background_command_reports_back_and_wakes_the_agent(client, user):
    chat_id = await new_chat(client)
    sid = str(chat_id)
    async with acp_connect(client) as acp:
        t0 = time.monotonic()
        turn = await prompt(acp, chat_id, bash("sleep 1; echo bg-done > out.txt; echo finished-bg", background=True))
        assert time.monotonic() - t0 < 1  # the run doesn't wait for the command
        assert turn.stop_reason == "end_turn" and not turn.results
        call_id = turn.of("tool_call")[0]["toolCallId"]
        started = [u for u in turn.of("tool_call_update") if u.get("_meta", {}).get("acf", {}).get("background")]
        assert (
            started
            and started[-1]["status"] == "in_progress"
            and "background" in started[-1]["content"][0]["content"]["text"]
        )
        assert turn.final.startswith("Result: Started in the background")

        # the job finishes: a new run starts by itself and this connection follows it
        start = await acp.wait_for(lambda n: n["method"] == "_acf/turn_start", timeout=10)
        assert start["params"] == {"sessionId": sid}
        await acp.wait_for(lambda n: sum(x["method"] == "_acf/turn_end" for x in acp.notifications) == 2, timeout=10)
        ups = acp.updates(sid)
        done = [u for u in ups if u["sessionUpdate"] == "tool_call_update" and u["toolCallId"] == call_id]
        assert done[-1]["status"] == "completed" and "finished-bg" in done[-1]["content"][0]["content"]["text"]
        assert done[-1]["_meta"]["acf"]["durationMs"] >= 1000
        replies = [u["content"]["text"] for u in ups if u["sessionUpdate"] == "agent_message_chunk"]
        assert "Background done:" in "".join(replies)
    assert workspace.read_file(user["id"], "out.txt").strip() == "bg-done"

    # a reload shows the finished job on the original step, not as a user message
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        ups = acp.updates(sid)
    assert [u["content"]["text"] for u in ups if u["sessionUpdate"] == "user_message_chunk"] == [
        bash("sleep 1; echo bg-done > out.txt; echo finished-bg", background=True)
    ]
    final = [u for u in ups if u["sessionUpdate"] == "tool_call_update" and u["toolCallId"] == call_id][-1]
    assert final["status"] == "completed"


async def test_background_result_joins_a_run_that_is_still_working(client, user):
    chat_id = await new_chat(client)
    script = "\n".join([bash("sleep 0.2; echo quick-bg", background=True), bash("sleep 1.5; echo slow-fg")])
    async with acp_connect(client) as acp:
        turn = await prompt(acp, chat_id, script)
        await asyncio.sleep(0.5)
        assert not [n for n in acp.notifications if n["method"] == "_acf/turn_start"]  # no second run
    assert turn.final.startswith("Background done:") and "quick-bg" in turn.final
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert not chat["running"]


async def test_stop_also_stops_background_commands(client, user):
    chat_id = await new_chat(client)
    sid = str(chat_id)
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        turn = await prompt(acp, chat_id, bash("sleep 30; echo never", background=True))
        call_id = turn.of("tool_call")[0]["toolCallId"]
        await acp.notify("session/cancel", {"sessionId": sid})

        def stopped(n):
            u = n.get("params", {}).get("update", {})
            return u.get("toolCallId") == call_id and u.get("status") == "failed"

        n = await acp.wait_for(stopped, timeout=10)
        assert "Stopped" in n["params"]["update"]["content"][0]["content"]["text"]
        await asyncio.sleep(0.3)
        assert not [x for x in acp.notifications if x["method"] == "_acf/turn_start"]  # a stop doesn't wake it
    # the model learns about it on the next turn
    async with acp_connect(client) as acp:
        turn = await prompt(acp, chat_id, "show messages")
    assert "Stopped by the user" in turn.final


async def test_a_job_lost_in_a_restart_is_closed_off(user):
    from acf.agent.loop import load_history
    from acf.db import Chat, Message, session_scope

    with session_scope() as db:
        chat = Chat(user_id=user["id"])
        db.add(chat)
        db.flush()
        chat_id = chat.id
        db.add(Message(chat_id=chat_id, role="user", content="go"))
        tc = {"id": "t1", "name": "bash", "arguments": {"command": "sleep 99", "background": True}}
        db.add(Message(chat_id=chat_id, role="assistant", content="", tool_calls=[tc]))
        db.add(
            Message(
                chat_id=chat_id,
                role="tool",
                content="Started in the background",
                tool_call_id="t1",
                name="bash",
                raw={"background": "bg-gone"},
            )
        )
    history = load_history(chat_id)
    assert "restarted" in str(history[-1].content)
    assert len(load_history(chat_id)) == len(history)  # repaired once
