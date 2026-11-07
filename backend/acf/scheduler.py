"""Recurring tasks: a cron schedule + a prompt. Each run creates a new chat with the result."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from acf import config
from acf.agent import loop as agent
from acf.db import Chat, Task, User, session_scope, utcnow

log = logging.getLogger("acf.scheduler")
_running: set[int] = set()


def validate(schedule: str, tz: str) -> None:
    if not croniter.is_valid(schedule) or len(schedule.split()) != 5:
        raise ValueError("Schedule must be a 5-field cron expression, e.g. '0 9 * * 1-5'")
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"Unknown time zone: {tz}") from e


def next_run(schedule: str, tz: str, after: datetime | None = None) -> datetime:
    """Next run as naive UTC."""
    zone = ZoneInfo(tz)
    base = (after or utcnow()).replace(tzinfo=UTC).astimezone(zone)
    nxt = croniter(schedule, base).get_next(datetime)
    return nxt.astimezone(UTC).replace(tzinfo=None)


async def run_task(task_id: int) -> int | None:
    """Run a task now. Returns the chat id, or None if it is already running."""
    if task_id in _running:
        return None
    _running.add(task_id)
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
            run, _ = agent.start(user, chat_id, prompt)
        try:
            await asyncio.shield(run.task)
            ok = run.ok
        except Exception:  # noqa: BLE001
            log.exception("task %s failed", task_id)
            ok = False
        with session_scope() as db:
            task = db.get(Task, task_id)
            if task:
                task.last_status = "ok" if ok else "error"
        return chat_id
    finally:
        _running.discard(task_id)


async def tick() -> list[int]:
    """Start every due task. Returns the ids started."""
    now = utcnow()
    started = []
    with session_scope() as db:
        due = (
            db.query(Task).filter(Task.enabled.is_(True), Task.next_run_at.is_not(None), Task.next_run_at <= now).all()
        )
        for task in due:
            task.next_run_at = next_run(task.schedule, task.timezone, now)
            if task.id not in _running:
                started.append(task.id)
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
