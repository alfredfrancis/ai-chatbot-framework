import asyncio
import json

import httpx

from acf import config, workspace
from tests.conftest import send


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def msgs(events, role):
    return [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == role]


async def test_plain_reply_and_history(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "hello there")
    assert events[-1]["type"] == "done"
    assert msgs(events, "assistant")[-1]["content"] == "Echo: hello there"
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert chat["title"] == "hello there" and not chat["running"]
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]


async def test_bash_tool_and_duration(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "run: echo $((6*7))")
    start = next(e for e in events if e["type"] == "tool_start")
    assert start["name"] == "bash" and start["label"] == "echo $((6*7))"
    tool = msgs(events, "tool")[0]
    assert "42" in tool["content"] and not tool["is_error"] and tool["duration_ms"] is not None
    assert msgs(events, "assistant")[-1]["content"].startswith("Result: 42")


async def test_failed_command_is_an_error_result(client, user):
    chat_id = await new_chat(client)
    tool = msgs(await send(client, chat_id, "run: exit 3"), "tool")[0]
    assert tool["is_error"] and "exit code 3" in tool["content"]


async def test_write_read_edit(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "write: notes/todo.md | buy flour")
    ws = workspace.workspace_dir(user["id"])
    assert (ws / "notes/todo.md").read_text() == "buy flour"
    await send(client, chat_id, "edit: notes/todo.md | flour | butter")
    assert (ws / "notes/todo.md").read_text() == "buy butter"
    tool = msgs(await send(client, chat_id, "edit: notes/todo.md | sugar | salt"), "tool")[0]
    assert tool["is_error"] and "not found" in tool["content"]
    tool = msgs(await send(client, chat_id, "read: notes/todo.md"), "tool")[0]
    assert tool["content"].strip() == "1\tbuy butter"
    tool = msgs(await send(client, chat_id, "read: ../../etc/passwd"), "tool")[0]
    assert tool["is_error"] and "outside the workspace" in tool["content"]


async def test_parallel_read_only_calls(client, user):
    ws = workspace.workspace_dir(user["id"])
    (ws / "a.md").write_text("alpha")
    (ws / "b.md").write_text("beta")
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "read: a.md b.md")
    assert {m["content"].split("\t")[1] for m in msgs(events, "tool")} == {"alpha", "beta"}


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
    tool = msgs(await send(client, chat_id, "run: python3 -c \"print('x' * 100000)\""), "tool")[0]
    assert "characters omitted" in tool["content"] and len(tool["content"]) < 35_000
    spill = tool["content"].split("saved to ")[1].split(";")[0]
    assert len(workspace.read_file(user["id"], spill)) > 100_000


async def test_unknown_tool_is_recoverable(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "tool: teleport {}")
    tool = msgs(events, "tool")[0]
    assert tool["is_error"] and "Unknown tool teleport" in tool["content"]
    assert events[-1]["type"] == "done"


async def test_memory_and_context_reach_the_prompt(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "remember: my cat is called Miso")
    assert "- my cat is called Miso" in workspace.read_file(user["id"], "memory.md")
    await send(client, chat_id, "write: context.md | I run a bakery in Porto.")
    system = msgs(await send(client, chat_id, "show system"), "assistant")[-1]["content"]
    assert "I run a bakery in Porto." in system and "my cat is called Miso" in system
    assert "skill-creator:" in system  # skills index


async def test_steering_message_is_injected(client, user):
    chat_id = await new_chat(client)

    async def later():
        # Wait until the tool is running (the model has answered with the call), then steer.
        for _ in range(200):
            chat = (await client.get(f"/api/chats/{chat_id}")).json()
            if any(m["role"] == "assistant" for m in chat["messages"]):
                break
            await asyncio.sleep(0.05)
        r = await client.post(f"/api/chats/{chat_id}/messages", json={"content": "show messages"})
        assert r.status_code == 202 and r.json() == {"queued": True}

    task = asyncio.create_task(later())
    events = await send(client, chat_id, "run: sleep 1.5; echo slow")
    await task
    assert any(e["type"] == "queued" and e["text"] == "show messages" for e in events)
    final = msgs(events, "assistant")[-1]["content"]
    # The model saw both messages in one run, the steering one after the tool result.
    assert final == "Messages: run: sleep 1.5; echo slow | show messages"
    roles = [m["role"] for m in (await client.get(f"/api/chats/{chat_id}")).json()["messages"]]
    assert roles == ["user", "assistant", "tool", "user", "assistant"]


async def test_steering_while_the_model_thinks_restarts_the_call(client, user):
    chat_id = await new_chat(client)

    async def later():
        await asyncio.sleep(0.5)
        r = await client.post(f"/api/chats/{chat_id}/messages", json={"content": "show messages"})
        assert r.status_code == 202

    task = asyncio.create_task(later())
    started = asyncio.get_running_loop().time()
    events = await send(client, chat_id, "slow: 30 first thought")
    await task
    # The 30 s call was dropped; the model answered with both messages, without waiting it out.
    assert asyncio.get_running_loop().time() - started < 10
    assert [m["content"] for m in msgs(events, "assistant")] == ["Messages: slow: 30 first thought | show messages"]
    roles = [m["role"] for m in (await client.get(f"/api/chats/{chat_id}")).json()["messages"]]
    assert roles == ["user", "user", "assistant"]


async def test_stop_cancels_and_keeps_history_valid(client, user):
    chat_id = await new_chat(client)

    async def stop_soon():
        await asyncio.sleep(0.8)
        assert (await client.post(f"/api/chats/{chat_id}/stop")).json() == {"stopped": True}

    task = asyncio.create_task(stop_soon())
    events = await send(client, chat_id, "run: sleep 20")
    await task
    assert any(e["type"] == "stopped" for e in events)
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    tool = [m for m in chat["messages"] if m["role"] == "tool"][0]
    assert tool["is_error"] and "Stopped" in tool["content"]
    # the chat keeps working afterwards
    assert msgs(await send(client, chat_id, "hi again"), "assistant")[-1]["content"] == "Echo: hi again"


async def test_attach_to_running_chat(client, user):
    chat_id = await new_chat(client)
    collected = []

    async def sender():
        collected.extend(await send(client, chat_id, "run: sleep 1; echo attached"))

    t = asyncio.create_task(sender())
    await asyncio.sleep(0.4)
    events = []
    async with client.stream("GET", f"/api/chats/{chat_id}/stream") as r:
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    await t
    assert events[0]["type"] == "message" and events[0]["message"]["role"] == "user"  # replayed
    assert msgs(events, "assistant")[-1]["content"].startswith("Result: attached")
    assert (await client.get(f"/api/chats/{chat_id}/stream")).json() == {"running": False}


async def test_compaction_summarises_old_messages(client, user, fake_llm_url):
    old = (config.settings.compact_tokens, config.settings.compact_keep_tokens)
    config.settings.compact_tokens, config.settings.compact_keep_tokens = 200, 1
    try:
        chat_id = await new_chat(client)
        for i in range(3):
            await send(client, chat_id, f"message number {i} " + "padding " * 60)
        events = await send(client, chat_id, "show messages")
        assert any(e["type"] == "notice" and "Summarised" in e["text"] for e in events)
        final = msgs(events, "assistant")[-1]["content"]
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
    final = msgs(await send(client, chat_id, "run: echo openai-ok"), "assistant")[-1]
    assert "openai-ok" in final["content"]


async def test_llm_error_is_friendly(client, user):
    await client.put("/api/settings", json={"provider": "openai", "model": "m", "base_url": "http://127.0.0.1:1/v1"})
    chat_id = await new_chat(client)
    err = next(e for e in await send(client, chat_id, "hi") if e["type"] == "error")
    assert "Could not reach the model" in err["error"]


async def test_long_unknown_tool_name_is_stored(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "tool: " + "t" * 300 + " {}")
    tool = msgs(events, "tool")[0]
    assert tool["is_error"] and "Unknown tool" in tool["content"]
