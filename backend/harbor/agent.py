"""The agent loop: model ⇄ tools, until the model answers in plain text."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from harbor import config, workspace
from harbor.db import Chat, Message, User, session_scope, utcnow
from harbor.llm import LLMConfig, LLMError, ToolCall, ToolSpec, make_llm
from harbor.mcp_client import McpHub
from harbor.sandbox import SandboxError, get_sandbox

BUILTIN_TOOLS = [
    ToolSpec(
        "run_command",
        "Run a shell command in the user's private Linux sandbox (working directory /workspace). "
        "Use it for scripts, data processing, installing packages and anything that needs a computer.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command, run with sh -c"},
                "timeout_seconds": {"type": "integer", "description": "Optional, default 120"},
            },
            "required": ["command"],
        },
    ),
    ToolSpec(
        "read_file",
        "Read a text file from the workspace.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ),
    ToolSpec(
        "write_file",
        "Create or overwrite a text file in the workspace.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    ),
    ToolSpec(
        "list_files",
        "List files in the workspace.",
        {"type": "object", "properties": {}},
    ),
    ToolSpec(
        "remember",
        "Save a short fact to long-term memory (memory.md) so it is available in future conversations. "
        "Use when the user shares a lasting preference or fact, or asks you to remember something.",
        {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]},
    ),
]

TOOL_LABELS = {
    "run_command": "Ran a command",
    "read_file": "Read a file",
    "write_file": "Wrote a file",
    "list_files": "Listed files",
    "remember": "Saved to memory",
}


def system_prompt(user: User) -> str:
    ctx = workspace.read_file(user.id, workspace.CONTEXT_FILE).strip()
    mem = workspace.read_file(user.id, workspace.MEMORY_FILE).strip()
    today = datetime.now(UTC).strftime("%A, %d %B %Y")
    return f"""You are Harbor, a friendly personal assistant. The person you help may not be technical:
explain things plainly, avoid jargon, and keep answers short unless asked for detail.

You can act, not just talk: you have a private Linux sandbox with a persistent folder /workspace.
Use your tools to run commands, read and write files, and use any connected apps. Prefer doing the work
over describing how to do it. Paths are relative to /workspace. Never claim to have done something you
did not do; if a tool fails, say so plainly.

Today is {today} (UTC).

The user's own notes about themselves and how they want you to work (context.md):
<context>
{ctx or "(empty)"}
</context>

Things you were asked to remember (memory.md). Add to it with the remember tool:
<memory>
{mem or "(empty)"}
</memory>"""


def _neutral(m: Message) -> dict[str, Any]:
    return {
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls or [],
        "tool_call_id": m.tool_call_id,
        "name": m.name,
        "is_error": m.is_error,
        "raw": m.raw,
    }


def _save(chat_id: int, **fields) -> dict[str, Any]:
    with session_scope() as db:
        msg = Message(chat_id=chat_id, **fields)
        db.add(msg)
        chat = db.get(Chat, chat_id)
        if chat:
            chat.updated_at = utcnow()
        db.flush()
        return msg.to_dict()


async def run_builtin(user_id: int, call: ToolCall) -> tuple[str, bool]:
    args = call.arguments or {}
    try:
        if call.name == "run_command":
            timeout = min(int(args.get("timeout_seconds") or config.settings.command_timeout), 900)
            res = await get_sandbox(user_id).exec(str(args["command"]), timeout)
            return res.as_text(), res.exit_code != 0
        if call.name == "read_file":
            path = workspace.resolve(user_id, str(args["path"]))
            if not path.is_file():
                return f"No such file: {args['path']}", True
            return workspace.read_file(user_id, str(args["path"])), False
        if call.name == "write_file":
            workspace.write_file(user_id, str(args["path"]), str(args.get("content", "")))
            return f"Saved {args['path']}", False
        if call.name == "list_files":
            files = workspace.list_files(user_id)
            return "\n".join(
                f"{f['path']} ({f['size']} bytes)" for f in files
            ) or "(workspace is empty)", False
        if call.name == "remember":
            workspace.append_memory(user_id, str(args["fact"]))
            return "Saved to memory.", False
    except KeyError as e:
        return f"Missing argument: {e}", True
    except (ValueError, SandboxError, OSError) as e:
        return str(e), True
    return f"Unknown tool: {call.name}", True


def _label(call: ToolCall, hub: McpHub) -> str:
    if hub.owns(call.name):
        return hub.label(call.name)
    if call.name == "run_command":
        return str(call.arguments.get("command", ""))[:120]
    if call.name in ("read_file", "write_file"):
        return f"{call.name} {call.arguments.get('path', '')}"
    return call.name


# Chats the agent is working on right now (interactive or scheduled).
RUNNING: set[int] = set()


async def run(user: User, chat_id: int, text: str) -> AsyncIterator[dict[str, Any]]:
    """Add a user message to a chat and run the agent. Yields UI events."""
    RUNNING.add(chat_id)
    try:
        async for event in _run(user, chat_id, text):
            yield event
    finally:
        RUNNING.discard(chat_id)


async def _run(user: User, chat_id: int, text: str) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "message", "message": _save(chat_id, role="user", content=text)}

    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        if chat and chat.title in ("", "New chat"):
            chat.title = (text.strip().splitlines() or ["New chat"])[0][:60]
        history = [
            _neutral(m) for m in db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
        ]

    llm = make_llm(LLMConfig.for_user(user))
    sandbox = get_sandbox(user.id)
    async with McpHub(user.id, user.mcp_config, sandbox) as hub:
        for status in hub.status():
            if status["state"] in ("error", "needs_auth"):
                yield {"type": "notice", "text": f"{status['name']}: {status['error'] or 'sign-in required'}"}
        tools = BUILTIN_TOOLS + hub.tool_specs()
        for _step in range(config.settings.max_agent_steps):
            try:
                reply = await llm.complete(system_prompt(user), history, tools)
            except LLMError as e:
                yield {"type": "error", "error": str(e)}
                return
            saved = _save(
                chat_id,
                role="assistant",
                content=reply.text,
                tool_calls=[c.to_dict() for c in reply.tool_calls] or None,
                raw=reply.raw,
            )
            history.append(
                {
                    "role": "assistant",
                    "content": reply.text,
                    "tool_calls": saved["tool_calls"],
                    "raw": reply.raw,
                }
            )
            yield {"type": "message", "message": saved}
            if not reply.tool_calls:
                return
            for call in reply.tool_calls:
                yield {"type": "tool_start", "id": call.id, "name": call.name, "label": _label(call, hub)}
                if hub.owns(call.name):
                    output, is_error = await hub.call(call.name, call.arguments)
                else:
                    output, is_error = await run_builtin(user.id, call)
                saved = _save(
                    chat_id,
                    role="tool",
                    content=output,
                    tool_call_id=call.id,
                    name=call.name,
                    is_error=is_error,
                )
                history.append(
                    {
                        "role": "tool",
                        "content": output,
                        "tool_call_id": call.id,
                        "name": call.name,
                        "is_error": is_error,
                    }
                )
                yield {"type": "message", "message": saved}
        yield {"type": "error", "error": "Stopped after too many steps. Ask me to continue if needed."}


async def run_to_completion(user: User, chat_id: int, text: str) -> tuple[str, bool]:
    """Run without streaming (scheduled tasks). Returns (final text, ok)."""
    final, ok = "", True
    async for ev in run(user, chat_id, text):
        if ev["type"] == "message" and ev["message"]["role"] == "assistant" and ev["message"]["content"]:
            final = ev["message"]["content"]
        elif ev["type"] == "error":
            final, ok = ev["error"], False
    return final, ok


def sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"
