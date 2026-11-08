import json
from datetime import datetime, timedelta

from acf import scheduler, workspace
from acf.db import Task, User, session_scope, utcnow
from tests.conftest import send


async def test_create_validate_update_delete(client, user):
    bad = await client.post("/api/tasks", json={"name": "x", "prompt": "y", "schedule": "every day"})
    assert bad.status_code == 400
    bad_tz = await client.post(
        "/api/tasks", json={"name": "x", "prompt": "y", "schedule": "0 9 * * *", "timezone": "Mars/Base"}
    )
    assert bad_tz.status_code == 400

    r = await client.post(
        "/api/tasks",
        json={"name": "Briefing", "prompt": "hello", "schedule": "0 8 * * 1-5", "timezone": "Europe/Lisbon"},
    )
    assert r.status_code == 200, r.text
    task = r.json()
    nxt = datetime.fromisoformat(task["next_run_at"].rstrip("Z"))
    assert nxt > utcnow() and nxt.weekday() < 5

    off = (await client.patch(f"/api/tasks/{task['id']}", json={"enabled": False})).json()
    assert off["enabled"] is False and off["next_run_at"] is None
    assert len((await client.get("/api/tasks")).json()) == 1
    await client.delete(f"/api/tasks/{task['id']}")
    assert (await client.get("/api/tasks")).json() == []


async def test_run_now_creates_chat(client, user):
    task = (
        await client.post("/api/tasks", json={"name": "Calc", "prompt": "run: echo $((2+3))", "schedule": "0 * * * *"})
    ).json()
    r = await client.post(f"/api/tasks/{task['id']}/run")
    assert r.status_code == 200
    chat_id = r.json()["chat_id"]
    # wait for completion
    import asyncio

    for _ in range(100):
        t = next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task["id"])
        if t["last_status"] in ("ok", "error"):
            break
        await asyncio.sleep(0.05)
    assert t["last_status"] == "ok" and t["last_chat_id"] == chat_id
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert chat["task_id"] == task["id"] and chat["title"].startswith("Calc · ")
    assert chat["messages"][-1]["content"].startswith("Result: 5")


async def test_scheduler_tick_runs_due_tasks(client, user):
    import asyncio

    task = (await client.post("/api/tasks", json={"name": "Due", "prompt": "hi", "schedule": "*/5 * * * *"})).json()
    with session_scope() as db:
        db.get(Task, task["id"]).next_run_at = utcnow() - timedelta(minutes=1)
    started = await scheduler.tick()
    assert task["id"] in started
    for _ in range(100):
        t = next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task["id"])
        if t["last_status"] == "ok":
            break
        await asyncio.sleep(0.05)
    assert t["last_status"] == "ok"
    assert datetime.fromisoformat(t["next_run_at"].rstrip("Z")) > utcnow()
    assert task["id"] not in await scheduler.tick()  # not due again


async def test_task_chat_reports_running_while_in_progress(client, user):
    """The UI polls a task's chat while it runs, so the chat must say it is running."""
    import asyncio

    task = (
        await client.post(
            "/api/tasks",
            json={"name": "Slow", "prompt": "run: sleep 1; echo slow-done", "schedule": "0 * * * *"},
        )
    ).json()
    r = (await client.post(f"/api/tasks/{task['id']}/run")).json()
    assert r["status"] == "running"
    chat = (await client.get(f"/api/chats/{r['chat_id']}")).json()
    assert chat["running"] is True
    for _ in range(100):
        chat = (await client.get(f"/api/chats/{r['chat_id']}")).json()
        if not chat["running"]:
            break
        await asyncio.sleep(0.1)
    assert chat["messages"][-1]["content"].startswith("Result: slow-done")


async def test_long_task_name_fits_the_chat_title(client, user):
    """Chat titles are limited in the database (PostgreSQL enforces it); long task names are cut."""
    name = "N" * 200
    task = (await client.post("/api/tasks", json={"name": name, "prompt": "hi", "schedule": "0 * * * *"})).json()
    r = await client.post(f"/api/tasks/{task['id']}/run")
    assert r.status_code == 200
    chat = (await client.get(f"/api/chats/{r.json()['chat_id']}")).json()
    assert chat["title"].startswith("N" * 180 + " · ") and len(chat["title"]) <= 200
    too_long = await client.post("/api/tasks", json={"name": "x" * 201, "prompt": "hi", "schedule": "0 * * * *"})
    assert too_long.status_code == 422


def _call(tool: str, **arguments) -> str:
    return "tool: mcp_call " + json.dumps({"server": "system", "tool": tool, "arguments": arguments})


async def test_agent_manages_tasks_with_the_system_server(client, user):
    """The built-in `system` MCP server is always connected and lets the agent schedule tasks."""
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    system = (await send(client, chat_id, "show system")).final
    assert "system: create_task, delete_task, list_tasks, run_task, update_task" in system.splitlines()
    definition = json.loads(workspace.read_file(user["id"], ".acf/mcp/system/create_task.json"))
    assert set(definition["input_schema"]["required"]) == {"name", "prompt", "timezone"}
    assert {"schedule", "run_at"} <= set(definition["input_schema"]["properties"])

    turn = await send(
        client,
        chat_id,
        _call("create_task", name="Briefing", prompt="hello", schedule="0 8 * * 1-5", timezone="Europe/Lisbon"),
    )
    assert turn.of("tool_call")[0]["title"] == "Used system · create_task"
    [task] = (await client.get("/api/tasks")).json()
    assert task["name"] == "Briefing" and task["enabled"] and task["next_run_at"]

    bad = await send(client, chat_id, _call("create_task", name="x", prompt="y", schedule="daily", timezone="UTC"))
    assert "5-field cron expression" in bad.final
    assert len((await client.get("/api/tasks")).json()) == 1

    await send(client, chat_id, _call("update_task", task_id=task["id"], enabled=False))
    paused = (await client.get("/api/tasks")).json()[0]
    assert paused["enabled"] is False and paused["next_run_at"] is None and paused["prompt"] == "hello"
    assert '"name": "Briefing"' in (await send(client, chat_id, _call("list_tasks"))).final

    await send(client, chat_id, _call("delete_task", task_id=task["id"]))
    assert (await client.get("/api/tasks")).json() == []


async def test_system_server_only_sees_the_users_own_tasks(client, user):
    with session_scope() as db:
        someone = User(email=f"other-{user['id']}@example.com", password_hash="x")
        db.add(someone)
        db.flush()
        other = Task(user_id=someone.id, name="Not yours", prompt="p", schedule="0 * * * *")
        db.add(other)
        db.flush()
        other_id = other.id
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    assert "Not yours" not in (await send(client, chat_id, _call("list_tasks"))).final
    for tool in ("update_task", "delete_task", "run_task"):
        args = {"task_id": other_id, **({"enabled": False} if tool == "update_task" else {})}
        assert f"No task with id {other_id}" in (await send(client, chat_id, _call(tool, **args))).final
    with session_scope() as db:
        assert db.get(Task, other_id).enabled is True


async def test_system_is_a_reserved_server_name(client, user):
    cfg = '{"mcpServers": {"system": {"command": "x"}}}'
    r = await client.put("/api/mcp/config", json={"config": cfg})
    assert r.status_code == 400 and "built-in" in r.text


async def test_one_off_task_runs_once_then_turns_itself_off(client, user):
    import asyncio

    # Local time in the task's time zone: 09:30 in Lisbon in winter is 09:30 UTC, in Tokyo 00:30 UTC.
    day = (utcnow() + timedelta(days=2)).date().isoformat()
    r = await client.post(
        "/api/tasks", json={"name": "Remind", "prompt": "hi", "run_at": f"{day}T09:30", "timezone": "Asia/Tokyo"}
    )
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["schedule"] == "" and task["run_at"] == f"{day}T00:30:00Z" == task["next_run_at"]

    for body, msg in [
        ({"run_at": "2020-01-01T09:00"}, "in the past"),
        ({"run_at": "tomorrow"}, "date and time"),
        ({"run_at": f"{day}T09:30", "schedule": "0 9 * * *"}, "not both"),
        ({}, "Give a schedule"),
    ]:
        bad = await client.post("/api/tasks", json={"name": "x", "prompt": "y", **body})
        assert bad.status_code == 400 and msg in bad.text, (body, bad.text)

    with session_scope() as db:
        db.get(Task, task["id"]).next_run_at = utcnow() - timedelta(minutes=1)  # it is due
    assert task["id"] in await scheduler.tick()
    for _ in range(100):
        t = next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task["id"])
        if t["last_status"] == "ok":
            break
        await asyncio.sleep(0.05)
    assert t["last_status"] == "ok" and t["enabled"] is False and t["next_run_at"] is None
    assert task["id"] not in await scheduler.tick()

    with session_scope() as db:
        db.get(Task, task["id"]).run_at = utcnow() - timedelta(minutes=1)  # its time has passed
    again = await client.patch(f"/api/tasks/{task['id']}", json={"enabled": True})
    assert again.status_code == 400 and "in the past" in again.text
    moved = (await client.patch(f"/api/tasks/{task['id']}", json={"enabled": True, "run_at": f"{day}T10:00"})).json()
    assert moved["enabled"] and moved["next_run_at"] == f"{day}T01:00:00Z"
    repeating = (await client.patch(f"/api/tasks/{task['id']}", json={"schedule": "0 9 * * *"})).json()
    assert repeating["run_at"] is None and repeating["schedule"] == "0 9 * * *"


async def test_agent_schedules_a_one_off_task(client, user):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    day = (utcnow() + timedelta(days=1)).date().isoformat()
    turn = await send(
        client,
        chat_id,
        _call("create_task", name="Call mum", prompt="Remind me", run_at=f"{day}T17:00", timezone="UTC"),
    )
    assert '"schedule": ""' in turn.final
    [task] = (await client.get("/api/tasks")).json()
    assert task["run_at"] == f"{day}T17:00:00Z" and task["enabled"]
