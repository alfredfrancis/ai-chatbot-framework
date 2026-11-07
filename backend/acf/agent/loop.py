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
- Tool errors, bad arguments and unknown tools become error results the model can recover from.
- Outputs are truncated with the full text spilled to a file (see tools.truncate).
- History is append-only. Provider messages are stored verbatim (thinking blocks survive). Before a
  new user turn, if the history is too long, older messages are summarised into one compaction record.
- Stop cancels the run; dangling tool calls get a "stopped" result so the history stays valid.
- Every step is an event; late subscribers (a reloaded page) get a replay, then live events.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
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

from acf import config, workspace
from acf.agent import prompt
from acf.agent.tools import BUILTIN_TOOLS, Tool, ToolContext, ToolResult, truncate
from acf.db import Chat, Message, User, session_scope, utcnow
from acf.llm import LLMConfig, LLMError, estimate_tokens, friendly_error, make_model
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
        for m in rows:
            job = m.background if m.role == "tool" else None
            if job and job not in reported and job not in JOBS:
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


class Run:
    def __init__(self, user: User, chat_id: int):
        self.user = user
        self.chat_id = chat_id
        self.inbox: asyncio.Queue[str | dict[str, Any]] = asyncio.Queue()  # user text, or a job's note row
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
            while not self.inbox.empty():  # keep the output of jobs that finished just before the stop
                item = self.inbox.get_nowait()
                if isinstance(item, dict):
                    self.emit({"type": "message", "message": _save(self.chat_id, **item)})
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
            item = self.inbox.get_nowait()
            fields = item if isinstance(item, dict) else {"role": "user", "content": item}
            msg = _save(self.chat_id, **fields)
            history.append(HumanMessage(fields["content"]))
            self.emit({"type": "message", "message": msg})
            got = True
        return got

    async def _compact(self, history: list[BaseMessage], model, apps: dict[str, list[str]]) -> list[BaseMessage]:
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
        reply = await model.ainvoke(
            [SystemMessage(prompt.build(self.user.id, apps)), *older, HumanMessage(SUMMARY_PROMPT)]
        )
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
                chat.title = workspace.message_title(str(first.content))
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
            tools: dict[str, Tool] = {t.name: t for t in [*BUILTIN_TOOLS, hub.tool()] if t}
            apps = hub.catalog()
            model = base_model.bind_tools([t.schema() for t in tools.values()])
            try:
                history = await self._compact(history, base_model, apps)
            except Exception as e:  # noqa: BLE001 - compaction is best effort
                log.warning("compaction failed: %s", e)

            for _ in range(config.settings.max_agent_steps):
                system = SystemMessage(
                    content=[
                        {
                            "type": "text",
                            "text": prompt.build(self.user.id, apps),
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                )
                try:
                    ai, stream_id = await self._think(model, system, history)
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
                self.emit({"type": "message", "message": saved, "stream": stream_id})
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
            self._inject_user_messages(history)
            self._nudged.clear()
            stream = _Stream()
            call = asyncio.ensure_future(self._stream(model, [system, *history], stream))
            nudge = asyncio.ensure_future(self._nudged.wait())
            try:
                done, _ = await asyncio.wait({call, nudge}, return_when=asyncio.FIRST_COMPLETED)
                if call not in done and stream.answering:
                    return await call, stream.id
            except asyncio.CancelledError:
                self._keep_partial(stream)
                raise
            finally:
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
        saved = _save(self.chat_id, role="assistant", content=text, raw={"lc": message_to_dict(ai)})
        self.final_text = text
        self.emit({"type": "message", "message": saved, "stream": stream.id})

    async def _execute(self, calls: list[dict], tools: dict[str, Tool], hub: McpHub | None) -> list[ToolMessage]:
        async def one(call: dict, wait: list[asyncio.Future]) -> ToolMessage:
            if wait:
                await asyncio.gather(*wait, return_exceptions=True)
            ctx = ToolContext(
                self.user.id,
                start_job=lambda label, work: start_job(self.user, self.chat_id, call, label, work),
            )
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
                raw={"duration_ms": ms, **({"background": result.background} if result.background else {})},
            )
            self.emit({"type": "message", "message": saved})
            return ToolMessage(
                content=content or "(no output)",
                tool_call_id=call["id"],
                status="error" if result.is_error else "success",
            )

        # Everything runs at once, except that a call waits for earlier calls on the same resource when
        # either one writes (read then edit the same file, two edits of one file).
        started: list[tuple[str | None, bool, asyncio.Future]] = []
        for c in calls:
            tool = tools.get(c["name"])
            res = tool.resource(c["args"]) if tool and "error" not in c else None
            ro = bool(tool and tool.read_only(c["args"]))
            wait = [f for r, r_ro, f in started if res is not None and r == res and not (ro and r_ro)]
            started.append((res, ro, asyncio.ensure_future(one(c, wait))))
        try:
            return list(await asyncio.gather(*(f for _, _, f in started)))
        except BaseException:
            for _, _, f in started:
                f.cancel()
            raise


RUNS: dict[int, Run] = {}


def _new_run(user: User, chat_id: int, item: str | dict[str, Any]) -> Run:
    run = Run(user, chat_id)
    RUNS[chat_id] = run
    run.inbox.put_nowait(item)
    run.task = asyncio.create_task(run.main())
    return run


def start(user: User, chat_id: int, text: str) -> tuple[Run, bool]:
    """Send a message: start a run, or steer the active one. Returns (run, queued)."""
    run = RUNS.get(chat_id)
    if run and not run.done:
        run.steer(text)
        return run, True
    return _new_run(user, chat_id, text), False


def stop(chat_id: int) -> None:
    """Stop the chat's run and its background commands."""
    run = RUNS.get(chat_id)
    if run:
        run.stop()
    for job in [j for j in JOBS.values() if j.chat_id == chat_id]:
        job.task.cancel()


# ------------------------------------------------------------------ chat watchers

# Clients that show a chat hear about what happens outside a run they follow: a run started by a finished
# background command ({"type": "run", "run": Run}) and a note saved while no run reads it ({"type": "message"}).
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
    for cb in list(_watchers.get(chat_id, [])):
        try:
            cb(event)
        except Exception:  # noqa: BLE001 - one broken client must not break the others
            log.exception("chat watcher failed")


# ------------------------------------------------------------------ background jobs


class Job:
    def __init__(self, job_id: str, user: User, chat_id: int, call: dict, label: str):
        self.id, self.user, self.chat_id, self.call, self.label = job_id, user, chat_id, call, label
        self.task: asyncio.Task


JOBS: dict[str, Job] = {}


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
    if sum(1 for j in JOBS.values() if j.chat_id == chat_id) >= MAX_JOBS:
        raise ValueError(f"{MAX_JOBS} background commands are already running. Wait for one to finish.")
    job = Job("bg-" + uuid.uuid4().hex[:6], user, chat_id, call, label)
    JOBS[job.id] = job
    job.task = asyncio.create_task(_job_main(job, work))
    return job.id


async def _job_main(job: Job, work: Callable[[], Awaitable[ToolResult]]) -> None:
    started = time.monotonic()
    stopped = False
    try:
        result = await work()
    except asyncio.CancelledError:
        result, stopped = ToolResult(JOB_STOPPED, True), True
    except Exception as e:  # noqa: BLE001
        log.exception("background job failed")
        result = ToolResult(f"The command could not run: {e}", True)
    finally:
        JOBS.pop(job.id, None)
    ms = int((time.monotonic() - started) * 1000)
    note = _job_note(job.id, job.call["id"], job.call["name"], result.content, result.is_error, ms, job.label)
    run = RUNS.get(job.chat_id)
    if stopped:  # a stop doesn't wake the agent: save it for the next turn and tell who is watching
        _broadcast(job.chat_id, {"type": "message", "message": _save(job.chat_id, **note)})
    elif run and not run.done:
        run.inbox.put_nowait(note)  # read at the run's next step
    else:
        _broadcast(job.chat_id, {"type": "run", "run": _new_run(job.user, job.chat_id, note)})


async def run_to_completion(user: User, chat_id: int, text: str) -> tuple[str, bool]:
    run, _ = start(user, chat_id, text)
    assert run.task
    await asyncio.shield(run.task)
    return run.final_text, run.ok
