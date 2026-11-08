"""Tasks: a prompt + when to run it, either a cron schedule (recurring) or a single time (`run_at`, one-off).
Each run creates a new chat with the result. A one-off task turns itself off once it has started.

Every app process runs the scheduler. A due task is claimed by moving its next_run_at with a
compare-and-set update, so exactly one process starts it."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy.orm import Session

from acf import bus, config
from acf.agent import loop as agent
from acf.db import Chat, Task, User, session_scope, utcnow

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
    }


def create(db: Session, user_id: int, fields: dict[str, Any]) -> Task:
    """Add a task for a user (the HTTP API and the agent's system tools). Raises ValueError if invalid."""
    fields = dict(fields)
    tz = fields.get("timezone") or "UTC"
    run_at = fields.pop("run_at", None)
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


async def run_task(task_id: int) -> int | None:
    """Run a task now. Returns the chat id, or None if it is already running (in any process)."""
    lock = f"task:{task_id}"
    if not bus.current().lock(lock):
        return None
    try:
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task is None:
                return None
            user = db.get(User, task.user_id)
            stamp = datetime.now(ZoneInfo(task.timezone)).strftime("%d %b %H:%M")
            chat = Chat(user_id=task.user_id, title=f"{task.name[:180]} · {stamp}", task_id=task.id)
            db.add(chat)
            task.last_status = "running"
            task.last_run_at = utcnow()
            db.flush()
            chat_id, prompt = chat.id, task.prompt
            task.last_chat_id = chat_id
            # Start the run before committing, so the chat already shows as running.
            feed, _ = agent.start(user, chat_id, prompt)
        try:
            ok = bool((await asyncio.shield(feed.wait())).get("ok"))
        except Exception:  # noqa: BLE001
            log.exception("task %s failed", task_id)
            ok = False
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task:
                task.last_status = "ok" if ok else "error"
        return chat_id
    finally:
        bus.current().unlock(lock)


async def tick() -> list[int]:
    """Start every due task. Returns the ids started."""
    now = utcnow()
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
        # Claim it: only the process whose update moves next_run_at on starts it.
        with session_scope() as db:
            claimed = (
                db.query(Task)
                .filter(Task.id == task_id, Task.next_run_at == due_at)
                .update(after, synchronize_session=False)
            )
        if claimed:
            started.append(task_id)
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
