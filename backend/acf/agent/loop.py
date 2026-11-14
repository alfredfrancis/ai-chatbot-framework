"""The agent loop.

Design (borrowing from pi, Hermes and Claude Code):
- One `Run` per chat at a time. Messages sent while it works are *steering* messages. While the model
  is thinking, its call is restarted with the message added (nothing has happened yet, so nothing is
  lost but tokens). Once it has started answering (text or a tool call), the answer finishes and the
  message is read next — text the user has seen is never thrown away. While tools run, the message
  waits for the batch to finish: tools have side effects and are never cut off.
- Replies stream: text and thinking deltas are events as they arrive; the complete message is stored
  when the stream ends. A stop mid-answer keeps the text shown so far.
- Model -> tool calls -> results -> model … until the model answers without tools. The calls of one
  answer run at the same time; a call waits only for earlier calls on the same file when one of them
  writes it.
- Background commands (`bash` with background: true) return at once and live on as jobs of the chat.
  Their output becomes a message: read at the next step of a run that is still working, or it starts a
  new run. Stop ends them too.
- MCP tools are not bound one by one: the prompt lists their names, their definitions are files in
  .acf/mcp/, and one `mcp_call` tool runs them (see mcp_client). Binding every schema costs tens of
  thousands of prompt tokens per step.
- Sub-agents (the `agent` tool, see subagents.py): helpers with a fresh context and a model the main agent
  picks. Several calls in one answer work side by side; each result is that helper's report. Each has a
  session of its own (a chat with a parent) that can be opened read-only.
- Tool errors, bad arguments and unknown tools become error results the model can recover from.
- Outputs are truncated with the full text spilled to a file (see tools.truncate).
- The system prompt is built once per turn and reused for every step, so the provider's prompt cache
  holds; edits to memory.md, context.md and skills reach it at the next turn.
- After a run: the chat is saved as Markdown for the agent to search (transcripts), and every few user
  messages a background review updates memory.md and skills (review).
- History is append-only. Provider messages are stored verbatim (thinking blocks survive). Before a
  new user turn, if the history is too long, older messages are summarised into one compaction record.
- Stop cancels the run; dangling tool calls get a "stopped" result so the history stays valid.
- Every step is an event; late subscribers (a reloaded page) get a replay, then live events.
- Run state is shared through the bus (acf/bus.py), so any app process can serve any chat: a run holds
  its chat's lease, reads its inbox (messages and job notes sent from any process) and publishes its
  events to a feed; stop and steering are signals to every process.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
    message_to_dict,
    messages_from_dict,
)

from acf import apps as personal_apps
from acf import bus, config, skills, workspace
from acf.agent import prompt, review, subagents, transcripts, usage
from acf.agent.tools import BUILTIN_TOOLS, Tool, ToolContext, ToolResult, call_tool, gather_calls
from acf.db import Chat, Message, Project, User, session_scope, utcnow
from acf.llm import LLMConfig, LLMError, calls_of, estimate_tokens, friendly_error, make_model
from acf.llm import text_of as _text_of
from acf.mcp_client import McpHub
from acf.sandbox import get_sandbox

log = logging.getLogger("acf.agent")
STOPPED = "Stopped by the user before this ran."
JOB_STOPPED = "Stopped by the user."
JOB_LOST = "This background command ended when the server restarted; its output is lost."
MAX_JOBS = 8  # running background commands per chat

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


def _strip_thinking(ai: AIMessage) -> AIMessage:
    if isinstance(ai.content, list):
        ai = ai.model_copy()
        ai.content = [
            b for b in ai.content if not (isinstance(b, dict) and b.get("type") in ("thinking", "redacted_thinking"))
        ]
    return ai


def _deltas(chunk: BaseMessage) -> list[tuple[str, str]]:
    """Visible pieces of a streamed chunk: ("text" | "thought", text)."""
    if isinstance(chunk.content, str):
        return [("text", chunk.content)] if chunk.content else []
    out = []
    for b in chunk.content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "text" and b.get("text"):
            out.append(("text", b["text"]))
        elif b.get("type") == "thinking" and b.get("thinking"):
            out.append(("thought", b["thinking"]))
    return out


class _Stream:
    """One streamed model call: its id (the message id clients group deltas by) and what was shown."""

    def __init__(self) -> None:
        self.id = "s" + uuid.uuid4().hex[:12]
        self.text = ""
        self.answering = False  # visible text or a tool call has started


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
        reported = {m.background for m in rows if m.role == "user" and m.background}
        running = bus.current().jobs(chat_id)
        for m in rows:
            job = m.background if m.role == "tool" else None
            if job and job not in reported and job not in running:
                db.add(_job_note_row(chat_id, job, m.tool_call_id or "", m.name or "", JOB_LOST, True, None))


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


def _text_item(text: str) -> dict[str, Any]:
    return {"kind": "text", "text": text}


def _note_item(fields: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "note", "fields": fields}


class Run:
    def __init__(self, user: User, chat_id: int, run_id: str | None = None):
        self.user = user
        self.chat_id = chat_id
        self.id = run_id or bus.new_id()
        self.feed = bus.current().feed(chat_id, self.id, local=True)
        self._nudged = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.final_text = ""
        self.ok = True
        # ACP stop reason: end_turn | cancelled | max_turn_requests; `error` is set when the run failed.
        self.stop_reason = "end_turn"
        self.error: str | None = None
        self.system: str | None = None  # the system prompt of the latest turn (reused by the review)
        self.usage: dict[str, Any] | None = None  # context usage after the latest model call (see usage)
        self._agents = asyncio.Semaphore(max(config.settings.subagents, 1))  # sub-agents working at once

    # -- events
    def emit(self, event: dict[str, Any]) -> None:
        bus.current().publish(self.feed, event)

    @property
    def events(self) -> list[dict[str, Any]]:
        return self.feed.events

    @property
    def done(self) -> bool:
        return self.task is not None and self.task.done()

    # -- control
    def nudge(self, text: str) -> None:
        """A message was pushed to the chat's inbox: restart a model call that hasn't started answering."""
        self._nudged.set()
        self.emit({"type": "queued", "text": text})

    def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()

    # -- main
    async def main(self) -> None:
        b = bus.current()
        try:
            while True:
                while b.pending(self.chat_id):
                    await self._turn()
                # Release, then look again: a message pushed meanwhile is ours if no one else took the chat.
                b.release(self.chat_id, self.id)
                if not b.pending(self.chat_id) or not b.claim(self.chat_id, self.id):
                    break
        except asyncio.CancelledError:
            for item in b.take(self.chat_id):  # keep the output of jobs that finished just before the stop
                if item["kind"] == "note":
                    self.emit({"type": "message", "message": _save(self.chat_id, **item["fields"])})
            repair(self.chat_id)
            self.stop_reason = "cancelled"
            self.emit({"type": "stopped"})
        except Exception as e:  # noqa: BLE001
            log.exception("run failed")
            self.ok = False
            self.final_text = self.error = f"Something went wrong: {e}"
            self.emit({"type": "error", "error": self.final_text})
        finally:
            b.release(self.chat_id, self.id)
            if RUNS.get(self.chat_id) is self:
                RUNS.pop(self.chat_id)
            transcripts.save(self.user.id, self.chat_id)
            self.emit(
                {
                    "type": "done",
                    "stop_reason": self.stop_reason,
                    "error": self.error,
                    "ok": self.ok,
                    "final_text": self.final_text,
                }
            )
        if self.stop_reason != "cancelled" and self.ok:
            try:
                review.maybe_start(self.user, self.chat_id, self.system)
            except Exception:  # noqa: BLE001 - never let the review break a finished run
                log.exception("could not start a review")

    def _inject_user_messages(self, history: list[BaseMessage]) -> bool:
        got = False
        for item in bus.current().take(self.chat_id):
            fields = item["fields"] if item["kind"] == "note" else {"role": "user", "content": item["text"]}
            msg = _save(self.chat_id, **fields)
            history.append(HumanMessage(fields["content"]))
            self.emit({"type": "message", "message": msg})
            got = True
        return got

    async def _compact(self, history: list[BaseMessage], model, system: str, limit: int) -> list[BaseMessage]:
        s = config.settings
        if estimate_tokens(history) < limit:
            return history
        # Keep a recent tail that starts at a user message, so tool calls stay paired; at most a sixth of the
        # limit, so a small token window still has something to summarise.
        keep_from, budget, keep = None, 0, min(s.compact_keep_tokens, limit // 6)
        for i in range(len(history) - 1, 0, -1):
            budget += estimate_tokens(history[i].content)
            if isinstance(history[i], HumanMessage) and budget >= keep:
                keep_from = i
                break
        if keep_from is None or keep_from < 2:
            return history  # nothing worth summarising
        older = [_strip_thinking(m) if isinstance(m, AIMessage) else m for m in history[:keep_from]]
        reply = await model.ainvoke([SystemMessage(system), *older, HumanMessage(SUMMARY_PROMPT)])
        with session_scope() as db:
            ids = [
                m.id
                for m in db.query(Message.id)
                .filter(Message.chat_id == self.chat_id, Message.role.in_(("user", "assistant", "tool")))
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
                chat.title = workspace.message_title(str(first.content))
                self.emit({"type": "title", "title": chat.title})
            project = db.get(Project, chat.project_id) if chat and chat.project_id else None

        try:
            cfg = LLMConfig.for_chat(self.user, self.chat_id)
            base_model = make_model(cfg)
        except LLMError as e:
            self.ok, self.final_text = False, str(e)
            self.error = self.final_text
            self.emit({"type": "error", "error": str(e)})
            return

        async with McpHub(self.user.id, self.user.mcp_config, get_sandbox(self.user.id)) as hub:
            for st in hub.status():
                if st["state"] in ("error", "needs_auth"):
                    self.emit({"type": "notice", "text": f"{st['name']}: {st['error'] or 'sign-in required'}"})
            agent_tool = subagents.TOOL if config.settings.subagents > 0 else None
            tools: dict[str, Tool] = {t.name: t for t in [*BUILTIN_TOOLS, agent_tool, hub.tool()] if t}
            schemas = [t.schema() for t in tools.values()]
            model = base_model.bind_tools(schemas)
            skills.seed(self.user.id)  # built-in skills added since the account was made
            for name in skills.archive_stale(self.user.id):
                self.emit({"type": "notice", "text": f"Moved the unused skill “{name}” to skills/.archive/."})
            # One system prompt for the whole turn: the same prefix every step, so the provider's cache holds.
            apps = hub.catalog()
            app = personal_apps.chat_app(self.user.id, self.chat_id)
            sections = prompt.sections(self.user.id, apps, cfg.model, project, (app.id, app.title) if app else None)
            self.system = "".join(text for _, text in sections)
            skill_names = [sk.name for sk in skills.list_skills(self.user.id)]
            window = usage.window(base_model, cfg.context_window)
            system = SystemMessage(
                content=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}]
            )
            try:
                # A token window set for the model: compact at 80% of it (else ACF_COMPACT_TOKENS).
                limit = int(cfg.context_window * 0.8) if cfg.context_window else config.settings.compact_tokens
                history = await self._compact(history, base_model, self.system, limit)
            except Exception as e:  # noqa: BLE001 - compaction is best effort
                log.warning("compaction failed: %s", e)

            for _ in range(config.settings.max_agent_steps):
                try:
                    ai, stream_id = await self._think(model, system, history)
                except asyncio.CancelledError:
                    raise
                except Exception as e:  # noqa: BLE001
                    self.ok, self.final_text = False, friendly_error(e)
                    self.error = self.final_text
                    self.emit({"type": "error", "error": self.final_text})
                    return
                calls = calls_of(ai)
                text = _text_of(ai)
                history.append(ai)
                self.usage = usage.measure(sections, schemas, skill_names, apps, history, ai, window)
                saved = _save(
                    self.chat_id,
                    role="assistant",
                    content=text,
                    tool_calls=[{"id": c["id"], "name": c["name"], "arguments": c["args"]} for c in calls] or None,
                    raw={"lc": message_to_dict(ai), "usage": self.usage, "stream": stream_id},
                )
                self.emit({"type": "message", "message": saved, "stream": stream_id})
                self.emit({"type": "usage", "usage": self.usage})
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

    async def _think(self, model, system: SystemMessage, history: list[BaseMessage]) -> tuple[AIMessage, str]:
        """Stream the model's answer. If the user steers before it starts answering, restart the call with
        their message; once it is answering, let it finish (the message is read at the next step)."""
        while True:
            self._nudged.clear()
            self._inject_user_messages(history)
            stream = _Stream()
            call = asyncio.ensure_future(self._stream(model, [system, *history], stream))
            nudge: asyncio.Future | None = None
            try:
                while True:
                    nudge = asyncio.ensure_future(self._nudged.wait())
                    done, _ = await asyncio.wait({call, nudge}, return_when=asyncio.FIRST_COMPLETED)
                    if call in done or stream.answering:
                        break
                    self._nudged.clear()
                    if bus.current().pending(self.chat_id):
                        break  # restart with the new message
                    # A late nudge for a message this call already has (signals can trail the inbox).
                if call not in done and stream.answering:
                    return await call, stream.id
            except asyncio.CancelledError:
                self._keep_partial(stream)
                raise
            finally:
                if nudge:
                    nudge.cancel()
                if not call.done():
                    call.cancel()
            if call.done() and not call.cancelled():
                return call.result(), stream.id  # an answer that raced the nudge wins
            with contextlib.suppress(asyncio.CancelledError):
                await call

    async def _stream(self, model, messages: list[BaseMessage], stream: _Stream) -> AIMessage:
        acc = None
        async for chunk in model.astream(messages):
            acc = chunk if acc is None else acc + chunk
            for kind, text in _deltas(chunk):
                if kind == "text":
                    stream.text += text
                    stream.answering = True
                self.emit({"type": "delta", "stream": stream.id, "kind": kind, "text": text})
            if getattr(chunk, "tool_call_chunks", None):
                stream.answering = True
        return message_chunk_to_message(acc) if acc is not None else AIMessage(content="")

    def _keep_partial(self, stream: _Stream) -> None:
        """Stopped mid-answer: store the text the user already saw (without thinking or tool calls)."""
        text = stream.text.strip()
        if not text:
            return
        ai = AIMessage(content=text)
        raw = {"lc": message_to_dict(ai), "stream": stream.id}
        saved = _save(self.chat_id, role="assistant", content=text, raw=raw)
        self.final_text = text
        self.emit({"type": "message", "message": saved, "stream": stream.id})

    async def _execute(self, calls: list[dict], tools: dict[str, Tool], hub: McpHub | None) -> list[ToolMessage]:
        async def one(call: dict, wait: list[asyncio.Future]) -> ToolMessage:
            if wait:
                await asyncio.gather(*wait, return_exceptions=True)

            async def subagent(args: dict[str, Any]) -> ToolResult:
                def progress(info: dict[str, Any]) -> None:
                    self.emit({"type": "agent", "id": call["id"], "agent": info})

                async with self._agents:
                    return await subagents.run(self.user, self.chat_id, self.system or "", tools, args, progress)

            ctx = ToolContext(
                self.user.id,
                start_job=lambda label, work: start_job(self.user, self.chat_id, call, label, work),
                subagent=subagent,
            )
            tool = tools.get(call["name"])
            label = tool.label(call["args"]) if tool else call["name"]
            self.emit({"type": "tool_start", "id": call["id"], "name": call["name"], "label": label})
            started = time.monotonic()
            result = await call_tool(call, tools, ctx)
            content = result.content
            ms = int((time.monotonic() - started) * 1000)
            raw: dict[str, Any] = {"duration_ms": ms}
            if result.background:
                raw["background"] = result.background
            if result.agent:
                raw["agent"] = result.agent
            saved = _save(
                self.chat_id,
                role="tool",
                content=content,
                tool_call_id=call["id"],
                name=call["name"],
                is_error=result.is_error,
                raw=raw,
            )
            self.emit({"type": "message", "message": saved})
            return ToolMessage(
                content=content or "(no output)",
                tool_call_id=call["id"],
                status="error" if result.is_error else "success",
            )

        # Everything runs at once, except that a call waits for earlier calls on the same resource when
        # either one writes (read then edit the same file, two edits of one file).
        return await gather_calls(calls, tools, one)


RUNS: dict[int, Run] = {}  # runs this process is running, by chat


def _new_run(user: User, chat_id: int, run_id: str) -> Run:
    run = Run(user, chat_id, run_id)
    RUNS[chat_id] = run
    run.task = asyncio.create_task(run.main())
    return run


def _submit(user: User, chat_id: int, item: dict[str, Any], steer: str | None = None) -> tuple[bus.Feed, bool]:
    """Put an item in the chat's inbox, then start a run here or leave it to the one running (anywhere).
    Returns (the feed of the run that reads it, whether that run was already running)."""
    b = bus.current()
    b.push(chat_id, item)
    for _ in range(100):
        run_id = bus.new_id()
        if b.claim(chat_id, run_id):
            return _new_run(user, chat_id, run_id).feed, False
        owner = b.owner(chat_id)
        if owner:
            if steer is not None:
                b.signal({"op": "steer", "chat_id": chat_id, "text": steer})
            return b.feed(chat_id, owner), True
    raise RuntimeError(f"Could not start a run for chat {chat_id}")


def start(user: User, chat_id: int, text: str) -> tuple[bus.Feed, bool]:
    """Send a message: start a run, or steer the active one. Returns (its feed, queued)."""
    text = skills.reference(user.id, text)  # "/name" calls a skill, also from a task or a personal app
    return _submit(user, chat_id, _text_item(text), steer=text)


def active(chat_id: int) -> bus.Feed | None:
    """The feed of the chat's running run, wherever it runs."""
    b = bus.current()
    run_id = b.owner(chat_id)
    if not run_id:
        return None
    feed = b.feed(chat_id, run_id)
    return None if feed.done else feed


def feed(chat_id: int, run_id: str) -> bus.Feed:
    return bus.current().feed(chat_id, run_id)


def running(chat_id: int) -> bool:
    return bus.current().owner(chat_id) is not None


def stop(chat_id: int) -> None:
    """Stop the chat's run and its background commands, in whichever process runs them."""
    bus.current().signal({"op": "stop", "chat_id": chat_id})


def _on_stop(msg: dict[str, Any]) -> None:
    chat_id = msg["chat_id"]
    run = RUNS.get(chat_id)
    if run:
        run.stop()
    for job in [j for j in JOBS.values() if j.chat_id == chat_id]:
        job.task.cancel()


def _on_steer(msg: dict[str, Any]) -> None:
    run = RUNS.get(msg["chat_id"])
    if run and not run.done:
        run.nudge(msg["text"])


def _on_lost(msg: dict[str, Any]) -> None:
    """Another process took this chat (this one was cut off from the bus): stop here."""
    run = RUNS.get(msg["chat_id"])
    if run:
        run.stop()


async def shutdown(grace: float) -> None:
    """Scale in / restart: let running agents finish for `grace` seconds, then stop them and the jobs.
    Only this event loop's work (tests serve a second app in a thread of the same process)."""
    loop = asyncio.get_running_loop()
    runs = lambda: [r for r in RUNS.values() if r.task and not r.task.done() and r.task.get_loop() is loop]  # noqa: E731
    jobs = [j for j in JOBS.values() if j.task.get_loop() is loop]
    if runs():
        await asyncio.wait([r.task for r in runs()], timeout=grace)
    for job in jobs:
        job.lost = True
        job.task.cancel()
    for run in runs():
        run.stop()
    pending = [t for t in [*(r.task for r in runs()), *(j.task for j in jobs)] if t and not t.done()]
    if pending:
        await asyncio.wait(pending, timeout=10)


# ------------------------------------------------------------------ chat watchers

# Clients that show a chat hear about what happens outside a run they follow: a run started by a finished
# background command ({"type": "run", "run_id": …}) and a note saved while no run reads it ({"type": "message"}).
# Events go out as a bus signal, so clients connected to any process hear them.
_watchers: dict[int, list[Callable[[dict[str, Any]], None]]] = {}


def watch_chat(chat_id: int, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
    _watchers.setdefault(chat_id, []).append(callback)

    def unwatch() -> None:
        cbs = _watchers.get(chat_id, [])
        if callback in cbs:
            cbs.remove(callback)
        if not cbs:
            _watchers.pop(chat_id, None)

    return unwatch


def _broadcast(chat_id: int, event: dict[str, Any]) -> None:
    bus.current().signal({"op": "chat", "chat_id": chat_id, "event": event})


def announce(chat_id: int, run_id: str) -> None:
    """Tell clients that have the chat open about a run they didn't start (e.g. from a personal app's screen)."""
    _broadcast(chat_id, {"type": "run", "run_id": run_id})


def _on_chat(msg: dict[str, Any]) -> None:
    for cb in list(_watchers.get(msg["chat_id"], [])):
        try:
            cb(msg["event"])
        except Exception:  # noqa: BLE001 - one broken client must not break the others
            log.exception("chat watcher failed")


# ------------------------------------------------------------------ background jobs


class Job:
    def __init__(self, job_id: str, user: User, chat_id: int, call: dict, label: str):
        self.id, self.user, self.chat_id, self.call, self.label = job_id, user, chat_id, call, label
        self.task: asyncio.Task
        self.lost = False  # cancelled by a shutdown, not by the user


JOBS: dict[str, Job] = {}  # background commands this process runs


def _job_note_row(
    chat_id: int, job: str, call_id: str, tool: str, text: str, is_error: bool, ms: int | None, command: str = ""
) -> Message:
    return Message(chat_id=chat_id, **_job_note(job, call_id, tool, text, is_error, ms, command))


def _job_note(
    job: str, call_id: str, tool: str, text: str, is_error: bool, ms: int | None, command: str = ""
) -> dict[str, Any]:
    head = f"[background job {job} {'failed' if is_error else 'finished'}" + (f" after {ms / 1000:.1f}s" if ms else "")
    body = f"{head}]\n" + (f"$ {command}\n" if command else "") + text
    return {
        "role": "user",
        "content": body,
        "tool_call_id": call_id,
        "name": tool,
        "is_error": is_error,
        "raw": {"background": job, "duration_ms": ms},
    }


def start_job(user: User, chat_id: int, call: dict, label: str, work: Callable[[], Awaitable[ToolResult]]) -> str:
    """Run `work` in the background for this chat; its result is reported as a note (see _finish)."""
    if len(bus.current().jobs(chat_id)) >= MAX_JOBS:
        raise ValueError(f"{MAX_JOBS} background commands are already running. Wait for one to finish.")
    job = Job("bg-" + uuid.uuid4().hex[:6], user, chat_id, call, label)
    JOBS[job.id] = job
    bus.current().add_job(chat_id, job.id)
    job.task = asyncio.create_task(_job_main(job, work))
    return job.id


async def _job_main(job: Job, work: Callable[[], Awaitable[ToolResult]]) -> None:
    started = time.monotonic()
    stopped = False
    try:
        result = await work()
    except asyncio.CancelledError:
        result, stopped = ToolResult(JOB_LOST if job.lost else JOB_STOPPED, True), True
    except Exception as e:  # noqa: BLE001
        log.exception("background job failed")
        result = ToolResult(f"The command could not run: {e}", True)
    finally:
        JOBS.pop(job.id, None)
        bus.current().drop_job(job.id)
    ms = int((time.monotonic() - started) * 1000)
    note = _job_note(job.id, job.call["id"], job.call["name"], result.content, result.is_error, ms, job.label)
    if stopped:  # a stop doesn't wake the agent: save it for the next turn and tell who is watching
        _broadcast(job.chat_id, {"type": "message", "message": _save(job.chat_id, **note)})
        return
    # Read at the next step of the chat's run (in any process), or start one here.
    feed, queued = _submit(job.user, job.chat_id, _note_item(note))
    if not queued:
        announce(job.chat_id, feed.run_id)


async def run_to_completion(user: User, chat_id: int, text: str) -> tuple[str, bool]:
    feed, _ = start(user, chat_id, text)
    done = await asyncio.shield(feed.wait())
    return done.get("final_text", ""), bool(done.get("ok"))


bus.handle("stop", _on_stop)
bus.handle("steer", _on_steer)
bus.handle("lost", _on_lost)
bus.handle("chat", _on_chat)
