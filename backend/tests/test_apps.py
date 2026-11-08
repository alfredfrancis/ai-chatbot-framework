"""Personal apps: apps/<id>/app.json in the workspace, shown in the menu, driven by one action API."""

from __future__ import annotations

import asyncio
import json

from acf import workspace
from tests.conftest import send

COCKPIT = {
    "title": "Cockpit",
    "description": "What needs you",
    "files": ["assistant/todo.md"],
    "blocks": [
        {"type": "markdown", "title": "Brief", "file": "apps/cockpit/brief.md"},
        {
            "type": "board",
            "title": "To-do",
            "file": "apps/cockpit/tasks.json",
            "columns": [{"id": "do", "title": "Do first"}, {"id": "schedule", "title": "Schedule"}],
        },
        {"type": "buttons", "buttons": [{"label": "Refresh", "action": "ask_agent", "args": {"prompt": "hi"}}]},
    ],
}
TASKS = {"items": [{"id": "1", "title": "Book flights", "column": "do"}]}


def _install(user_id: int, app_id: str = "cockpit", spec: dict | None = None) -> None:
    workspace.write_file(user_id, f"apps/{app_id}/app.json", json.dumps(spec or {**COCKPIT, "title": app_id.title()}))


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
    workspace.write_file(user["id"], "apps/cockpit/brief.md", "# Today\nNothing needs you.")
    workspace.write_file(user["id"], "apps/cockpit/tasks.json", json.dumps(TASKS))

    assert (await client.get("/api/apps")).json() == [
        {"id": "cockpit", "title": "Cockpit", "description": "What needs you", "error": None}
    ]
    app = (await client.get("/api/apps/cockpit")).json()
    assert app["title"] == "Cockpit" and app["error"] is None and app["running"] is False
    brief, board, buttons = app["blocks"]
    assert brief["text"] == "# Today\nNothing needs you."
    assert board["data"] == TASKS
    assert buttons["buttons"][0]["label"] == "Refresh"


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


async def test_ordering_and_missing_data_files(client, user):
    _install(user["id"], "zed", {**COCKPIT, "title": "Zed", "order": 1})
    _install(user["id"], "abc", {**COCKPIT, "title": "Abc", "order": 2})
    assert [a["id"] for a in (await client.get("/api/apps")).json()] == ["zed", "abc"]
    app = (await client.get("/api/apps/zed")).json()
    assert app["blocks"][0]["text"] == "" and app["blocks"][1]["data"] == {"items": []}


async def test_update_file_writes_the_app_folder_and_declared_files_only(client, user):
    _install(user["id"])
    r = await _action(client, "cockpit", "update_file", path="apps/cockpit/tasks.json", content=json.dumps(TASKS))
    assert r.status_code == 200, r.text
    assert json.loads(workspace.read_file(user["id"], "apps/cockpit/tasks.json")) == TASKS
    r = await _action(client, "cockpit", "update_file", path="assistant/todo.md", content="- [ ] call mum\n")
    assert r.status_code == 200
    assert workspace.read_file(user["id"], "assistant/todo.md") == "- [ ] call mum\n"
    for path in ["memory.md", "apps/other/app.json", "apps/cockpit/../../memory.md", "../escape"]:
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
    assert app["blocks"][0]["text"] == "Updated by the agent"
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
    assert json.loads(r.json()["output"]) == []
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
