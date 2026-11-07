import asyncio

import httpx

from acf import config, workspace
from tests.acp_client import acp_connect
from tests.conftest import prompt, send


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


async def test_plain_reply_and_history(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "hello there")
    assert turn.stop_reason == "end_turn"
    assert turn.final == "Echo: hello there"
    assert turn.of("session_info_update")[0]["title"] == "hello there"
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert chat["title"] == "hello there" and not chat["running"]
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]


async def test_bash_tool_and_duration(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "run: echo $((6*7))")
    call = turn.of("tool_call")[0]
    assert call["title"] == "Ran echo $((6*7))" and call["kind"] == "execute" and call["status"] == "pending"
    assert call["rawInput"] == {"command": "echo $((6*7))"} and call["_meta"]["acf"]["tool"] == "bash"
    statuses = [u["status"] for u in turn.of("tool_call_update") if u["toolCallId"] == call["toolCallId"]]
    assert statuses == ["in_progress", "completed"]
    tool = turn.results[0]
    assert "42" in tool["text"] and tool["status"] == "completed" and tool["durationMs"] is not None
    assert turn.final.startswith("Result: 42")


async def test_failed_command_is_an_error_result(client, user):
    chat_id = await new_chat(client)
    tool = (await send(client, chat_id, "run: exit 3")).results[0]
    assert tool["status"] == "failed" and "exit code 3" in tool["text"]


async def test_write_read_edit(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "write: notes/todo.md | buy flour")
    ws = workspace.workspace_dir(user["id"])
    assert (ws / "notes/todo.md").read_text() == "buy flour"
    await send(client, chat_id, "edit: notes/todo.md | flour | butter")
    assert (ws / "notes/todo.md").read_text() == "buy butter"
    tool = (await send(client, chat_id, "edit: notes/todo.md | sugar | salt")).results[0]
    assert tool["status"] == "failed" and "not found" in tool["text"]
    turn = await send(client, chat_id, "read: notes/todo.md")
    assert turn.of("tool_call")[0]["locations"] == [{"path": "/workspace/notes/todo.md"}]
    assert turn.results[0]["text"].strip() == "1\tbuy butter"
    tool = (await send(client, chat_id, "read: ../../etc/passwd")).results[0]
    assert tool["status"] == "failed" and "outside the workspace" in tool["text"]


async def test_parallel_read_only_calls(client, user):
    ws = workspace.workspace_dir(user["id"])
    (ws / "a.md").write_text("alpha")
    (ws / "b.md").write_text("beta")
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "read: a.md b.md")
    assert {r["text"].split("\t")[1] for r in turn.results} == {"alpha", "beta"}


async def test_read_only_tools_run_concurrently_writes_in_order(user):
    import time

    from acf.agent.loop import Run
    from acf.agent.tools import Tool, ToolResult
    from acf.db import Chat, User, session_scope

    with session_scope() as db:
        u = db.get(User, user["id"])
        chat = Chat(user_id=u.id)
        db.add(chat)
        db.flush()
        chat_id = chat.id

    async def slow(args, ctx):
        await asyncio.sleep(0.3)
        return ToolResult(args["x"])

    ro = Tool("ro", "", {}, slow, read_only=lambda a: True)
    rw = Tool("rw", "", {}, slow)
    run = Run(u, chat_id)
    calls = [{"id": f"c{i}", "name": "ro", "args": {"x": str(i)}} for i in range(3)]
    t0 = time.monotonic()
    out = await run._execute(calls, {"ro": ro, "rw": rw}, None)
    assert time.monotonic() - t0 < 0.6 and [m.content for m in out] == ["0", "1", "2"]
    calls = [{"id": f"w{i}", "name": n, "args": {"x": n}} for i, n in enumerate(["ro", "rw"])]
    t0 = time.monotonic()
    await run._execute(calls, {"ro": ro, "rw": rw}, None)
    assert time.monotonic() - t0 >= 0.6  # a writer in the batch -> sequential


async def test_large_output_is_truncated_and_spilled(client, user):
    chat_id = await new_chat(client)
    tool = (await send(client, chat_id, "run: python3 -c \"print('x' * 100000)\"")).results[0]
    assert "characters omitted" in tool["text"] and len(tool["text"]) < 35_000
    spill = tool["text"].split("saved to ")[1].split(";")[0]
    assert len(workspace.read_file(user["id"], spill)) > 100_000


async def test_unknown_tool_is_recoverable(client, user):
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "tool: teleport {}")
    tool = turn.results[0]
    assert tool["status"] == "failed" and "Unknown tool teleport" in tool["text"]
    assert turn.stop_reason == "end_turn"


async def test_memory_and_context_reach_the_prompt(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "remember: my cat is called Miso")
    assert "- my cat is called Miso" in workspace.read_file(user["id"], "memory.md")
    await send(client, chat_id, "write: context.md | I run a bakery in Porto.")
    system = (await send(client, chat_id, "show system")).final
    assert "I run a bakery in Porto." in system and "my cat is called Miso" in system
    assert "skill-creator:" in system  # skills index


async def test_steering_message_is_injected(client, user):
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp:
        first = asyncio.create_task(prompt(acp, chat_id, "run: sleep 1.5; echo slow"))
        await acp.wait_for(lambda n: n.get("params", {}).get("update", {}).get("status") == "in_progress")
        steer = await prompt(acp, chat_id, "show messages")  # returns when the whole run ends
        turn = await first
    assert turn.stop_reason == steer.stop_reason == "end_turn"
    # The steering message is echoed when the agent reads it; the starting prompt is not echoed to its sender.
    assert [u["content"]["text"] for u in turn.of("user_message_chunk")] == ["show messages"]
    # The model saw both messages in one run, the steering one after the tool result.
    assert turn.final == "Messages: run: sleep 1.5; echo slow | show messages"
    roles = [m["role"] for m in (await client.get(f"/api/chats/{chat_id}")).json()["messages"]]
    assert roles == ["user", "assistant", "tool", "user", "assistant"]


async def test_steering_while_the_model_thinks_restarts_the_call(client, user):
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp:
        started = asyncio.get_running_loop().time()
        first = asyncio.create_task(prompt(acp, chat_id, "slow: 30 first thought"))
        await asyncio.sleep(0.5)
        await prompt(acp, chat_id, "show messages")
        turn = await first
    # The 30 s call was dropped; the model answered with both messages, without waiting it out.
    assert asyncio.get_running_loop().time() - started < 10
    assert turn.error is None and turn.stop_reason == "end_turn", turn.error
    assert turn.texts == ["Messages: slow: 30 first thought | show messages"]
    roles = [m["role"] for m in (await client.get(f"/api/chats/{chat_id}")).json()["messages"]]
    assert roles == ["user", "user", "assistant"]


async def test_cancel_stops_and_keeps_history_valid(client, user):
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp:
        task = asyncio.create_task(prompt(acp, chat_id, "run: sleep 20"))
        await acp.wait_for(lambda n: n.get("params", {}).get("update", {}).get("status") == "in_progress")
        await acp.notify("session/cancel", {"sessionId": str(chat_id)})
        turn = await asyncio.wait_for(task, 10)
    assert turn.stop_reason == "cancelled"
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    tool = [m for m in chat["messages"] if m["role"] == "tool"][0]
    assert tool["is_error"] and "Stopped" in tool["content"]
    # the chat keeps working afterwards
    assert (await send(client, chat_id, "hi again")).final == "Echo: hi again"


async def test_load_replays_history_then_follows_a_running_agent(client, user):
    chat_id = await new_chat(client)
    sid = str(chat_id)
    await send(client, chat_id, "run: echo first")
    async with acp_connect(client) as sender:
        running = asyncio.create_task(prompt(sender, chat_id, "run: sleep 1; echo attached"))
        await sender.wait_for(lambda n: n.get("params", {}).get("update", {}).get("status") == "in_progress")
        async with acp_connect(client) as watcher:
            loaded = await watcher.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
            assert loaded["_meta"]["acf"]["running"] is True
            end = await watcher.wait_for(lambda n: n["method"] == "_acf/turn_end")
            assert end["params"] == {"sessionId": sid, "stopReason": "end_turn"}
            kinds = [u["sessionUpdate"] for u in watcher.updates(sid)]
            texts = [u["content"]["text"] for u in watcher.updates(sid) if "content" in u and "text" in u["content"]]
        await running
    # replayed: the first exchange and the running prompt; then live: the tool result and the answer
    assert texts[0] == "run: echo first" and texts.count("run: sleep 1; echo attached") == 1
    assert texts[-1].startswith("Result: attached")
    assert kinds.count("tool_call") == 2  # no duplicates between the replay and the live updates
    async with acp_connect(client) as acp:
        loaded = await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
    assert loaded["_meta"]["acf"]["running"] is False


async def test_compaction_summarises_old_messages(client, user, fake_llm_url):
    old = (config.settings.compact_tokens, config.settings.compact_keep_tokens)
    config.settings.compact_tokens, config.settings.compact_keep_tokens = 200, 1
    try:
        chat_id = await new_chat(client)
        for i in range(3):
            await send(client, chat_id, f"message number {i} " + "padding " * 60)
        turn = await send(client, chat_id, "show messages")
        assert any("Summarised" in n for n in turn.notices)
        final = turn.final
        assert final.startswith("Messages: <summary of the earlier conversation>\nSUMMARY of")
        assert "message number 0" in final  # carried by the summary
    finally:
        config.settings.compact_tokens, config.settings.compact_keep_tokens = old
    async with httpx.AsyncClient() as h:
        last = (await h.get(f"{fake_llm_url}/_requests")).json()[-1]["body"]
    assert all(
        b.get("type") != "thinking"
        for m in last["messages"][:-1]
        if m["role"] == "assistant"
        for b in (m["content"] if isinstance(m["content"], list) else [])
    )


async def test_anthropic_request_shape(client, user, fake_llm_url):
    async with httpx.AsyncClient() as h:
        await h.delete(f"{fake_llm_url}/_requests")
    chat_id = await new_chat(client)
    await send(client, chat_id, "run: echo hi")
    async with httpx.AsyncClient() as h:
        reqs = (await h.get(f"{fake_llm_url}/_requests")).json()
    second = reqs[-1]["body"]
    assert second["model"] == "claude-opus-5-5"
    assert second["output_config"] == {"effort": "medium"}
    assert second["system"][0]["cache_control"] == {"type": "ephemeral"}
    assistant = second["messages"][-2]
    assert assistant["role"] == "assistant" and assistant["content"][0]["type"] == "thinking"
    assert second["messages"][-1]["content"][0]["type"] == "tool_result"
    assert {t["name"] for t in second["tools"]} == {"read", "write", "edit", "bash"}


async def test_openai_compatible_provider(client, user, fake_llm_url):
    r = await client.put(
        "/api/settings",
        json={"provider": "openai", "model": "local-model", "base_url": f"{fake_llm_url}/v1", "api_key": "k"},
    )
    assert r.status_code == 200 and r.json()["has_api_key"]
    chat_id = await new_chat(client)
    assert "openai-ok" in (await send(client, chat_id, "run: echo openai-ok")).final


async def test_llm_error_is_friendly(client, user):
    await client.put("/api/settings", json={"provider": "openai", "model": "m", "base_url": "http://127.0.0.1:1/v1"})
    chat_id = await new_chat(client)
    turn = await send(client, chat_id, "hi")
    assert turn.stop_reason is None and "Could not reach the model" in turn.error


async def test_long_unknown_tool_name_is_stored(client, user):
    chat_id = await new_chat(client)
    tool = (await send(client, chat_id, "tool: " + "t" * 300 + " {}")).results[0]
    assert tool["status"] == "failed" and "Unknown tool" in tool["text"]
