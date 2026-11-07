import json
import re
import shutil
from urllib.parse import parse_qs, urlparse

import httpx

from acf import workspace
from acf.mcp_client import ConfigError, parse_config
from tests.conftest import FAKES, send


def test_parse_config_validation():
    ok = parse_config('{"mcpServers": {"a": {"command": "npx", "args": ["x"]}, "b": {"url": "https://x/mcp"}}}')
    assert ok["a"].transport == "stdio" and ok["b"].transport == "http"
    for bad, msg in [
        ("{", "Invalid JSON"),
        ('{"mcpServers": {"a": {}}}', "needs either"),
        ('{"mcpServers": {"bad name": {"command": "x"}}}', "may only use"),
        ('{"mcpServers": {"a": {"url": "ftp://x"}}}', "must start with"),
    ]:
        try:
            parse_config(bad)
        except ConfigError as e:
            assert msg in str(e)
        else:
            raise AssertionError(bad)


async def test_save_config_rejects_invalid(client, user):
    r = await client.put("/api/mcp/config", json={"config": '{"mcpServers": {"a": 1}}'})
    assert r.status_code == 400


async def setup_echo(client, user_id):
    shutil.copy(FAKES / "echo_mcp.py", workspace.workspace_dir(user_id) / "echo_mcp.py")
    cfg = {"mcpServers": {"echo": {"command": "python3", "args": ["echo_mcp.py"]}}}
    assert (await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})).status_code == 200


async def test_stdio_server_tools(client, user):
    await setup_echo(client, user["id"])
    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "connected", servers
    assert {t["name"] for t in servers[0]["tools"]} == {"echo", "add", "whereami"}

    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    call = {"server": "echo", "tool": "add", "arguments": {"a": 2, "b": 40}}
    events = await send(client, chat_id, f"tool: mcp_call {json.dumps(call)}")
    start = next(e for e in events if e["type"] == "tool_start")
    assert start["label"] == "echo · add"
    final = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][-1]
    assert final["content"] == "Result: 42"


def _reply(events) -> str:
    return [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][-1][
        "content"
    ]


async def test_app_tools_are_names_in_the_prompt_and_files_in_the_workspace(client, user):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    assert _reply(await send(client, chat_id, "list tools")) == "Tools: read, write, edit, bash"
    assert "mcp_call" not in _reply(await send(client, chat_id, "show system"))

    await setup_echo(client, user["id"])
    stale = workspace.workspace_dir(user["id"]) / ".acf/mcp/echo/removed_tool.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("{}")
    assert _reply(await send(client, chat_id, "list tools")) == "Tools: read, write, edit, bash, mcp_call"
    system = _reply(await send(client, chat_id, "show system"))
    assert "echo: add, echo, whereami" in system.splitlines()
    assert "mcp_call" in system and ".acf/mcp/" in system

    definition = json.loads(workspace.read_file(user["id"], ".acf/mcp/echo/add.json"))
    assert definition == {
        "description": "Add two numbers",
        "input_schema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    }
    assert not stale.exists()

    events = await send(client, chat_id, "read: .acf/mcp/echo/echo.json")
    result = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert not result["is_error"] and "Echo the given text back" in result["content"]


async def test_unknown_app_tool_lists_the_valid_ones(client, user):
    await setup_echo(client, user["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, 'tool: mcp_call {"server": "echo", "tool": "teleport", "arguments": {}}')
    result = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert result["is_error"]
    assert all(name in result["content"] for name in ("add", "echo", "whereami"))


async def test_read_only_app_tools_run_together(client, user):
    await setup_echo(client, user["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]

    def order(events) -> list[str]:
        return [
            "start" if e["type"] == "tool_start" else "result"
            for e in events
            if e["type"] == "tool_start" or (e["type"] == "message" and e["message"]["role"] == "tool")
        ]

    echo = 'tool: mcp_call {"server": "echo", "tool": "echo", "arguments": {"text": "%s"}}'
    add = 'tool: mcp_call {"server": "echo", "tool": "add", "arguments": {"a": 1, "b": 2}}'
    events = await send(client, chat_id, f"{echo % 'one'}\n{echo % 'two'}")
    assert order(events) == ["start", "start", "result", "result"]
    events = await send(client, chat_id, f"{echo % 'one'}\n{add}")
    assert order(events) == ["start", "result", "start", "result"]


async def test_broken_server_reported(client, user):
    cfg = {"mcpServers": {"nope": {"command": "definitely-not-a-binary-xyz"}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "error" and servers[0]["error"]
    # the agent still works and tells the user
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, "hello")
    assert any(e["type"] == "notice" and e["text"].startswith("nope:") for e in events)
    assert events[-1]["type"] == "done"


async def test_oauth_flow(client, user, oauth_mcp_url):
    cfg = {"mcpServers": {"notes": {"url": f"{oauth_mcp_url}/mcp"}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "needs_auth", servers

    redirect = "http://app.local/oauth/callback"
    r = await client.post("/api/mcp/servers/notes/oauth/start", json={"redirect_uri": redirect})
    assert r.status_code == 200, r.text
    auth_url = r.json()["authorize_url"]
    q = parse_qs(urlparse(auth_url).query)
    assert q["code_challenge_method"] == ["S256"] and q["redirect_uri"] == [redirect]
    assert q["resource"] == [f"{oauth_mcp_url}/mcp"]

    # The user clicks "Allow" on the provider's page
    async with httpx.AsyncClient() as h:
        page = (await h.get(auth_url)).text
    allow = re.search(r'id="allow" href="([^"]+)"', page).group(1).replace("&amp;", "&")
    back = parse_qs(urlparse(allow).query)

    # The frontend callback page posts code + state to AI Chatbot Framework
    r = await client.post("/api/oauth/callback", json={"code": back["code"][0], "state": back["state"][0]})
    assert r.status_code == 200 and r.json()["server"] == "notes"
    replay = await client.post("/api/oauth/callback", json={"code": back["code"][0], "state": back["state"][0]})
    assert replay.status_code == 400

    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "connected" and servers[0]["signed_in"], servers
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, 'tool: mcp_call {"server": "notes", "tool": "get_secret_note"}')
    final = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][-1]
    assert "pineapple" in final["content"]

    await client.delete("/api/mcp/servers/notes/oauth")
    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "needs_auth"


async def test_token_refresh(client, user, oauth_mcp_url):
    """An expired access token is refreshed transparently."""
    import time

    from acf import oauth
    from acf.db import OAuthToken, session_scope

    cfg = {"mcpServers": {"notes": {"url": f"{oauth_mcp_url}/mcp"}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    r = await client.post(
        "/api/mcp/servers/notes/oauth/start", json={"redirect_uri": "http://app.local/oauth/callback"}
    )
    async with httpx.AsyncClient() as h:
        page = (await h.get(r.json()["authorize_url"])).text
    allow = re.search(r'id="allow" href="([^"]+)"', page).group(1).replace("&amp;", "&")
    back = parse_qs(urlparse(allow).query)
    await client.post("/api/oauth/callback", json={"code": back["code"][0], "state": back["state"][0]})

    with session_scope() as db:
        row = db.query(OAuthToken).filter_by(user_id=user["id"], server_name="notes").one()
        tokens = row.get("tokens_json")
        old = tokens["access_token"]
        tokens["expires_at"] = time.time() - 10
        row.put("tokens_json", tokens)
    new = await oauth.access_token(user["id"], "notes", f"{oauth_mcp_url}/mcp")
    assert new and new != old


async def test_unreachable_remote_server_has_friendly_error(client, user):
    cfg = {"mcpServers": {"gone": {"url": "http://127.0.0.1:1/mcp"}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    servers = (await client.get("/api/mcp/servers")).json()["servers"]
    assert servers[0]["state"] == "error"
    assert servers[0]["error"] == "Could not reach 127.0.0.1:1. Check the address."


async def _config(client) -> dict:
    return json.loads((await client.get("/api/mcp/config")).json()["config"])


async def test_add_edit_rename_delete_server(client, user):
    keep = {"mcpServers": {"first": {"command": "npx"}, "gh": {"url": "https://x/mcp", "oauth": {"client_id": "c"}}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(keep)})

    r = await client.put(
        "/api/mcp/servers/files",
        json={"transport": "stdio", "command": " npx ", "args": ["-y", "pkg"], "env": {"TOKEN": "t"}},
    )
    assert r.status_code == 200
    cfg = await _config(client)
    assert list(cfg["mcpServers"]) == ["first", "gh", "files"]
    assert cfg["mcpServers"]["files"] == {"command": "npx", "args": ["-y", "pkg"], "env": {"TOKEN": "t"}}

    # Editing a remote server keeps keys the form doesn't know (oauth), and can disable it.
    r = await client.put(
        "/api/mcp/servers/gh",
        json={"transport": "http", "url": "https://y/mcp", "headers": {"X-Api-Key": "k"}, "enabled": False},
    )
    assert r.status_code == 200
    assert (await _config(client))["mcpServers"]["gh"] == {
        "oauth": {"client_id": "c"},
        "url": "https://y/mcp",
        "headers": {"X-Api-Key": "k"},
        "enabled": False,
    }

    # Rename keeps position; clashes and unknown sources are rejected.
    assert (
        await client.put("/api/mcp/servers/gh", json={"transport": "stdio", "command": "x", "rename_from": "first"})
    ).status_code == 409
    assert (
        await client.put("/api/mcp/servers/new", json={"transport": "stdio", "command": "x", "rename_from": "nope"})
    ).status_code == 404
    r = await client.put(
        "/api/mcp/servers/local", json={"transport": "stdio", "command": "uvx", "rename_from": "first"}
    )
    assert r.status_code == 200
    assert list((await _config(client))["mcpServers"]) == ["local", "gh", "files"]

    # Invalid entries go through the same validation as the JSON editor.
    r = await client.put("/api/mcp/servers/bad", json={"transport": "http", "url": "ftp://x"})
    assert r.status_code == 400 and "must start with" in r.json()["detail"]
    assert (
        await client.put("/api/mcp/servers/bad%20name", json={"transport": "stdio", "command": "x"})
    ).status_code == 400
    assert (await client.put("/api/mcp/servers/empty", json={"transport": "stdio"})).status_code == 400

    assert (await client.delete("/api/mcp/servers/files")).status_code == 200
    assert (await client.delete("/api/mcp/servers/files")).status_code == 404
    assert list((await _config(client))["mcpServers"]) == ["local", "gh"]


async def test_delete_server_forgets_oauth_tokens(client, user):
    from acf import oauth
    from acf.db import OAuthToken, session_scope

    await client.put("/api/mcp/servers/notes", json={"transport": "http", "url": "https://x/mcp"})
    with session_scope() as db:
        db.add(OAuthToken(user_id=user["id"], server_name="notes", server_url="https://x/mcp"))
    assert (await client.delete("/api/mcp/servers/notes")).status_code == 200
    with session_scope() as db:
        assert oauth._row(db, user["id"], "notes") is None


async def test_presets_catalog_and_add(client, user):
    presets = (await client.get("/api/mcp/presets")).json()["presets"]
    by_id = {p["id"]: p for p in presets}
    assert {"linear", "notion"} <= set(by_id)
    assert by_id["linear"]["url"] == "https://mcp.linear.app/mcp" and not by_id["linear"]["added"]
    assert all(p["url"].startswith("https://") and p["name"] and p["description"] for p in presets)

    # keeps whatever the user already configured
    cfg = {"mcpServers": {"files": {"command": "npx", "args": ["x"]}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    r = await client.post("/api/mcp/presets/notion")
    assert r.status_code == 200, r.text
    servers = parse_config(r.json()["config"])
    assert servers["notion"].url == "https://mcp.notion.com/mcp" and "files" in servers
    assert (await client.get("/api/mcp/config")).json()["config"] == r.json()["config"]
    by_id = {p["id"]: p for p in (await client.get("/api/mcp/presets")).json()["presets"]}
    assert by_id["notion"]["added"] and not by_id["linear"]["added"]

    # adding twice is a no-op; a different server under the same name is a conflict
    assert (await client.post("/api/mcp/presets/notion")).status_code == 200
    cfg = {"mcpServers": {"linear": {"url": "https://example.com/other"}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    r = await client.post("/api/mcp/presets/linear")
    assert r.status_code == 409 and "already" in r.json()["detail"]
    assert (await client.post("/api/mcp/presets/nope")).status_code == 404


async def test_preset_from_file_signs_in(client, user, oauth_mcp_url, tmp_path, monkeypatch):
    from acf import config

    extra = tmp_path / "presets.json"
    notes = {"id": "notes", "name": "Notes", "description": "Test notes", "url": f"{oauth_mcp_url}/mcp"}
    extra.write_text(json.dumps([notes]))
    monkeypatch.setenv("ACF_MCP_PRESETS_FILE", str(extra))
    config.reload_settings()
    try:
        ids = [p["id"] for p in (await client.get("/api/mcp/presets")).json()["presets"]]
        assert "notes" in ids and "linear" in ids
        assert (await client.post("/api/mcp/presets/notes")).status_code == 200
        servers = (await client.get("/api/mcp/servers")).json()["servers"]
        assert servers[0]["name"] == "notes" and servers[0]["state"] == "needs_auth"
        r = await client.post("/api/mcp/servers/notes/oauth/start", json={"redirect_uri": "http://app.local/cb"})
        assert r.status_code == 200 and "code_challenge" in r.json()["authorize_url"]
    finally:
        monkeypatch.delenv("ACF_MCP_PRESETS_FILE")
        config.reload_settings()


def test_bad_presets_file_is_reported(tmp_path, monkeypatch):
    from acf import config, mcp_presets

    bad = tmp_path / "p.json"
    bad.write_text('[{"id": "x y", "name": "X", "url": "ftp://x"}]')
    monkeypatch.setenv("ACF_MCP_PRESETS_FILE", str(bad))
    config.reload_settings()
    try:
        try:
            mcp_presets.presets()
        except ValueError as e:
            assert "x y" in str(e)
        else:
            raise AssertionError("expected ValueError")
    finally:
        monkeypatch.delenv("ACF_MCP_PRESETS_FILE")
        config.reload_settings()
