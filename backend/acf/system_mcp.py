"""The built-in `system` MCP server: features of AI Chatbot Framework itself, for the agent.

It runs in the API process (an in-memory MCP connection, no sandbox) and is bound to one user, so every
query it makes is scoped to that user. McpHub connects it next to the user's own servers, so the agent
reaches it like any connected app: `.acf/mcp/system/<tool>.json` + `mcp_call`.

Add a system feature here as a tool, not as a new built-in agent tool.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from acf import scheduler
from acf.db import Task, session_scope

NAME = "system"
_runs: set[asyncio.Task] = set()  # keep started runs referenced until they finish

Name = Annotated[str, Field(min_length=1, max_length=200, description="Short name shown on the Tasks page")]
Prompt = Annotated[
    str, Field(min_length=1, max_length=20_000, description="What the agent should do on each run, in full")
]
Schedule = Annotated[
    str,
    Field(max_length=100, description="Repeating: 5-field cron expression, e.g. '0 9 * * 1-5' (09:00 on weekdays)"),
]
RunAt = Annotated[
    str,
    Field(
        max_length=40,
        description="Once: local date and time in `timezone`, e.g. '2026-11-09T14:30'. Must be in the future.",
    ),
]
Timezone = Annotated[str, Field(max_length=64, description="IANA time zone of the schedule, e.g. 'Europe/Lisbon'")]

_READ = ToolAnnotations(read_only_hint=True, destructive_hint=False)
_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False)
_DELETE = ToolAnnotations(read_only_hint=False, destructive_hint=True)


@contextmanager
def _invalid_as_error() -> Iterator[None]:
    """Report a ValueError's message to the agent (the SDK hides the text of unexpected errors)."""
    try:
        yield
    except ValueError as e:
        raise ToolError(str(e)) from e


def server(user_id: int) -> MCPServer:
    mcp = MCPServer(NAME, instructions="Features of AI Chatbot Framework: scheduled tasks.")

    def own(db, task_id: int) -> Task:
        task = db.get(Task, task_id)
        if task is None or task.user_id != user_id:
            raise ToolError(f"No task with id {task_id}. Use list_tasks to see the user's tasks.")
        return task

    @mcp.tool(annotations=_READ)
    def list_tasks() -> str:
        """List the user's scheduled tasks, repeating and one-off (also shown on the Tasks page)."""
        with session_scope() as db:
            tasks = db.query(Task).filter_by(user_id=user_id).order_by(Task.id).all()
            return json.dumps([scheduler.as_dict(t) for t in tasks], indent=2)

    @mcp.tool(annotations=_WRITE)
    def create_task(
        name: Name,
        prompt: Prompt,
        timezone: Timezone,
        schedule: Schedule | None = None,
        run_at: RunAt | None = None,
        enabled: bool = True,
    ) -> str:
        """Schedule a task: give `schedule` for a repeating task or `run_at` for one that runs once (a
        reminder, "in 2 hours", "tomorrow at 9"). On each run the agent gets `prompt` in a new chat, without
        the current conversation, so write the prompt so it stands on its own. Ask the user for their time
        zone if you do not know it. A one-off task turns itself off after its run."""
        fields = {
            "name": name,
            "prompt": prompt,
            "schedule": schedule,
            "run_at": run_at,
            "timezone": timezone,
            "enabled": enabled,
        }
        with session_scope() as db, _invalid_as_error():
            return json.dumps(scheduler.as_dict(scheduler.create(db, user_id, fields)), indent=2)

    @mcp.tool(annotations=_WRITE)
    def update_task(
        task_id: int,
        name: Name | None = None,
        prompt: Prompt | None = None,
        schedule: Schedule | None = None,
        run_at: RunAt | None = None,
        timezone: Timezone | None = None,
        enabled: bool | None = None,
    ) -> str:
        """Change a task. Leave out what stays the same; enabled=false pauses it. Setting `schedule` makes it
        repeating, setting `run_at` makes it run once."""
        fields = {
            "name": name,
            "prompt": prompt,
            "schedule": schedule,
            "run_at": run_at,
            "timezone": timezone,
            "enabled": enabled,
        }
        with session_scope() as db, _invalid_as_error():
            return json.dumps(scheduler.as_dict(scheduler.update(own(db, task_id), fields)), indent=2)

    @mcp.tool(annotations=_DELETE)
    def delete_task(task_id: int) -> str:
        """Delete a task for good. To stop it for a while, pause it with update_task instead."""
        with session_scope() as db:
            task = own(db, task_id)
            name = task.name
            db.delete(task)
        return f"Deleted task {task_id} ({name})."

    @mcp.tool(annotations=_WRITE)
    async def run_task(task_id: int) -> str:
        """Start a run of a task now, in its own new chat. Returns at once; the result appears in that chat."""
        with session_scope() as db:
            own(db, task_id)
        run = asyncio.create_task(scheduler.run_task(task_id))
        _runs.add(run)
        run.add_done_callback(_runs.discard)
        return f"Started task {task_id}. Its result appears in a new chat and on the Tasks page."

    return mcp
