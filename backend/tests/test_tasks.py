import asyncio
import json
from datetime import datetime, timedelta

import pytest

from acf import config, scheduler, workspace
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


async def test_due_tasks_start_even_when_recovery_fails(client, user, monkeypatch):
    task = (await client.post("/api/tasks", json={"name": "Due", "prompt": "hi", "schedule": "*/5 * * * *"})).json()
    with session_scope() as db:
        db.get(Task, task["id"]).next_run_at = utcnow() - timedelta(minutes=1)

    async def broken() -> None:
        raise ConnectionError("Redis went away")

    monkeypatch.setattr(scheduler, "recover", broken)
    assert task["id"] in await scheduler.tick()
    await _finished(client, task["id"])


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


async def _finished(client, task_id: int) -> dict:
    import asyncio

    for _ in range(100):
        t = next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task_id)
        if t["last_status"] in ("ok", "error"):
            return t
        await asyncio.sleep(0.05)
    return t


async def test_a_task_runs_on_its_own_model(client, user, fake_llm_url):
    """A task can name a model (e.g. a small local one for background jobs); its runs use it, chats don't."""
    await client.patch("/api/settings/models", json={"key": "anthropic:claude-haiku-5-5", "enabled": False})
    for model in ("anthropic:claude-haiku-5-5", "nope:nothing", "anthropic:not-in-the-list"):
        bad = await client.post(
            "/api/tasks", json={"name": "x", "prompt": "y", "schedule": "0 * * * *", "model": model}
        )
        assert bad.status_code == 400 and "Unknown model" in bad.text, (model, bad.text)

    # A model of one's own on an OpenAI-compatible server, like llama-server on a Raspberry Pi.
    await client.put("/api/settings/providers/openai", json={"base_url": f"{fake_llm_url}/v1", "api_key": "k"})
    await client.post("/api/settings/models", json={"provider": "openai", "id": "qwen3.5-4b"})
    r = await client.post(
        "/api/tasks",
        json={"name": "Hourly", "prompt": "show model", "schedule": "0 * * * *", "model": "openai:qwen3.5-4b"},
    )
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["model"] == "openai:qwen3.5-4b"

    chat_id = (await client.post(f"/api/tasks/{task['id']}/run")).json()["chat_id"]
    assert (await _finished(client, task["id"]))["last_status"] == "ok"
    assert (await client.get(f"/api/chats/{chat_id}")).json()["messages"][-1]["content"] == "Model: qwen3.5-4b"
    # A plain chat still uses the default model.
    plain = (await client.post("/api/chats", json={})).json()["id"]
    assert (await send(client, plain, "show model")).final == "Model: claude-opus-5-5"

    # "" goes back to the user's default; a bad model is refused on a change too.
    bad = await client.patch(f"/api/tasks/{task['id']}", json={"model": "anthropic:claude-haiku-5-5"})
    assert bad.status_code == 400 and "Unknown model" in bad.text
    reset = (await client.patch(f"/api/tasks/{task['id']}", json={"model": ""})).json()
    assert reset["model"] == ""
    chat_id = (await client.post(f"/api/tasks/{task['id']}/run")).json()["chat_id"]
    await _finished(client, task["id"])
    assert (await client.get(f"/api/chats/{chat_id}")).json()["messages"][-1]["content"] == "Model: claude-opus-5-5"


async def test_agent_picks_a_tasks_model(client, user):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    await send(client, chat_id, "show system")  # connects the system server, which writes its tool files
    for tool in ("create_task", "update_task"):
        definition = json.loads(workspace.read_file(user["id"], f".acf/mcp/system/{tool}.json"))
        assert "model" in definition["input_schema"]["properties"]
    args = {"name": "Digest", "prompt": "p", "schedule": "0 9 * * *", "timezone": "UTC"}
    await send(client, chat_id, _call("create_task", **args, model="anthropic:claude-sonnet-5-5"))
    [task] = (await client.get("/api/tasks")).json()
    assert task["model"] == "anthropic:claude-sonnet-5-5"
    bad = await send(client, chat_id, _call("update_task", task_id=task["id"], model="nope:nothing"))
    assert "Unknown model" in bad.final
    await send(client, chat_id, _call("update_task", task_id=task["id"], model=""))
    assert (await client.get("/api/tasks")).json()[0]["model"] == ""


async def _left_running(client, **fields) -> tuple[int, int]:
    """A task marked running for a chat, as a runner leaves it when its process dies mid-run. Recovery
    acts at the first sighting of the free lock here (no grace); the grace has its own test."""
    config.settings.bus_ttl = 0
    body = {"name": "Report", "prompt": "hi", "schedule": "0 9 * * *", **fields}
    r = await client.post("/api/tasks", json=body)
    assert r.status_code == 200, r.text
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    with session_scope() as db:
        t = db.get(Task, r.json()["id"])
        t.last_status, t.last_run_at, t.last_chat_id = "running", utcnow(), chat_id
    return r.json()["id"], chat_id


async def _task(client, task_id: int) -> dict:
    return next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task_id)


async def _notes(client, chat_id: int) -> list[str]:
    return [m["content"] for m in (await client.get(f"/api/chats/{chat_id}")).json()["messages"] if m["role"] == "note"]


async def test_dead_runners_task_is_marked_stopped(client, user):
    task_id, chat_id = await _left_running(client)
    await scheduler.tick()
    assert (await _task(client, task_id))["last_status"] == "stopped"
    await scheduler.tick()
    assert await _notes(client, chat_id) == [
        "The server running this task stopped before the agent finished. It runs again at its next scheduled time."
    ]


async def test_a_lock_free_only_briefly_does_not_stop_a_run(client, user):
    """After a Redis restart every lock is free until its holder's heartbeat takes it back: a run is stopped
    only once its lock has stayed free for bus_ttl/2, and a lock seen held again starts the wait over."""
    from acf import bus

    task_id, chat_id = await _left_running(client)
    config.settings.bus_ttl = 0.6
    await scheduler.tick()  # free: first sighting
    assert (await _task(client, task_id))["last_status"] == "running"
    assert await bus.current().lock(f"task:{task_id}")  # the heartbeat took it back
    await scheduler.tick()
    await bus.current().unlock(f"task:{task_id}")
    await asyncio.sleep(0.35)
    await scheduler.tick()  # free again, but the earlier sighting was forgotten
    assert (await _task(client, task_id))["last_status"] == "running"
    await asyncio.sleep(0.35)
    await scheduler.tick()
    assert (await _task(client, task_id))["last_status"] == "stopped"
    assert len(await _notes(client, chat_id)) == 1


@pytest.mark.parametrize("skew", [60, -60])
async def test_the_grace_holds_whatever_the_replicas_clocks_say(client, user, redis_url, skew, monkeypatch):
    """Replica A, its clock `skew` seconds off, sights the free lock first; replica B, its clock right,
    decides. The run is stopped once the grace has passed by Redis's clock, not before and not never."""
    import types
    import uuid

    from acf import bus

    shared = bus.RedisBus(redis_url, f"acf-test-{uuid.uuid4().hex[:8]}", ttl=0.6)
    await shared.start()
    bus.use(shared)
    try:
        task_id, _ = await _left_running(client)
        config.settings.bus_ttl = 0.6  # grace 0.3 s
        real = bus.time
        monkeypatch.setattr(bus, "time", types.SimpleNamespace(time=lambda: real.time() + skew))
        await scheduler.tick()  # replica A: the first sighting
        monkeypatch.setattr(bus, "time", real)
        await scheduler.tick()  # replica B, at once: within the grace
        assert (await _task(client, task_id))["last_status"] == "running"
        await asyncio.sleep(0.4)
        await scheduler.tick()  # replica B, past the grace
        assert (await _task(client, task_id))["last_status"] == "stopped"
    finally:
        bus.use(None)
        await shared.close()


async def test_task_a_live_process_runs_is_not_marked_stopped(client, user):
    """A runner takes the task's lock before it says "running": while the lock is held, the run is alive."""
    from acf import bus

    task_id, chat_id = await _left_running(client)
    assert await bus.current().lock(f"task:{task_id}")
    try:
        await scheduler.tick()
    finally:
        await bus.current().unlock(f"task:{task_id}")
    assert (await _task(client, task_id))["last_status"] == "running"
    assert await _notes(client, chat_id) == []


async def test_a_run_that_starts_while_recovery_looks_is_not_marked_stopped(client, user, monkeypatch):
    """Recovery finds the lock free, then a new run takes it and says "running" for its own chat."""
    from acf import bus

    task_id, old_chat = await _left_running(client)
    new_chat = (await client.post("/api/chats", json={})).json()["id"]
    free = bus.current().locked

    async def new_run_starts_right_after(names) -> set[str]:
        was = await free(names)
        with session_scope() as db:
            db.get(Task, task_id).last_chat_id = new_chat
        return was

    monkeypatch.setattr(bus.current(), "locked", new_run_starts_right_after)
    await scheduler.tick()
    assert (await _task(client, task_id))["last_status"] == "running"
    assert await _notes(client, old_chat) == [] and await _notes(client, new_chat) == []


async def test_a_run_that_says_running_while_recovery_stops_the_old_one_stays_running(client, user):
    """Recovery stops the dead run in X just before a new run's "running" for Y is written. The task
    must end as running Y: a run that shows as stopped can't be seen by Run now, which then waits on it."""
    from sqlalchemy import event

    from acf import db

    task_id, old_chat = await _left_running(client)
    new_chat = (await client.post("/api/chats", json={})).json()["id"]
    notes: list = []

    def recovery_commits_first(conn, cursor, statement, *args):
        if not notes and statement.startswith("UPDATE tasks"):
            notes.append(None)  # once: recovery's own UPDATE comes through here too
            notes[0] = scheduler._stop(task_id, old_chat)

    event.listen(db._engine, "before_cursor_execute", recovery_commits_first)
    try:
        scheduler._set(task_id, last_status="running", last_run_at=utcnow(), last_chat_id=new_chat)
    finally:
        event.remove(db._engine, "before_cursor_execute", recovery_commits_first)
    assert notes and notes[0] is not None  # recovery did stop the old run in between
    task = await _task(client, task_id)
    assert (task["last_status"], task["last_chat_id"]) == ("running", new_chat)


async def test_stopped_one_off_task_is_not_run_again(client, user):
    day = (utcnow() + timedelta(days=2)).date().isoformat()
    task_id, chat_id = await _left_running(client, schedule="", run_at=f"{day}T09:30")
    with session_scope() as db:
        t = db.get(Task, task_id)
        t.enabled, t.next_run_at = False, None  # as the tick that started it left it
    assert task_id not in await scheduler.tick()
    task = await _task(client, task_id)
    assert task["last_status"] == "stopped" and not task["enabled"] and task["next_run_at"] is None
    assert (await _notes(client, chat_id))[0].endswith("Use Run now to run it again.")


async def test_processes_recovering_at_once_write_one_note(client, user):
    import asyncio

    task_id, chat_id = await _left_running(client)
    await asyncio.gather(scheduler.tick(), scheduler.tick(), scheduler.tick())
    assert (await _task(client, task_id))["last_status"] == "stopped"
    assert len(await _notes(client, chat_id)) == 1


async def test_a_hung_database_does_not_stop_the_event_loop(client, user):
    """The scheduler waits for the database in a thread, so liveness and other requests go on meanwhile."""
    import asyncio
    import threading
    import time

    from sqlalchemy import event

    from acf import db

    hang = threading.Event()

    def slow(conn, cursor, statement, *args):
        if hang.is_set() and "tasks" in statement:
            time.sleep(1.0)

    event.listen(db._engine, "before_cursor_execute", slow)
    hang.set()
    try:
        tick = asyncio.create_task(scheduler.tick())
        started = time.monotonic()
        r = await client.get("/api/health")
        answered = time.monotonic() - started
        await tick
    finally:
        hang.clear()
        event.remove(db._engine, "before_cursor_execute", slow)
    assert r.status_code == 200 and answered < 0.5, answered
