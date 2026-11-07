import httpx

from harbor import workspace
from tests.conftest import send


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


async def test_plain_reply_and_history(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "hello there")
    kinds = [e["type"] for e in events]
    assert kinds[-1] == "done"
    replies = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"]
    assert replies[-1]["content"] == "Echo: hello there"

    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert chat["title"] == "hello there"
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]


async def test_run_command_tool(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "run: echo $((6*7))")
    starts = [e for e in events if e["type"] == "tool_start"]
    assert starts and starts[0]["name"] == "run_command"
    tool_msgs = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool"]
    assert "42" in tool_msgs[0]["content"] and not tool_msgs[0]["is_error"]
    final = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][
        -1
    ]
    assert final["content"].startswith("Result: 42")


async def test_failed_command_is_reported_as_error(client, user):
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "run: exit 3")
    tool_msg = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert tool_msg["is_error"] and "exit code 3" in tool_msg["content"]


async def test_files_roundtrip(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "write: notes/todo.md | buy flour")
    assert (workspace.workspace_dir(user["id"]) / "notes/todo.md").read_text() == "buy flour"
    events = await send(client, chat_id, "read: notes/todo.md")
    assert any("buy flour" in e["message"]["content"] for e in events if e["type"] == "message")
    files = (await client.get("/api/files")).json()
    assert {"path": "notes/todo.md", "size": 9} in files
    events = await send(client, chat_id, "read: ../../etc/passwd")
    tool = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert tool["is_error"] and "outside the workspace" in tool["content"]


async def test_remember_updates_memory_and_prompt(client, user):
    chat_id = await new_chat(client)
    await send(client, chat_id, "remember: my cat is called Miso")
    mem = (await client.get("/api/memory")).json()["memory"]
    assert "- my cat is called Miso" in mem

    await client.put("/api/memory/context", json={"content": "# About me\nI run a bakery in Porto."})
    events = await send(client, chat_id, "show system")
    system = [
        e["message"]["content"]
        for e in events
        if e["type"] == "message" and e["message"]["role"] == "assistant"
    ][-1]
    assert "I run a bakery in Porto." in system
    assert "my cat is called Miso" in system


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
    # assistant turn is replayed verbatim (thinking block kept) and tool results go back in one user turn
    assistant = second["messages"][-2]
    assert assistant["role"] == "assistant" and assistant["content"][0]["type"] == "thinking"
    assert second["messages"][-1]["content"][0]["type"] == "tool_result"
    assert {t["name"] for t in second["tools"]} >= {"run_command", "read_file", "write_file", "remember"}


async def test_openai_compatible_provider(client, user, fake_llm_url):
    r = await client.put(
        "/api/settings",
        json={"provider": "openai", "model": "local-model", "base_url": f"{fake_llm_url}/v1", "api_key": "k"},
    )
    assert r.status_code == 200 and r.json()["has_api_key"]
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "run: echo openai-ok")
    final = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][
        -1
    ]
    assert "openai-ok" in final["content"]


async def test_llm_error_is_friendly(client, user):
    await client.put(
        "/api/settings", json={"provider": "openai", "model": "m", "base_url": "http://127.0.0.1:1/v1"}
    )
    chat_id = await new_chat(client)
    events = await send(client, chat_id, "hi")
    err = next(e for e in events if e["type"] == "error")
    assert "Could not reach the model" in err["error"]
