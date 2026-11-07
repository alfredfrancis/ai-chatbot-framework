"""The agent loop.

Design (borrowing from pi, Hermes and Claude Code):
- One `Run` per chat at a time. Messages sent while it works are *steering* messages. While the model
  is thinking, its call is restarted with the message added (nothing has happened yet, so nothing is
  lost but tokens). While tools run, the message waits for the batch to finish: tools have side
  effects and are never cut off. Either way the user redirects the agent without stopping it.
- Model -> tool calls -> results -> model … until the model answers without tools. Independent
  read-only calls run concurrently; anything that writes runs in order.
- Tool errors, bad arguments and unknown tools become error results the model can recover from.
- Outputs are truncated with the full text spilled to a file (see tools.truncate).
- History is append-only. Provider messages are stored verbatim (thinking blocks survive). Before a
  new user turn, if the history is too long, older messages are summarised into one compaction record.
- Stop cancels the run; dangling tool calls get a "stopped" result so the history stays valid.
- Every step is an event; late subscribers (a reloaded page) get a replay, then live events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_to_dict,
    messages_from_dict,
)

from acf import config
from acf.agent import prompt
from acf.agent.tools import BUILTIN_TOOLS, Tool, ToolContext, ToolResult, truncate
from acf.db import Chat, Message, User, session_scope, utcnow
from acf.llm import LLMConfig, LLMError, estimate_tokens, friendly_error, make_model
from acf.mcp_client import McpHub
from acf.sandbox import get_sandbox

log = logging.getLogger("acf.agent")
STOPPED = "Stopped by the user before this ran."

SUMMARY_PROMPT = """Summarise the conversation above so you can continue the work without it. Write:
## Goal
## Done so far (with file paths and results)
## Key facts, preferences and decisions
## Open items / next steps
Be concrete and complete; this summary replaces the earlier messages."""


# ------------------------------------------------------------------ persistence


def _save(chat_id: int, **fields) -> dict[str, Any]:
    with session_scope() as db:
        msg = Message(chat_id=chat_id, **fields)
        db.add(msg)
        chat = db.get(Chat, chat_id)
        if chat:
            chat.updated_at = utcnow()
        db.flush()
        return msg.to_dict()


def _text_of(ai: AIMessage) -> str:
    if isinstance(ai.content, str):
        return ai.content.strip()
    return "\n".join(b.get("text", "") for b in ai.content if isinstance(b, dict) and b.get("type") == "text").strip()


def _strip_thinking(ai: AIMessage) -> AIMessage:
    if isinstance(ai.content, list):
        ai = ai.model_copy()
        ai.content = [
            b for b in ai.content if not (isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"))
        ]
    return ai


def repair(chat_id: int) -> None:
    """Give every tool call without a result a 'stopped' result (after a crash or a stop)."""
    with session_scope() as db:
        rows = db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
        answered = {m.tool_call_id for m in rows if m.role == "tool"}
        for m in rows:
            if m.role == "assistant":
                for tc in m.tool_calls or []:
                    if tc["id"] not in answered:
                        db.add(
                            Message(
                                chat_id=chat_id,
                                role="tool",
                                content=STOPPED,
                                tool_call_id=tc["id"],
                                name=tc["name"],
                                is_error=True,
                            )
                        )
                        answered.add(tc["id"])


def load_history(chat_id: int) -> list[BaseMessage]:
    """DB rows -> LangChain messages, starting from the latest compaction summary."""
    repair(chat_id)
    with session_scope() as db:
        rows = db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
    summary = next((m for m in reversed(rows) if m.role == "summary"), None)
    out: list[BaseMessage] = []
    strip_until = -1
    if summary:
        info = summary.raw or {}
        rows = [m for m in rows if m.id > info.get("covers_until", 0) and m.role != "summary"]
        strip_until = info.get("compacted_at", -1)
        out.append(HumanMessage(f"<summary of the earlier conversation>\n{summary.content}\n</summary>"))
    for m in rows:
        if m.role == "user":
            out.append(HumanMessage(m.content))
        elif m.role == "assistant":
            raw = (m.raw or {}).get("lc")
            ai = (
                messages_from_dict([raw])[0]
                if raw
                else AIMessage(
                    content=m.content,
                    tool_calls=[
                        {"id": t["id"], "name": t["name"], "args": t["arguments"], "type": "tool_call"}
                        for t in m.tool_calls or []
                    ],
                )
            )
            # Thinking blocks are bound to the prefix they were produced with; after compaction the
            # prefix changed, so drop them from messages that predate the compaction.
            out.append(_strip_thinking(ai) if m.id <= strip_until else ai)
        elif m.role == "tool":
            out.append(
                ToolMessage(
                    content=m.content or "(no output)",
                    tool_call_id=m.tool_call_id or "",
                    status="error" if m.is_error else "success",
                )
            )
    return out


# ------------------------------------------------------------------ the run


class Run:
    def __init__(self, user: User, chat_id: int):
        self.user = user
        self.chat_id = chat_id
        self.inbox: asyncio.Queue[str] = asyncio.Queue()
        self._nudged = asyncio.Event()
        self.events: list[dict[str, Any]] = []
        self._listeners: list[asyncio.Queue] = []
        self.task: asyncio.Task | None = None
        self.final_text = ""
        self.ok = True
        # ACP stop reason: end_turn | cancelled | max_turn_requests; `error` is set when the run failed.
        self.stop_reason = "end_turn"
        self.error: str | None = None

    # -- events
    def emit(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        for q in self._listeners:
            q.put_nowait(event)

    def listen(self) -> asyncio.Queue:
        """Register a listener now: it gets every event so far, then live ones."""
        q: asyncio.Queue = asyncio.Queue()
        for e in self.events:
            q.put_nowait(e)
        self._listeners.append(q)
        return q

    def unlisten(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        q = self.listen()
        try:
            while True:
                e = await q.get()
                yield e
                if e["type"] == "done":
                    return
        finally:
            self.unlisten(q)

    @property
    def done(self) -> bool:
        return self.task is not None and self.task.done()

    # -- control
    def steer(self, text: str) -> None:
        self.inbox.put_nowait(text)
        self._nudged.set()
        self.emit({"type": "queued", "text": text})

    def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()

    # -- main
    async def main(self) -> None:
        try:
            while not self.inbox.empty():
                await self._turn()
        except asyncio.CancelledError:
            repair(self.chat_id)
            self.stop_reason = "cancelled"
            self.emit({"type": "stopped"})
        except Exception as e:  # noqa: BLE001
            log.exception("run failed")
            self.ok = False
            self.final_text = self.error = f"Something went wrong: {e}"
            self.emit({"type": "error", "error": self.final_text})
        finally:
            RUNS.pop(self.chat_id, None)
            self.emit({"type": "done"})

    def _inject_user_messages(self, history: list[BaseMessage]) -> bool:
        got = False
        while not self.inbox.empty():
            text = self.inbox.get_nowait()
            msg = _save(self.chat_id, role="user", content=text)
            history.append(HumanMessage(text))
            self.emit({"type": "message", "message": msg})
            got = True
        return got

    async def _compact(self, history: list[BaseMessage], model) -> list[BaseMessage]:
        s = config.settings
        if estimate_tokens(history) < s.compact_tokens:
            return history
        # Keep a recent tail that starts at a user message, so tool calls stay paired.
        keep_from, budget = None, 0
        for i in range(len(history) - 1, 0, -1):
            budget += estimate_tokens(history[i].content)
            if isinstance(history[i], HumanMessage) and budget >= s.compact_keep_tokens:
                keep_from = i
                break
        if keep_from is None or keep_from < 2:
            return history  # nothing worth summarising
        older = [_strip_thinking(m) if isinstance(m, AIMessage) else m for m in history[:keep_from]]
        reply = await model.ainvoke([SystemMessage(prompt.build(self.user.id)), *older, HumanMessage(SUMMARY_PROMPT)])
        with session_scope() as db:
            ids = [
                m.id
                for m in db.query(Message.id)
                .filter(Message.chat_id == self.chat_id, Message.role != "summary")
                .order_by(Message.id)
                .all()
            ]
        # Map the history index back to DB rows: the kept tail is the last N persisted messages.
        kept = len(history) - keep_from
        covers_until = ids[-kept - 1] if kept < len(ids) else 0
        _save(
            self.chat_id,
            role="summary",
            content=_text_of(reply),
            raw={"covers_until": covers_until, "compacted_at": ids[-1]},
        )
        self.emit({"type": "notice", "text": "Summarised earlier messages to keep the conversation fast."})
        return load_history(self.chat_id)

    async def _turn(self) -> None:
        self.ok, self.error = True, None  # a later turn (e.g. from a steering message) supersedes an earlier failure
        history = load_history(self.chat_id)
        self._inject_user_messages(history)
        with session_scope() as db:
            chat = db.get(Chat, self.chat_id)
            first = next((m for m in history if isinstance(m, HumanMessage)), None)
            if chat and chat.title in ("", "New chat") and first:
                chat.title = (str(first.content).strip().splitlines() or ["New chat"])[0][:60]
                self.emit({"type": "title", "title": chat.title})

        try:
            base_model = make_model(LLMConfig.for_user(self.user))
        except LLMError as e:
            self.ok, self.final_text = False, str(e)
            self.error = self.final_text
            self.emit({"type": "error", "error": str(e)})
            return

        async with McpHub(self.user.id, self.user.mcp_config, get_sandbox(self.user.id)) as hub:
            for st in hub.status():
                if st["state"] in ("error", "needs_auth"):
                    self.emit({"type": "notice", "text": f"{st['name']}: {st['error'] or 'sign-in required'}"})
            tools: dict[str, Tool] = {t.name: t for t in BUILTIN_TOOLS + hub.tools()}
            model = base_model.bind_tools([t.schema() for t in tools.values()])
            try:
                history = await self._compact(history, base_model)
            except Exception as e:  # noqa: BLE001 - compaction is best effort
                log.warning("compaction failed: %s", e)

            for _ in range(config.settings.max_agent_steps):
                system = SystemMessage(
                    content=[
                        {
                            "type": "text",
                            "text": prompt.build(self.user.id),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                )
                try:
                    ai = await self._think(model, system, history)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    self.ok, self.final_text = False, friendly_error(e)
                    self.error = self.final_text
                    self.emit({"type": "error", "error": self.final_text})
                    return
                calls = list(ai.tool_calls) + [
                    {
                        "id": c.get("id") or f"invalid_{i}",
                        "name": c.get("name") or "unknown",
                        "args": {},
                        "error": c.get("error") or "Invalid arguments",
                    }
                    for i, c in enumerate(ai.invalid_tool_calls)
                ]
                text = _text_of(ai)
                saved = _save(
                    self.chat_id,
                    role="assistant",
                    content=text,
                    tool_calls=[{"id": c["id"], "name": c["name"], "arguments": c["args"]} for c in calls] or None,
                    raw={"lc": message_to_dict(ai)},
                )
                history.append(ai)
                self.emit({"type": "message", "message": saved})
                if text:
                    self.final_text = text
                if not calls:
                    if self._inject_user_messages(history):
                        continue  # the user added something while the model was answering
                    return
                for msg in await self._execute(calls, tools, hub):
                    history.append(msg)
                self._inject_user_messages(history)
            self.stop_reason = "max_turn_requests"
            self.emit({"type": "notice", "text": "Stopped after too many steps. Say “continue” to keep going."})

    async def _think(self, model, system: SystemMessage, history: list[BaseMessage]) -> AIMessage:
        """Call the model; if the user steers before it answers, restart the call with their message."""
        while True:
            self._inject_user_messages(history)
            self._nudged.clear()
            call = asyncio.ensure_future(model.ainvoke([system, *history]))
            nudge = asyncio.ensure_future(self._nudged.wait())
            try:
                await asyncio.wait({call, nudge}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                nudge.cancel()
                if not call.done():
                    call.cancel()
            if call.done() and not call.cancelled():
                return call.result()  # an answer that raced the nudge wins; the message goes in next step
            try:
                await call
            except asyncio.CancelledError:
                pass

    async def _execute(self, calls: list[dict], tools: dict[str, Tool], hub: McpHub) -> list[ToolMessage]:
        ctx = ToolContext(self.user.id)

        async def one(call: dict) -> ToolMessage:
            tool = tools.get(call["name"])
            label = tool.label(call["args"]) if tool else call["name"]
            self.emit({"type": "tool_start", "id": call["id"], "name": call["name"], "label": label})
            started = time.monotonic()
            if "error" in call:
                result = ToolResult(f"Could not parse the arguments: {call['error']}. Send valid JSON.", True)
            elif tool is None:
                result = ToolResult(f"Unknown tool {call['name']}. Available: {', '.join(tools)}", True)
            else:
                try:
                    result = await tool.run(call["args"], ctx)
                except KeyError as e:
                    result = ToolResult(f"Missing argument: {e}", True)
                except (ValueError, OSError, TypeError) as e:
                    result = ToolResult(str(e), True)
            # Safety net for tools (e.g. MCP) that don't cut their own output.
            content = (
                result.content if "characters omitted" in result.content[:40_000] else truncate(result.content, ctx)
            )
            ms = int((time.monotonic() - started) * 1000)
            saved = _save(
                self.chat_id,
                role="tool",
                content=content,
                tool_call_id=call["id"],
                name=call["name"],
                is_error=result.is_error,
                raw={"duration_ms": ms},
            )
            self.emit({"type": "message", "message": saved})
            return ToolMessage(
                content=content or "(no output)",
                tool_call_id=call["id"],
                status="error" if result.is_error else "success",
            )

        parallel = all(tools.get(c["name"]) is not None and tools[c["name"]].read_only for c in calls)
        if parallel and len(calls) > 1:
            return list(await asyncio.gather(*(one(c) for c in calls)))
        return [await one(c) for c in calls]


RUNS: dict[int, Run] = {}


def start(user: User, chat_id: int, text: str) -> tuple[Run, bool]:
    """Send a message: start a run, or steer the active one. Returns (run, queued)."""
    run = RUNS.get(chat_id)
    if run and not run.done:
        run.steer(text)
        return run, True
    run = Run(user, chat_id)
    RUNS[chat_id] = run
    run.inbox.put_nowait(text)
    run.task = asyncio.create_task(run.main())
    return run, False


async def run_to_completion(user: User, chat_id: int, text: str) -> tuple[str, bool]:
    run, _ = start(user, chat_id, text)
    assert run.task
    await asyncio.shield(run.task)
    return run.final_text, run.ok
