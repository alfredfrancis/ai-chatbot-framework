from datetime import datetime, timedelta

from acf import scheduler
from acf.db import Task, session_scope, utcnow


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
