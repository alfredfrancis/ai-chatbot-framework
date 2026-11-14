"""Personal apps: apps/<id>/app.json in the workspace, shown in the menu, driven by one action API."""

from __future__ import annotations

import asyncio
import json

from acf import skills, workspace
from tests.conftest import send

COCKPIT = {"title": "Cockpit", "description": "What needs you", "files": ["assistant/todo.md"]}
SCREEN = """root = Screen([needs, todo])
brief = Query("read_file", {path: "apps/cockpit/brief.md"}, {text: ""}, 10)
needs = Card("Needs you", [Text(brief.text)])
todo = Board("To-do", "apps/cockpit/tasks.json", [{id: "do", title: "Do first"}])
"""
TASKS = {"items": [{"id": "1", "title": "Book flights", "column": "do"}]}


def _install(user_id: int, app_id: str = "cockpit", spec: dict | None = None) -> None:
    workspace.write_file(user_id, f"apps/{app_id}/app.json", json.dumps(spec or {**COCKPIT, "title": app_id.title()}))
    workspace.write_file(user_id, f"apps/{app_id}/app.oui", SCREEN)


async def _action(client, app_id: str, action: str, **args):
    return await client.post(f"/api/apps/{app_id}/actions", json={"action": action, "args": args})


async def _wait_idle(client, app_id: str) -> dict:
    for _ in range(200):
        app = (await client.get(f"/api/apps/{app_id}")).json()
        if not app["running"]:
            return app
        await asyncio.sleep(0.05)
    raise AssertionError("the app's agent run did not finish")


async def test_agent_creates_an_app_that_the_menu_lists(client, user):
    chat = (await client.post("/api/chats", json={})).json()
    await send(client, chat["id"], "write: apps/cockpit/app.json | " + json.dumps(COCKPIT))
    assert (await client.get("/api/apps")).json()[0]["error"] == (
        "apps/cockpit/app.oui is missing: write the screen in OpenUI Lang."
    )
    await send(client, chat["id"], "write: apps/cockpit/app.oui | " + SCREEN)

    assert (await client.get("/api/apps")).json() == [
        {"id": "cockpit", "title": "Cockpit", "description": "What needs you", "error": None}
    ]
    app = (await client.get("/api/apps/cockpit")).json()
    assert app["title"] == "Cockpit" and app["error"] is None and app["running"] is False
    assert app["source"] == SCREEN.strip()


async def test_read_file_returns_text_and_json(client, user):
    _install(user["id"])
    workspace.write_file(user["id"], "apps/cockpit/brief.md", "# Today")
    workspace.write_file(user["id"], "apps/cockpit/tasks.json", json.dumps(TASKS))
    r = (await _action(client, "cockpit", "read_file", path="apps/cockpit/brief.md")).json()
    assert r["text"] == "# Today" and r["data"] is None
    r = (await _action(client, "cockpit", "read_file", path="apps/cockpit/tasks.json")).json()
    assert r["data"] == TASKS
    assert (await _action(client, "cockpit", "read_file", path="apps/cockpit/none.md")).json()["text"] == ""
    assert (await _action(client, "cockpit", "read_file", path="memory.md")).status_code == 400


async def test_at_most_five_apps_and_bad_specs_are_reported(client, user):
    for name in ["a1", "a2", "a3", "a4", "a5", "a6"]:
        _install(user["id"], name)
    workspace.write_file(user["id"], "apps/a0/app.json", "{not json")
    apps = (await client.get("/api/apps")).json()
    assert [a["id"] for a in apps] == ["a0", "a1", "a2", "a3", "a4"]
    assert apps[0]["error"] and "app.json" in apps[0]["error"]
    assert (await client.get("/api/apps/a0")).json()["error"]
    assert (await client.get("/api/apps/a6")).status_code == 404
    assert (await client.get("/api/apps/nope")).status_code == 404
    assert (await client.get("/api/apps/..%2Fskills")).status_code == 404


async def test_ordering(client, user):
    _install(user["id"], "zed", {**COCKPIT, "title": "Zed", "order": 1})
    _install(user["id"], "abc", {**COCKPIT, "title": "Abc", "order": 2})
    assert [a["id"] for a in (await client.get("/api/apps")).json()] == ["zed", "abc"]


async def test_update_file_writes_the_app_folder_and_declared_files_only(client, user):
    _install(user["id"])
    r = await _action(client, "cockpit", "update_file", path="apps/cockpit/tasks.json", content=json.dumps(TASKS))
    assert r.status_code == 200, r.text
    assert json.loads(workspace.read_file(user["id"], "apps/cockpit/tasks.json")) == TASKS
    r = await _action(client, "cockpit", "update_file", path="assistant/todo.md", content="- [ ] call mum\n")
    assert r.status_code == 200
    assert workspace.read_file(user["id"], "assistant/todo.md") == "- [ ] call mum\n"
    for path in [
        "memory.md",
        "apps/cockpit/app.json",
        "apps/cockpit/app.oui",
        "apps/other/app.json",
        "apps/cockpit/../../memory.md",
        "../escape",
    ]:
        r = await _action(client, "cockpit", "update_file", path=path, content="x")
        assert r.status_code == 400, path
    assert "x" != workspace.read_file(user["id"], "memory.md")


async def test_ask_agent_runs_in_the_apps_own_chat(client, user):
    _install(user["id"])
    prompt = "write: apps/cockpit/brief.md | Updated by the agent"
    r = await _action(client, "cockpit", "ask_agent", prompt=prompt, event='Moved "Book flights" to Schedule.')
    assert r.status_code == 200, r.text
    chat_id = r.json()["chat_id"]
    app = await _wait_idle(client, "cockpit")
    assert app["chat_id"] == chat_id
    assert workspace.read_file(user["id"], "apps/cockpit/brief.md") == "Updated by the agent"
    msgs = (await client.get(f"/api/chats/{chat_id}")).json()["messages"]
    first = msgs[0]["content"]
    assert first.startswith("[App: Cockpit, apps/cockpit/app.json]") and 'Moved "Book flights"' in first
    assert first.endswith(prompt)
    # The same chat is reused for the next action.
    r = await _action(client, "cockpit", "ask_agent", prompt="hello again")
    assert r.json()["chat_id"] == chat_id
    await _wait_idle(client, "cockpit")
    assert (await client.get(f"/api/chats/{chat_id}")).json()["title"] == "Cockpit app"


async def test_mcp_action_runs_read_only_tools_only(client, user):
    _install(user["id"])
    r = await _action(client, "cockpit", "mcp", server="system", tool="list_tasks", arguments={})
    assert r.status_code == 200, r.text
    assert r.json()["data"] == [] and r.json()["text"].strip() == "[]"
    r = await _action(
        client,
        "cockpit",
        "mcp",
        server="system",
        tool="create_task",
        arguments={"name": "x", "prompt": "x", "schedule": "0 9 * * *", "timezone": "UTC"},
    )
    assert r.status_code == 400 and "ask_agent" in r.json()["detail"]
    assert (await client.get("/api/tasks")).json() == []
    r = await _action(client, "cockpit", "mcp", server="nope", tool="x")
    assert r.status_code == 400


async def test_run_action_executes_an_app_script_in_the_sandbox(client, user):
    _install(user["id"])
    script = 'printf "%s" "$1" > apps/cockpit/last.json\necho "got it"\n'
    workspace.write_file(user["id"], "apps/cockpit/actions/save.sh", script)
    r = await _action(client, "cockpit", "run", script="save", input={"n": 1})
    assert r.status_code == 200, r.text
    assert r.json()["output"].strip() == "got it"
    assert json.loads(workspace.read_file(user["id"], "apps/cockpit/last.json")) == {"n": 1}
    workspace.write_file(user["id"], "apps/cockpit/actions/fail.sh", "echo bad >&2\nexit 3\n")
    r = await _action(client, "cockpit", "run", script="fail")
    assert r.status_code == 400 and "bad" in r.json()["detail"]
    for name in ["missing", "../../x", "a b"]:
        assert (await _action(client, "cockpit", "run", script=name)).status_code == 400


async def test_unknown_actions_and_other_users_apps(client, user):
    _install(user["id"])
    assert (await _action(client, "cockpit", "delete_everything")).status_code == 422
    await client.post("/api/auth/logout")
    r = await client.post("/api/auth/signup", json={"email": "other-apps@example.com", "password": "correct horse"})
    assert r.status_code == 200
    assert (await client.get("/api/apps")).json() == []
    assert (await client.get("/api/apps/cockpit")).status_code == 404
    assert (await _action(client, "cockpit", "update_file", path="apps/cockpit/x", content="x")).status_code == 404


async def test_system_prompt_tells_the_agent_about_apps(client, user):
    chat = (await client.post("/api/chats", json={})).json()
    text = (await send(client, chat["id"], "show system")).final
    assert "apps/" in text and "personal-apps" in text


async def test_the_openui_skill_ships_the_generated_reference(client, user):
    ref = workspace.read_file(user["id"], "skills/openui/reference.md")
    assert "Generated from frontend/src/openui/library.tsx" in ref
    for signature in (
        "Screen(children",
        "Board(title: string, file: string",
        "BarChart(title: string, labels: string[]",
        "PieChart(title: string, slices",
        "Tabs(tabs: Tab[])",
        "Slider(label: string, value?: $binding<number>",
        "Query(",
        "Mutation(",
        "@ToAssistant",
        "```openui",
    ):
        assert signature in ref, signature
    skill = workspace.read_file(user["id"], "skills/openui/SKILL.md")
    assert "reference.md" in skill and "```openui" in skill


async def test_personal_apps_refers_to_the_openui_skill(client, user):
    text = workspace.read_file(user["id"], "skills/personal-apps/SKILL.md")
    assert "skills/openui/SKILL.md" in text
    assert not (skills.skills_root(user["id"]) / "personal-apps" / "openui.md").exists()


async def test_system_prompt_points_to_openui_views(client, user):
    chat = (await client.post("/api/chats", json={})).json()
    text = (await send(client, chat["id"], "show system")).final
    assert "skills/openui/SKILL.md" in text


async def test_the_apps_chat_is_made_once_and_tells_the_agent_which_app_it_controls(client, user):
    _install(user["id"])
    r = await client.post("/api/apps/cockpit/chat")
    assert r.status_code == 200, r.text
    chat_id = r.json()["chat_id"]
    assert (await client.post("/api/apps/cockpit/chat")).json()["chat_id"] == chat_id
    assert (await client.get("/api/apps/cockpit")).json()["chat_id"] == chat_id
    assert (await client.get(f"/api/chats/{chat_id}")).json()["title"] == "Cockpit app"
    # ask_agent from the screen uses the same chat.
    r = await _action(client, "cockpit", "ask_agent", prompt="reply: ok")
    assert r.json()["chat_id"] == chat_id
    await _wait_idle(client, "cockpit")

    # A plain message in the app's chat (the sidebar) knows which app it changes.
    text = (await send(client, chat_id, "show system")).final
    assert '<app id="cockpit" title="Cockpit">' in text and "apps/cockpit/app.oui" in text
    # Other chats don't get the app section.
    other = (await client.post("/api/chats", json={})).json()
    assert "<app id=" not in (await send(client, other["id"], "show system")).final

    # The chat follows the app: a plain message edits its screen.
    new = SCREEN.replace("Needs you", "Today")
    await send(client, chat_id, "write: apps/cockpit/app.oui | " + new)
    assert (await client.get("/api/apps/cockpit")).json()["source"] == new.strip()

    assert (await client.post("/api/apps/nope/chat")).status_code == 404
    workspace.write_file(user["id"], "apps/broken/app.json", "{not json")
    assert (await client.post("/api/apps/broken/chat")).status_code == 400


async def test_a_deleted_app_chat_is_made_again(client, user):
    _install(user["id"])
    chat_id = (await client.post("/api/apps/cockpit/chat")).json()["chat_id"]
    assert (await client.delete(f"/api/chats/{chat_id}")).status_code == 200
    assert (await client.get("/api/apps/cockpit")).json()["chat_id"] is None
    # A new chat (which may get the deleted chat's id) is not the app's chat.
    other = (await client.post("/api/chats", json={})).json()
    assert "<app id=" not in (await send(client, other["id"], "show system")).final
    again = (await client.post("/api/apps/cockpit/chat")).json()["chat_id"]
    assert again != other["id"]
    assert (await client.get("/api/apps/cockpit")).json()["chat_id"] == again


async def test_a_client_with_the_apps_chat_open_follows_runs_the_screen_starts(client, user):
    from tests.acp_client import acp_connect

    _install(user["id"])
    sid = str((await client.post("/api/apps/cockpit/chat")).json()["chat_id"])
    async with acp_connect(client) as acp:
        await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        r = await _action(client, "cockpit", "ask_agent", prompt="write: apps/cockpit/brief.md | From the screen")
        assert r.json()["queued"] is False
        await acp.wait_for(lambda n: n.get("method") == "_acf/turn_end" and n["params"]["sessionId"] == sid)
        updates = acp.updates(sid)
    texts = [u["content"].get("text", "") for u in updates if u["sessionUpdate"] == "user_message_chunk"]
    assert texts and texts[0].startswith("[App: Cockpit, apps/cockpit/app.json] The user pressed a button.")
    done = [u for u in updates if u["sessionUpdate"] == "tool_call_update" and u.get("status") == "completed"]
    assert done, "the panel hears when the agent's write is done"
    assert workspace.read_file(user["id"], "apps/cockpit/brief.md") == "From the screen"
