"""The Agent Client Protocol endpoint: protocol, sessions, auth and the external access token."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.acp_client import Rejected, RpcError, acp_connect, joined
from tests.conftest import free_port, prompt, serve


async def test_initialize_and_session_lifecycle(client, user):
    async with acp_connect(client) as acp:
        init = await acp.request("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
        assert init["protocolVersion"] == 1
        caps = init["agentCapabilities"]
        assert caps["loadSession"] is True and caps["promptCapabilities"]["embeddedContext"] is True
        assert init["agentInfo"]["name"] == "ai-chatbot-framework" and init["authMethods"] == []

        sid = (await acp.request("session/new", {"cwd": "/home/me", "mcpServers": []}))["sessionId"]
        turn = await prompt(acp, sid, "hello acp")
        assert turn.stop_reason == "end_turn" and turn.final == "Echo: hello acp"

        listed = (await acp.request("session/list", {}))["sessions"]
        assert listed[0]["sessionId"] == sid and listed[0]["title"] == "hello acp" and listed[0]["cwd"] == "/workspace"

    # the web app sees the same chat
    chats = (await client.get("/api/chats")).json()
    assert chats[0]["id"] == int(sid) and chats[0]["title"] == "hello acp"


async def test_load_replays_the_history(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        await prompt(acp, sid, "run: echo replay-me")
    async with acp_connect(client) as acp:
        result = await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        assert result["_meta"]["acf"]["running"] is False
        kinds = [(u["sessionUpdate"], u.get("status")) for u in acp.updates(sid)]
    assert kinds == [
        ("user_message_chunk", None),
        ("agent_message_chunk", None),
        ("tool_call", "pending"),
        ("tool_call_update", "completed"),
        ("agent_message_chunk", None),
    ]


async def test_prompt_content_blocks(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        blocks = [
            {"type": "text", "text": "Look at this"},
            {"type": "resource", "resource": {"uri": "file:///notes.md", "text": "buy flour"}},
        ]
        await acp.request("session/prompt", {"sessionId": sid, "prompt": blocks})
        final = list(joined([u for u in acp.updates(sid) if u["sessionUpdate"] == "agent_message_chunk"]).values())[-1]
        assert final == 'Echo: Look at this\n\n<file uri="file:///notes.md">\nbuy flour\n</file>'

        with pytest.raises(RpcError) as e:
            await acp.request("session/prompt", {"sessionId": sid, "prompt": [{"type": "image", "data": "x"}]})
        assert e.value.code == -32602 and "Unsupported content block: image" in e.value.message


async def test_protocol_errors(client, user):
    async with acp_connect(client) as acp:
        with pytest.raises(RpcError) as e:
            await acp.request("session/fly", {})
        assert e.value.code == -32601
        with pytest.raises(RpcError) as e:
            await acp.request("session/prompt", {"sessionId": "999999", "prompt": [{"type": "text", "text": "hi"}]})
        assert e.value.code == -32002
        await acp.raw("not json")
        err = await acp.wait_for(lambda n: n.get("error", {}).get("code") == -32700)
        assert err["id"] is None


async def test_sessions_are_private(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
    await client.post("/api/auth/logout")
    other = f"other-{time.time_ns()}@example.com"
    await client.post("/api/auth/signup", json={"email": other, "password": "correct horse"})
    async with acp_connect(client) as acp:
        with pytest.raises(RpcError) as e:
            await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        assert e.value.code == -32002
        assert (await acp.request("session/list", {}))["sessions"] == []


async def test_connection_needs_auth_and_same_origin_cookie(client, user):
    cookie = client.cookies.get("acf_session")
    app = client._transport.app
    from tests.acp_client import AsgiWebSocket

    with pytest.raises(Rejected):
        async with AsgiWebSocket(app, "/api/acp"):
            pass
    with pytest.raises(Rejected):  # cross-site page using the user's cookie
        async with AsgiWebSocket(
            app, "/api/acp", {"cookie": f"acf_session={cookie}", "origin": "https://evil.example"}
        ):
            pass
    async with AsgiWebSocket(app, "/api/acp", {"cookie": f"acf_session={cookie}", "origin": "http://test"}):
        pass
    with pytest.raises(Rejected):  # a session token is not an ACP token
        async with AsgiWebSocket(app, "/api/acp", {"authorization": f"Bearer {cookie}"}):
            pass


async def test_access_token_for_external_clients(client, user):
    assert (await client.get("/api/acp/token")).json() == {"token": None, "endpoint": "/api/acp"}
    created = (await client.post("/api/acp/token")).json()
    token = created["value"]
    assert token.startswith("acp_") and created["token"]["hint"] == token[-4:]
    assert created["token"]["last_used_at"] is None
    assert "value" not in (await client.get("/api/acp/token")).json()  # shown once

    async with acp_connect(client, {"authorization": f"Bearer {token}"}) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        assert (await prompt(acp, sid, "from outside")).final == "Echo: from outside"
    info = (await client.get("/api/acp/token")).json()["token"]
    assert info["last_used_at"] is not None

    # replacing the token revokes the old one; deleting turns external access off
    new = (await client.post("/api/acp/token")).json()["value"]
    with pytest.raises(Rejected):
        async with acp_connect(client, {"authorization": f"Bearer {token}"}):
            pass
    async with acp_connect(client, {"authorization": f"Bearer {new}"}):
        pass
    assert (await client.delete("/api/acp/token")).json()["token"] is None
    with pytest.raises(Rejected):
        async with acp_connect(client, {"authorization": f"Bearer {new}"}):
            pass


async def test_stdio_bridge_end_to_end(client, user):
    """A stdio ACP client (like an editor) reaches a real server through `python -m acf.acp_bridge`."""
    from acf.main import create_app

    token = (await client.post("/api/acp/token")).json()["value"]
    port = free_port()
    server = serve(create_app(), port)
    env = {**os.environ, "ACF_ACP_TOKEN": token}
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "acf.acp_bridge",
        "--url",
        f"ws://127.0.0.1:{port}/api/acp",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        cwd=Path(__file__).parents[1],
        env=env,
    )

    async def call(mid: int, method: str, params: dict) -> tuple[dict, list[dict]]:
        proc.stdin.write(
            (json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params}) + "\n").encode()
        )
        await proc.stdin.drain()
        seen = []
        while True:
            msg = json.loads(await asyncio.wait_for(proc.stdout.readline(), 30))
            if msg.get("id") == mid:
                return msg, seen
            seen.append(msg)

    try:
        init, _ = await call(1, "initialize", {"protocolVersion": 1, "clientCapabilities": {}})
        assert init["result"]["protocolVersion"] == 1
        new, _ = await call(2, "session/new", {"cwd": "/tmp", "mcpServers": []})
        sid = new["result"]["sessionId"]
        res, seen = await call(
            3, "session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": "run: echo bridged"}]}
        )
        assert res["result"] == {"stopReason": "end_turn"}
        texts = list(
            joined(
                [
                    m["params"]["update"]
                    for m in seen
                    if m.get("method") == "session/update"
                    and m["params"]["update"]["sessionUpdate"] == "agent_message_chunk"
                ]
            ).values()
        )
        assert texts[-1].startswith("Result: bridged")  # streamed, joined per message
        bad = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "acf.acp_bridge",
            "--url",
            f"ws://127.0.0.1:{port}/api/acp",
            "--token",
            "acp_wrong",
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parents[1],
        )
        _, err = await asyncio.wait_for(bad.communicate(), 20)
        assert bad.returncode == 2 and b"refused the connection (403)" in err
    finally:
        proc.stdin.close()
        await asyncio.wait_for(proc.wait(), 10)
        server.should_exit = True


async def test_attached_files_reach_the_agent_and_replay_as_links(client, user):
    await client.post("/api/files", files={"file": ("sales.csv", b"day,eur\nmon,120\n")}, data={"folder": "uploads"})
    link = {"type": "resource_link", "uri": "file:///workspace/uploads/sales.csv", "name": "sales.csv", "size": 16}
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        await acp.request(
            "session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": "read: uploads/sales.csv"}, link]}
        )
        steps = [u for u in acp.updates(sid) if u["sessionUpdate"] == "tool_call_update" and u.get("content")]
        assert "mon,120" in steps[-1]["content"][0]["content"]["text"]

        # an attachment alone is a valid prompt; the agent reads where the file is
        await acp.request("session/prompt", {"sessionId": sid, "prompt": [link]})
        final = list(joined([u for u in acp.updates(sid) if u["sessionUpdate"] == "agent_message_chunk"]).values())[-1]
        assert final == "Echo: [Attached file: sales.csv](file:///workspace/uploads/sales.csv)"
        sid2 = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        await acp.request("session/prompt", {"sessionId": sid2, "prompt": [link]})
    chats = {c["id"]: c["title"] for c in (await client.get("/api/chats")).json()}
    assert chats[int(sid)] == "read: uploads/sales.csv" and chats[int(sid2)] == "sales.csv"

    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        users = [u for u in acp.updates(sid) if u["sessionUpdate"] == "user_message_chunk"]
    first, second = users[0]["_meta"]["acf"]["messageId"], users[-1]["_meta"]["acf"]["messageId"]
    assert [(u["content"]["type"], u["_meta"]["acf"]["messageId"]) for u in users] == [
        ("text", first),
        ("resource_link", first),
        ("resource_link", second),
    ]
    assert users[0]["content"]["text"] == "read: uploads/sales.csv"
    assert users[1]["content"] == {
        "type": "resource_link",
        "uri": "file:///workspace/uploads/sales.csv",
        "name": "sales.csv",
    }


async def test_only_workspace_links_count_as_attachments(client, user):
    async with acp_connect(client) as acp:
        sid = (await acp.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        # a name with spaces and brackets (a kept upload) is still one attachment
        odd = {"type": "resource_link", "uri": "file:///workspace/uploads/a (1).csv", "name": "a (1).csv"}
        await acp.request("session/prompt", {"sessionId": sid, "prompt": [odd]})
        link = {"type": "resource_link", "uri": "https://example.com/a.pdf", "name": "a.pdf"}
        await acp.request("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": "see"}, link]})
        final = list(joined([u for u in acp.updates(sid) if u["sessionUpdate"] == "agent_message_chunk"]).values())[-1]
        assert final == "Echo: see\n\n[a.pdf](https://example.com/a.pdf)"
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        users = [u["content"] for u in acp.updates(sid) if u["sessionUpdate"] == "user_message_chunk"]
    assert users[0] == {
        "type": "resource_link",
        "uri": "file:///workspace/uploads/a%20%281%29.csv",
        "name": "a (1).csv",
    }
    assert users[1] == {"type": "text", "text": "see\n\n[a.pdf](https://example.com/a.pdf)"}
