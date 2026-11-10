"""Sub-agents: the `agent` tool.

The main agent hands a part of a job to a helper, as Cursor and Claude Code do with their Task tool:
- A sub-agent starts with a fresh context: the system prompt of the turn and the prompt the main agent
  wrote, nothing of the chat. What it reads and runs never enters the main agent's context; only its last
  answer does, as the tool result. That keeps a long job's context small.
- The calls of one answer run at the same time (like any tools), so the main agent fans out several
  sub-agents with one goal each and then puts their reports together. At most `ACF_SUBAGENTS` of a run work
  at once; the rest wait.
- The main agent picks the model of each one: "inherit" (its own), "fast" (a small model of the same
  provider) or a model id. The provider, address and key are always the user's own (LLMConfig.with_model).
- A sub-agent has the main agent's tools except `agent` (no sub-agents of sub-agents) and background
  commands (nothing would read their output).
- The chat keeps the tool result (the report) and, with it, the model, the steps it took and the tokens it
  used; the same record goes to clients while it works (`agent` events), so the chat shows what each one is
  doing.
- Each one has a session of its own (`Session`): a chat with `parent_id` set, holding its messages. It is
  kept out of the chat list and nobody can send to it, but a client can open it like any chat (session/load),
  also while the sub-agent works: it holds its chat's lease and publishes its events to a feed.
- Stopping the run stops its sub-agents: they are awaited by the tool call, so the cancel reaches them.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage, message_to_dict

from acf import bus, config
from acf.agent.tools import Tool, ToolContext, ToolResult, call_tool, gather_calls, tool_title
from acf.db import Chat, Message, User, session_scope
from acf.llm import LLMConfig, LLMError, calls_of, friendly_error, make_model, text_of

NAME = "agent"
MAX_PROMPT = 50_000

# Added to the turn's system prompt, after the cached part.
ROLE = """

<sub-agent>
You are a sub-agent: a helper the main agent started for one part of a bigger job. The message below is \
your whole assignment; you see nothing of the conversation with the user and cannot ask questions, so make \
reasonable assumptions and say which. You share the user's workspace with the main agent and other \
sub-agents working at the same time: change only the files your assignment is about.
Your last message is the only thing the main agent gets. Make it a complete report: what you found or \
did, the facts and file paths it needs, and what you could not do. Don't address the user, don't offer \
follow-ups, and don't save anything to memory.md.
</sub-agent>"""


async def _tool(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    if not str(args["prompt"]).strip():
        return ToolResult("prompt must not be empty: it is all the sub-agent knows.", True)
    if len(str(args["prompt"])) > MAX_PROMPT:
        return ToolResult(f"The prompt is too long (max {MAX_PROMPT} characters). Put the material in a file.", True)
    if ctx.subagent is None:
        return ToolResult("Sub-agents are not available here. Do this part yourself.", True)
    return await ctx.subagent(args)


TOOL = Tool(
    NAME,
    "Hand a self-contained part of the job to a sub-agent: a helper with your tools and a fresh context. "
    "It knows nothing of this conversation, so the prompt must carry the goal, what you already know (file "
    "paths, facts, constraints) and what to report back. Its last message comes back as the result; the user "
    "does not see it, so put what matters in your own answer. Several agent calls in one answer work at the "
    "same time: use that to split a job into independent parts, then combine the reports. Not worth it for "
    "something you can do in a step or two.",
    {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "What this sub-agent does, in 3 to 6 words"},
            "prompt": {"type": "string", "description": "The full assignment"},
            "model": {
                "type": "string",
                "description": 'The model it runs on: "inherit" (yours; the default), "fast" (a smaller, quicker '
                "model, for simple or broad look-ups) or a model id of your provider",
            },
        },
        "required": ["description", "prompt"],
    },
    _tool,
    label=lambda a: str(a.get("description", ""))[:160],
)


class Session:
    """A sub-agent's own chat: its messages, stored as they come, and a feed of its events while it works."""

    def __init__(self, user_id: int, parent_id: int, title: str):
        with session_scope() as db:
            chat = Chat(user_id=user_id, parent_id=parent_id, title=title.strip()[:200] or "Sub-agent")
            db.add(chat)
            db.flush()
            self.chat_id: int = chat.id
        self.run_id = bus.new_id()
        bus.current().claim(self.chat_id, self.run_id)
        self.feed = bus.current().feed(self.chat_id, self.run_id, local=True)

    def emit(self, event: dict[str, Any]) -> None:
        bus.current().publish(self.feed, event)

    def save(self, **fields: Any) -> None:
        with session_scope() as db:
            msg = Message(chat_id=self.chat_id, **fields)
            db.add(msg)
            db.flush()
            saved = msg.to_dict()
        self.emit({"type": "message", "message": saved})

    def close(self, stop_reason: str) -> None:
        bus.current().release(self.chat_id, self.run_id)
        self.emit({"type": "done", "stop_reason": stop_reason, "error": None, "ok": True, "final_text": ""})


async def run(
    user: User,
    chat_id: int,
    system: str,
    tools: dict[str, Tool],
    args: dict[str, Any],
    progress: Callable[[dict[str, Any]], None],
) -> ToolResult:
    """Work on `args["prompt"]` in a fresh context until the model answers without tools; the answer is the
    result. `chat_id` is the chat of the run that asked; `tools` are the main agent's; `progress` gets the
    record of the sub-agent after every change."""
    session = Session(user.id, chat_id, str(args.get("description") or ""))
    stop_reason = "end_turn"
    try:
        return await _work(user, session, system, tools, args, progress)
    except asyncio.CancelledError:
        stop_reason = "cancelled"
        raise
    finally:
        session.close(stop_reason)


async def _work(
    user: User,
    session: Session,
    system: str,
    tools: dict[str, Tool],
    args: dict[str, Any],
    progress: Callable[[dict[str, Any]], None],
) -> ToolResult:
    cfg = LLMConfig.for_user(user).with_model(str(args.get("model") or ""))
    info: dict[str, Any] = {"model": cfg.model, "tokens": 0, "steps": [], "session": str(session.chat_id)}

    def report() -> dict[str, Any]:
        return {**info, "steps": [dict(s) for s in info["steps"]]}

    def failed(why: str) -> ToolResult:
        text = f"The sub-agent could not finish: {why}"
        session.save(role="note", content=text)  # shown as a notice to whoever opens the session
        return ToolResult(text, True, agent=report())

    session.save(role="user", content=str(args["prompt"]))

    tools = {name: t for name, t in tools.items() if name != NAME}
    try:
        model = make_model(cfg).bind_tools([t.schema() for t in tools.values()])
    except LLMError as e:
        return failed(str(e))
    ctx = ToolContext(user.id)  # no background jobs and no sub-agents of its own
    progress(report())

    async def one(call: dict[str, Any], wait: list[asyncio.Future]) -> ToolMessage:
        if wait:
            await asyncio.gather(*wait, return_exceptions=True)
        step = {"title": tool_title(call["name"], call["args"]), "ok": None}
        info["steps"].append(step)
        progress(report())
        session.emit({"type": "tool_start", "id": call["id"], "name": call["name"]})
        started = time.monotonic()
        result = await call_tool(call, tools, ctx)
        step["ok"] = not result.is_error
        session.save(
            role="tool",
            content=result.content,
            tool_call_id=call["id"],
            name=call["name"],
            is_error=result.is_error,
            raw={"duration_ms": int((time.monotonic() - started) * 1000)},
        )
        progress(report())
        return ToolMessage(
            content=result.content or "(no output)",
            tool_call_id=call["id"],
            status="error" if result.is_error else "success",
        )

    # The turn's prompt first, unchanged, so a sub-agent on the main agent's model reads it from the cache.
    head = SystemMessage(
        content=[
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": ROLE.lstrip() if not system else ROLE},
        ]
    )
    history: list[BaseMessage] = [HumanMessage(str(args["prompt"]))]
    text = ""
    for _ in range(config.settings.max_agent_steps):
        try:
            ai = await model.ainvoke([head, *history])
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - a provider error ends this sub-agent, not the run
            return failed(friendly_error(e) + (f"\n\nIts last message:\n{text}" if text else ""))
        history.append(ai)
        info["tokens"] += int((ai.usage_metadata or {}).get("total_tokens") or 0)
        text = text_of(ai) or text
        calls = calls_of(ai)
        session.save(
            role="assistant",
            content=text_of(ai),
            tool_calls=[{"id": c["id"], "name": c["name"], "arguments": c["args"]} for c in calls] or None,
            raw={"lc": message_to_dict(ai)},
        )
        if not calls:
            return ToolResult(text or "(The sub-agent finished without a report.)", agent=report())
        history.extend(await gather_calls(calls, tools, one))
    return failed(
        f"it was stopped after {config.settings.max_agent_steps} steps." + (f"\n\nSo far:\n{text}" if text else "")
    )
