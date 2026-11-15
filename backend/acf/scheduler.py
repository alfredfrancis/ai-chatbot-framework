"""Tasks: a prompt + when to run it, either a cron schedule (recurring) or a single time (`run_at`, one-off).
Each run creates a new chat with the result. A one-off task turns itself off once it has started.
A task made for a project (`project_id`) runs as a chat in that project, with the project's instructions.
A task with a `model` runs on that model (e.g. a small local one for background jobs); "" = the user's default.

Every app process runs the scheduler. A due task is claimed by moving its next_run_at with a
compare-and-set update, so exactly one process starts it. A run whose process died is marked stopped on
the next tick of any process."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy.orm import Session

from acf import bus, config, logs, models, projects
from acf.agent import loop as agent
from acf.db import Chat, Message, Task, User, session_scope, utcnow

log = logging.getLogger("acf.scheduler")


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"Unknown time zone: {tz}") from e


def validate(schedule: str, tz: str) -> None:
    if not croniter.is_valid(schedule) or len(schedule.split()) != 5:
        raise ValueError("Schedule must be a 5-field cron expression, e.g. '0 9 * * 1-5'")
    _zone(tz)


def to_utc(when: datetime | str, tz: str) -> datetime:
    """A one-off time as naive UTC. A time without an offset is local time in `tz`."""
    if isinstance(when, str):
        try:
            when = datetime.fromisoformat(when.strip().replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError("Run time must be a date and time like '2026-11-09T14:30'") from e
    if when.tzinfo is None:
        when = when.replace(tzinfo=_zone(tz))
    return when.astimezone(UTC).replace(tzinfo=None, microsecond=0)


def _check_model(db: Session, user_id: int, key: str) -> None:
    """A task's model must be "" (the user's default) or one the user's model picker offers."""
    if not key:
        return
    user = db.get(User, user_id)
    picker = models.config_options(user)[0]["options"]
    if key not in {o["value"] for o in picker}:
        raise ValueError(f"Unknown model: {key}. Use one that is on in Settings, or leave it empty for the default")


def _plan(task: Task) -> None:
    """Check when a task runs and set its next run. Raises ValueError if invalid."""
    if task.run_at is not None:
        if task.schedule:
            raise ValueError("Give either a schedule (repeating) or a run time (once), not both")
        _zone(task.timezone)
        if task.enabled and task.run_at <= utcnow():
            raise ValueError("The run time is in the past; pick a time in the future")
        task.next_run_at = task.run_at if task.enabled else None
        return
    if not task.schedule:
        raise ValueError("Give a schedule (repeating) or a run time (once)")
    validate(task.schedule, task.timezone)
    task.next_run_at = next_run(task.schedule, task.timezone, utcnow()) if task.enabled else None


def next_run(schedule: str, tz: str, after: datetime | None = None) -> datetime:
    """Next run as naive UTC."""
    zone = ZoneInfo(tz)
    base = (after or utcnow()).replace(tzinfo=UTC).astimezone(zone)
    nxt = croniter(schedule, base).get_next(datetime)
    return nxt.astimezone(UTC).replace(tzinfo=None)


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() + "Z" if d else None


def as_dict(t: Task) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "prompt": t.prompt,
        "schedule": t.schedule,
        "run_at": _iso(t.run_at),
        "timezone": t.timezone,
        "enabled": t.enabled,
        "next_run_at": _iso(t.next_run_at),
        "last_run_at": _iso(t.last_run_at),
        "last_status": t.last_status,
        "last_chat_id": t.last_chat_id,
        "project_id": t.project_id,
        "model": t.model or "",
    }


def create(db: Session, user_id: int, fields: dict[str, Any]) -> Task:
    """Add a task for a user (the HTTP API and the agent's system tools). Raises ValueError if invalid."""
    fields = dict(fields)
    tz = fields.get("timezone") or "UTC"
    run_at = fields.pop("run_at", None)
    if fields.get("project_id") is not None:
        projects.own(db, user_id, fields["project_id"])
    fields["model"] = (fields.get("model") or "").strip()
    _check_model(db, user_id, fields["model"])
    task = Task(
        user_id=user_id,
        **{
            **fields,
            "timezone": tz,
            "schedule": fields.get("schedule") or "",
            "enabled": fields.get("enabled") is not False,
        },
        run_at=to_utc(run_at, tz) if run_at else None,
    )
    _plan(task)
    db.add(task)
    db.flush()
    return task


def update(task: Task, fields: dict[str, Any]) -> Task:
    """Change a task; None values are left as they are. Setting a schedule makes it repeating, setting a run
    time makes it one-off. Raises ValueError if invalid."""
    fields = {k: v for k, v in fields.items() if v is not None}
    if "model" in fields:
        fields["model"] = fields["model"].strip()
        db = Session.object_session(task)
        if db is None:
            with session_scope() as db:
                _check_model(db, task.user_id, fields["model"])
        else:
            _check_model(db, task.user_id, fields["model"])
    tz = fields.get("timezone", task.timezone)
    if fields.get("run_at"):
        fields["run_at"] = to_utc(fields["run_at"], tz)
        fields.setdefault("schedule", "")
    elif fields.get("schedule"):
        fields["run_at"] = None
    for k, v in fields.items():
        setattr(task, k, v)
    _plan(task)
    return task


# The database is reached from a thread (asyncio.to_thread): a database that stops answering then holds up
# the scheduler, not the event loop with every request and the liveness check on it.


def _open_chat(task_id: int) -> tuple[User, int, str] | None:
    """A new chat for a run of the task: (user, chat id, prompt), or None if the task is gone."""
    with session_scope() as db:
        task = db.get(Task, task_id)
        if task is None:
            return None
        user = db.get(User, task.user_id)
        stamp = datetime.now(ZoneInfo(task.timezone)).strftime("%d %b %H:%M")
        title = f"{task.name[:180]} · {stamp}"
        chat = Chat(
            user_id=task.user_id, title=title, task_id=task.id, project_id=task.project_id, model=task.model or ""
        )
        db.add(chat)
        db.flush()
        return user, chat.id, task.prompt


def _set(task_id: int, **fields: Any) -> None:
    """Write every field, even one that seems unchanged: the ORM would leave out a column set to the value
    it loaded, and recovery may change that column in between (a "running" for a new run must land)."""
    with session_scope() as db:
        db.query(Task).filter(Task.id == task_id).update(fields, synchronize_session=False)


async def run_task(task_id: int) -> int | None:
    """Run a task now. Returns the chat id, or None if it is already running (in any process)."""
    lock = f"task:{task_id}"
    token = None
    if not await bus.current().lock(lock):
        return None
    try:
        opened = await asyncio.to_thread(_open_chat, task_id)
        if opened is None:
            return None
        user, chat_id, prompt = opened
        token = logs.bind(task_id=task_id, user_id=user.id)
        # Start the run before the task says "running", so its chat already shows as running.
        feed, _ = await agent.start(user, chat_id, prompt)
        await asyncio.to_thread(_set, task_id, last_status="running", last_run_at=utcnow(), last_chat_id=chat_id)
        try:
            ok = bool((await asyncio.shield(feed.wait())).get("ok"))
        except Exception:  # noqa: BLE001
            log.exception("task %s failed", task_id)
            ok = False
        await asyncio.to_thread(_set, task_id, last_status="ok" if ok else "error")
        return chat_id
    finally:
        await bus.current().unlock(lock)
        if token:
            logs.reset(token)


TASK_STOPPED = "The server running this task stopped before the agent finished."


def _left_running() -> list[tuple[int, int | None]]:
    with session_scope() as db:
        return [tuple(r) for r in db.query(Task.id, Task.last_chat_id).filter(Task.last_status == "running").all()]


def _stop(task_id: int, chat_id: int | None) -> dict[str, Any] | None:
    """Mark the run in `chat_id` stopped and leave a note in its chat; the note, or None if that run is not
    the task's running one (any more). The compare-and-set makes it happen once, whoever else tries."""
    with session_scope() as db:
        stopped = (
            db.query(Task)
            .filter(Task.id == task_id, Task.last_status == "running", Task.last_chat_id == chat_id)
            .update({Task.last_status: "stopped"}, synchronize_session=False)
        )
        task = db.get(Task, task_id)
        if not stopped or task is None or chat_id is None or db.get(Chat, chat_id) is None:
            return None
        again = " It runs again at its next scheduled time." if task.schedule else " Use Run now to run it again."
        note = Message(chat_id=chat_id, role="note", content=TASK_STOPPED + again)
        db.add(note)
        db.flush()
        return note.to_dict()


async def recover() -> None:
    """Mark stopped the tasks whose runner died: they say "running", but no process holds their lock.
    A runner takes the lock before it says "running" and lets go after it says how the run ended, so a
    lock that stays free with "running" means its process is gone. "Stays": after a Redis restart every
    lock is briefly free until its holder's heartbeat (every bus_ttl/3) takes it back, so a run is only
    stopped once its lock has been seen free for bus_ttl/2. A run that starts meanwhile is a new chat."""
    b = bus.current()
    running = await asyncio.to_thread(_left_running)
    names = {task_id: f"task:{task_id}" for task_id, _ in running}
    held = await b.locked(names.values())
    await b.forget(f"free:{names[task_id]}:{chat_id}" for task_id, chat_id in running if names[task_id] in held)
    grace, interval = config.settings.bus_ttl / 2, config.settings.scheduler_interval
    for task_id, chat_id in running:
        if names[task_id] in held:
            continue
        since = await b.seen(f"free:{names[task_id]}:{chat_id}", ttl=grace * 4 + 3 * interval)
        if time.time() - since < grace:
            continue
        note = await asyncio.to_thread(_stop, task_id, chat_id)
        if note and chat_id is not None:
            log.warning("task %s: its run in chat %s ended with its process; marked stopped", task_id, chat_id)
            await agent._broadcast(chat_id, {"type": "message", "message": note})


def _claim_due(now: datetime) -> list[int]:
    """Claim every due task: only the process whose update moves next_run_at on starts it."""
    started = []
    with session_scope() as db:
        due = (
            db.query(Task.id, Task.next_run_at, Task.schedule, Task.timezone, Task.run_at)
            .filter(Task.enabled.is_(True), Task.next_run_at.is_not(None), Task.next_run_at <= now)
            .all()
        )
    for task_id, due_at, schedule, tz, run_at in due:
        # one-off: it never runs again by itself
        after = {Task.next_run_at: None, Task.enabled: False} if run_at is not None else {}
        after = after or {Task.next_run_at: next_run(schedule, tz, now)}
        with session_scope() as db:
            claimed = (
                db.query(Task)
                .filter(Task.id == task_id, Task.next_run_at == due_at)
                .update(after, synchronize_session=False)
            )
        if claimed:
            started.append(task_id)
    return started


async def tick() -> list[int]:
    """Recover tasks a dead process left running, then start every due task. Returns the ids started."""
    await recover()
    started = await asyncio.to_thread(_claim_due, utcnow())
    for task_id in started:
        asyncio.create_task(run_task(task_id))
    return started


async def loop() -> None:
    while True:
        try:
            await tick()
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(config.settings.scheduler_interval)
