"""Agent Client Protocol (ACP) over WebSocket.

ACP (https://agentclientprotocol.com) is JSON-RPC 2.0 between a client (an editor, a chat app) and an
agent. It is the one way to talk to the agent: the web app's chat uses it, and so can any other client.

    ws(s)://<host>/api/acp      one JSON-RPC message per text frame
    auth: the web app's session cookie (same origin only), or
          `Authorization: Bearer <ACP access token>` (Settings → External apps)

Stdio-only clients (e.g. editors) connect through `python -m acf.acp_bridge`.

Methods: initialize, session/new, session/load, session/list, session/prompt, and the session/cancel
notification. A session is a chat. While the agent works the client gets `session/update` notifications
(user/agent message chunks, tool_call, tool_call_update, session_info_update). session/load replays the
history and, if the agent is working, keeps streaming live updates. A session/prompt sent while the agent
is working is a steering message: it is read at the next step and its response arrives when the run ends.

Extensions (`_acf/…` notifications and `_meta.acf`; other clients ignore them):
  _acf/notice    {sessionId, text}                connection problems, summaries, step limit, what a
                                                  background review learned
  _acf/turn_end  {sessionId, stopReason, error?}  a run this connection follows has ended
  _acf/turn_start {sessionId}                     a finished background command started a run on a
                                                  session this connection loaded or prompted
After every model call a `usage_update` (used, size) reports how full the context window is;
`_meta.acf` = {percent, measured, parts: [{name, tokens, items?, count?}]} says what fills it (see
agent/usage). session/load ends its replay with the latest one.
A background command's tool call stays `in_progress` (`_meta.acf.background` = job id) after its turn;
when the command ends, a `tool_call_update` completes it with the output.
A sub-agent (the `agent` tool) is one tool call: while it works, `tool_call_update`s carry
`_meta.acf.agent` = {model, tokens, steps: [{title, ok}]} (`ok` is null for a step that is running); the
update that completes it has the sub-agent's report as its content and the final `_meta.acf.agent`.
`_meta.acf.agent.session` is the sub-agent's own session: session/load replays it (and follows it while it
works) and answers with `_meta.acf.parent` = {sessionId, title} of the session it belongs to. It is
read-only (session/prompt and session/cancel are refused) and session/list leaves it out.
Projects: session/new with `_meta.acf.projectId` starts the session in that project (its instructions and
folder reach the agent); session/list marks such sessions with `_meta.acf.projectId` and session/load
answers with `_meta.acf.project` = {id, name}.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from acf import config, models, projects, skills, workspace
from acf.agent import loop as agent
from acf.agent import usage as context_usage
from acf.agent.tools import tool_kind, tool_title
from acf.auth import COOKIE, user_for_acp_token, user_for_session
from acf.bus import Feed
from acf.db import Chat, Message, Project, User, session_scope, utcnow

log = logging.getLogger("acf.acp")
router = APIRouter()

PROTOCOL_VERSION = 1
MAX_PROMPT = 100_000
WORKSPACE = "/workspace"
SUMMARY_NOTICE = "Earlier messages were summarised to keep things fast."
READ_ONLY = "A sub-agent's session is read-only. Send your message to the chat it belongs to."

# JSON-RPC error codes
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603
NOT_FOUND = -32002  # ACP: resource not found
RUN_FAILED = -32000

try:
    VERSION = version("ai-chatbot-framework")
except PackageNotFoundError:  # pragma: no cover - running from a plain checkout
    VERSION = "0"


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


# ------------------------------------------------------------------ translation: stored messages -> ACP updates


def _text(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def user_blocks(text: str) -> list[dict[str, Any]]:
    """A stored user message as ACP content blocks: its text, then a resource_link per attached file."""
    links = [{"type": "resource_link", "uri": uri, "name": name} for name, uri in workspace.ATTACHED_RE.findall(text)]
    rest = skills.strip_references(workspace.ATTACHED_RE.sub("", text)).strip()
    return ([_text(rest)] if rest or not links else []) + links


def user_updates(m: dict[str, Any]) -> list[dict[str, Any]]:
    meta = {"acf": {"messageId": m["id"]}}
    return [{"sessionUpdate": "user_message_chunk", "content": b, "_meta": meta} for b in user_blocks(m["content"])]


def assistant_updates(m: dict[str, Any], with_text: bool = True) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if m["content"] and with_text:
        out.append(
            {
                "sessionUpdate": "agent_message_chunk",
                "content": _text(m["content"]),
                "_meta": {"acf": {"messageId": m["id"]}},
            }
        )
    for c in m["tool_calls"]:
        update: dict[str, Any] = {
            "sessionUpdate": "tool_call",
            "toolCallId": c["id"],
            "title": tool_title(c["name"], c["arguments"] or {}),
            "kind": tool_kind(c["name"]),
            "status": "pending",
            "rawInput": c["arguments"],
            "_meta": {"acf": {"tool": c["name"]}},
        }
        if c["name"] in ("read", "write", "edit") and (c["arguments"] or {}).get("path"):
            update["locations"] = [{"path": f"{WORKSPACE}/{str(c['arguments']['path']).lstrip('/')}"}]
        out.append(update)
    return out


def tool_result_updates(m: dict[str, Any]) -> list[dict[str, Any]]:
    """A tool result, or a background command's note (it finishes the tool call that started it)."""
    meta: dict[str, Any] = {"durationMs": m["duration_ms"]}
    status = "failed" if m["is_error"] else "completed"
    if m["background"]:
        meta["background"] = m["background"]
        if m["role"] == "tool":
            status = "in_progress"  # started; the note with its output completes it
    if m.get("agent"):
        meta["agent"] = m["agent"]
    return [
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": m["tool_call_id"],
            "status": status,
            "content": [{"type": "content", "content": _text(m["content"])}],
            "_meta": {"acf": meta},
        }
    ]


def message_updates(m: dict[str, Any]) -> list[dict[str, Any]]:
    """One stored message as ACP updates; a summary or a review note becomes an `_acf/notice` (marked with
    `notice`)."""
    role = m["role"]
    if role == "user" and m["background"] and m["tool_call_id"]:
        return tool_result_updates(m)
    if role == "user":
        return user_updates(m)
    if role == "assistant":
        return assistant_updates(m)
    if role == "tool":
        return tool_result_updates(m)
    if role == "summary":
        return [{"notice": SUMMARY_NOTICE}]
    if role == "note" and m["content"]:
        learned = m.get("learned")
        return [{"notice": m["content"], **({"learned": {"id": m["id"], **learned}} if learned else {})}]
    return []


def prompt_text(blocks: Any) -> str:
    """ACP content blocks -> the text the agent reads. Text, resource links and embedded text resources.

    Links to files in the workspace (file:///workspace/…, e.g. files attached in the web chat) become
    `[Attached file: name](uri)` lines, which the agent opens with its read tool.
    """
    if not isinstance(blocks, list) or not blocks:
        raise RpcError(INVALID_PARAMS, "prompt must be a non-empty list of content blocks")
    parts: list[str] = []
    for b in blocks:
        kind = b.get("type") if isinstance(b, dict) else None
        if kind == "text":
            parts.append(str(b.get("text", "")))
        elif kind == "resource_link":
            uri, name = str(b.get("uri", "")), str(b.get("name") or b.get("uri", "")).replace("]", ")")
            if uri.startswith(f"file://{WORKSPACE}/") and "\n" not in uri + name:
                uri = uri.replace(" ", "%20").replace("(", "%28").replace(")", "%29")  # keep the link one token
                parts.append(workspace.ATTACHED.format(name=name, uri=uri))
            else:
                parts.append(f"[{name}]({uri})")
        elif kind == "resource" and isinstance(b.get("resource"), dict) and "text" in b["resource"]:
            r = b["resource"]
            parts.append(f'<file uri="{r.get("uri", "")}">\n{r["text"]}\n</file>')
        else:
            raise RpcError(INVALID_PARAMS, f"Unsupported content block: {kind}. Send text or text resources.")
    text = "\n\n".join(p for p in parts if p).strip()
    if not text:
        raise RpcError(INVALID_PARAMS, "The prompt is empty")
    if len(text) > MAX_PROMPT:
        raise RpcError(INVALID_PARAMS, f"The prompt is too long (max {MAX_PROMPT} characters)")
    return text


# ------------------------------------------------------------------ connection


class _Reply:
    """A handler result plus work to start once the response has been sent."""

    def __init__(self, result: Any, after=None):
        self.result, self.after = result, after


class Connection:
    def __init__(self, ws: WebSocket, user_id: int):
        self.ws = ws
        self.user_id = user_id
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._watchers: dict[int, tuple[str, asyncio.Task]] = {}  # chat -> (run id, forwarding task)
        self._chats: dict[int, Any] = {}  # chat id -> unwatch, for sessions this connection shows

    # -- io
    async def send(self, msg: dict[str, Any]) -> None:
        async with self._lock:
            await self.ws.send_text(json.dumps(msg))

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _emit(self, sid: str, updates: list[dict[str, Any]]) -> None:
        for u in updates:
            if "notice" in u:
                learned = {"_meta": {"acf": {"learned": u["learned"]}}} if "learned" in u else {}
                await self.notify("_acf/notice", {"sessionId": sid, "text": u["notice"], **learned})
            else:
                await self.notify("session/update", {"sessionId": sid, "update": u})

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def serve(self) -> None:
        try:
            while True:
                frame = await self.ws.receive()
                if frame["type"] == "websocket.disconnect":
                    break
                raw = frame.get("text") or (frame.get("bytes") or b"").decode(errors="replace")
                try:
                    msg = json.loads(raw)
                except ValueError:
                    await self.send(
                        {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}
                    )
                    continue
                if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
                    err = {"code": INVALID_REQUEST, "message": "Invalid request"}
                    await self.send({"jsonrpc": "2.0", "id": None, "error": err})
                    continue
                if "method" not in msg:
                    continue  # a response; this agent sends no requests to the client
                if "id" in msg:
                    self._spawn(self._request(msg))
                else:
                    await self._notification(msg["method"], msg.get("params") or {})
        except WebSocketDisconnect:
            pass
        finally:
            # The agent keeps working when a client goes away; only this connection's listeners stop.
            for unwatch in self._chats.values():
                unwatch()
            for task in list(self._tasks):
                task.cancel()

    async def _request(self, msg: dict[str, Any]) -> None:
        mid, method = msg["id"], msg["method"]
        try:
            handler = METHODS.get(method)
            if handler is None:
                raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
            params = msg.get("params") or {}
            if not isinstance(params, dict):
                raise RpcError(INVALID_PARAMS, "params must be an object")
            out = await handler(self, params)
            reply = out if isinstance(out, _Reply) else _Reply(out)
            await self.send({"jsonrpc": "2.0", "id": mid, "result": reply.result})
            if reply.after:
                reply.after()
        except RpcError as e:
            await self._send_quietly({"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": e.message}})
        except (asyncio.CancelledError, WebSocketDisconnect):
            raise
        except Exception:  # noqa: BLE001
            log.exception("ACP %s failed", method)
            await self._send_quietly(
                {"jsonrpc": "2.0", "id": mid, "error": {"code": INTERNAL_ERROR, "message": "Internal error"}}
            )

    async def _send_quietly(self, msg: dict[str, Any]) -> None:
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await self.send(msg)

    async def _notification(self, method: str, params: dict[str, Any]) -> None:
        if method == "session/cancel":
            with contextlib.suppress(RpcError):
                agent.stop(self._own_chat(params, write=True))

    # -- helpers
    def _watch(self, chat_id: int) -> None:
        """Hear about runs a background command starts in this chat, and notes saved outside a run."""
        if chat_id in self._chats:
            return
        sid = str(chat_id)

        def on_event(e: dict[str, Any]) -> None:
            if e["type"] == "run":
                current = self._watchers.get(chat_id)
                if not (current and current[0] == e["run_id"]):
                    self._spawn(self.notify("_acf/turn_start", {"sessionId": sid}))
                    self._follow(agent.feed(chat_id, e["run_id"]), chat_id)
            elif e["type"] == "message":
                self._spawn(self._emit(sid, message_updates(e["message"])))
            elif e["type"] == "title":  # named after the run ended (acf.agent.titles)
                update = {
                    "sessionUpdate": "session_info_update",
                    "title": e["title"],
                    "updatedAt": utcnow().isoformat() + "Z",
                }
                self._spawn(self._emit(sid, [update]))

        self._chats[chat_id] = agent.watch_chat(chat_id, on_event)

    def _user(self) -> User:
        with session_scope() as db:
            user = db.get(User, self.user_id)
            if user is None:
                raise RpcError(INVALID_REQUEST, "This account no longer exists")
            return user

    def _own_chat(self, params: dict[str, Any], write: bool = False) -> int:
        """The user's chat for `sessionId`. `write`: for sending to it, which a sub-agent's session refuses."""
        sid = params.get("sessionId")
        if not isinstance(sid, str) or not sid.isdigit():
            raise RpcError(INVALID_PARAMS, "sessionId must be a session id from session/new or session/list")
        with session_scope() as db:
            chat = db.get(Chat, int(sid))
            if not chat or chat.user_id != self.user_id:
                raise RpcError(NOT_FOUND, f"Session {sid} not found")
            if write and chat.parent_id is not None:
                raise RpcError(INVALID_REQUEST, READ_ONLY)
            return chat.id

    def _follow(
        self,
        run: Feed,
        chat_id: int,
        *,
        skip_user: str | None = None,
        after_id: int = 0,
        answered: set[str] | None = None,
        replayed: set[str] | None = None,
        gate: asyncio.Event | None = None,
    ) -> asyncio.Task:
        """Forward a run's events to this client (once per run), then send `_acf/turn_end`."""
        current = self._watchers.get(chat_id)
        if current and current[0] == run.run_id:
            return current[1]
        queue = run.listen()  # registered now, so nothing between here and the first await is missed
        # Streams whose message is already stored (and so replayed by session/load) are not re-sent.
        replayed = (replayed or set()) | {
            e.get("stream") for e in run.events if e["type"] == "message" and e["message"]["id"] <= after_id
        }
        task = self._spawn(self._forward(run, chat_id, queue, skip_user, after_id, answered or set(), replayed, gate))
        self._watchers[chat_id] = (run.run_id, task)
        return task

    async def _forward(
        self,
        run: Feed,
        chat_id: int,
        queue: asyncio.Queue,
        skip_user: str | None,
        after_id: int,
        answered: set[str],
        replayed: set[str | None],
        gate: asyncio.Event | None,
    ) -> None:
        sid = str(chat_id)
        streamed: set[str] = set()  # streams whose text this client got as deltas
        try:
            if gate:
                await gate.wait()
            while True:
                e = await queue.get()
                kind = e["type"]
                if kind == "done":
                    end: dict[str, Any] = {"sessionId": sid, "stopReason": e.get("stop_reason") or "end_turn"}
                    if e.get("error"):
                        end["error"] = e["error"]
                    break
                if kind == "message":
                    m = e["message"]
                    if m["id"] <= after_id:
                        continue  # already replayed by session/load
                    if m["role"] == "user" and skip_user is not None and m["content"] == skip_user:
                        skip_user = None  # the prompt that started this run; its sender has it
                        continue
                    if m["role"] == "assistant":
                        await self._emit(sid, assistant_updates(m, with_text=e.get("stream") not in streamed))
                    else:
                        await self._emit(sid, message_updates(m))
                elif kind == "delta" and e["stream"] not in replayed:
                    if e["kind"] == "text":
                        streamed.add(e["stream"])
                    update = "agent_message_chunk" if e["kind"] == "text" else "agent_thought_chunk"
                    meta = {"acf": {"messageId": e["stream"]}}
                    await self._emit(sid, [{"sessionUpdate": update, "content": _text(e["text"]), "_meta": meta}])
                elif kind == "tool_start" and e["id"] not in answered:
                    await self._emit(
                        sid, [{"sessionUpdate": "tool_call_update", "toolCallId": e["id"], "status": "in_progress"}]
                    )
                elif kind == "agent" and e["id"] not in answered:
                    update = {"sessionUpdate": "tool_call_update", "toolCallId": e["id"], "status": "in_progress"}
                    await self._emit(sid, [{**update, "_meta": {"acf": {"agent": e["agent"]}}}])
                elif kind == "usage":
                    await self._emit(sid, [context_usage.update(e["usage"])])
                elif kind == "notice":
                    await self._emit(sid, [{"notice": e["text"]}])
                elif kind == "title":
                    update = {
                        "sessionUpdate": "session_info_update",
                        "title": e["title"],
                        "updatedAt": utcnow().isoformat() + "Z",
                    }
                    await self._emit(sid, [update])
            await self.notify("_acf/turn_end", end)
        finally:
            run.unlisten(queue)
            if self._watchers.get(chat_id, (None,))[0] == run.run_id:
                del self._watchers[chat_id]


# ------------------------------------------------------------------ methods


async def initialize(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "agentCapabilities": {
            "loadSession": True,
            "promptCapabilities": {"image": False, "audio": False, "embeddedContext": True},
            "mcpCapabilities": {"http": False, "sse": False},
            "sessionCapabilities": {"list": {}},
        },
        "authMethods": [],
        "agentInfo": {"name": "ai-chatbot-framework", "title": "AI Chatbot Framework", "version": VERSION},
    }


async def authenticate(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    return {}  # the connection is authenticated when it is opened


async def session_new(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    # `cwd` and `mcpServers` are accepted and ignored: the agent works in its own sandbox, with the
    # connections configured in the web app.
    project_id = ((params.get("_meta") or {}).get("acf") or {}).get("projectId")
    with session_scope() as db:
        if project_id is not None:
            try:
                projects.own(db, conn.user_id, project_id if isinstance(project_id, int) else -1)
            except ValueError as e:
                raise RpcError(INVALID_PARAMS, "Project not found") from e
        chat = Chat(user_id=conn.user_id, title="New chat", project_id=project_id)
        db.add(chat)
        db.flush()
        sid = str(chat.id)
    return {"sessionId": sid, "configOptions": models.config_options(conn._user())}


async def session_list(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as db:
        rows = (
            db.query(Chat)
            .filter_by(user_id=conn.user_id, parent_id=None)
            .order_by(Chat.updated_at.desc())
            .limit(200)
            .all()
        )
        sessions = [
            {
                "sessionId": str(c.id),
                "cwd": WORKSPACE,
                "title": c.title,
                "updatedAt": c.updated_at.isoformat() + "Z",
                **({"_meta": {"acf": {"projectId": c.project_id}}} if c.project_id else {}),
            }
            for c in rows
        ]
    return {"sessions": sessions, "nextCursor": None}


async def session_load(conn: Connection, params: dict[str, Any]) -> _Reply:
    chat_id = conn._own_chat(params)
    sid = str(chat_id)
    run = agent.active(chat_id)
    gate = asyncio.Event()
    meta: dict[str, Any] = {"running": run is not None}
    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        parent = db.get(Chat, chat.parent_id) if chat and chat.parent_id else None
        if chat:
            meta["title"] = chat.title
        if chat and parent:  # a sub-agent's session
            meta["parent"] = {"sessionId": str(parent.id), "title": parent.title}
        project = db.get(Project, chat.project_id) if chat and chat.project_id else None
        if project:
            meta["project"] = {"id": project.id, "name": project.name}
        choice = (chat.model, chat.effort) if chat else ("", "")
        stored = db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
        rows = [m.to_dict() for m in stored]
        last_usage = next(
            (m.raw["usage"] for m in reversed(stored) if m.role == "assistant" and (m.raw or {}).get("usage")), None
        )
        # Streams whose answer is stored: their deltas may still reach a feed that trails another process.
        replayed = {(m.raw or {}).get("stream") for m in stored if m.role == "assistant"} - {None}
    answered = {m["tool_call_id"] for m in rows if m["role"] == "tool"}
    conn._watch(chat_id)
    if run:  # listen before replaying, so events emitted meanwhile are queued, not lost
        after_id = rows[-1]["id"] if rows else 0
        conn._follow(run, chat_id, after_id=after_id, answered=answered, replayed=replayed, gate=gate)
    for m in rows:
        await conn._emit(sid, message_updates(m))
    if last_usage:
        await conn._emit(sid, [context_usage.update(last_usage)])
    options = models.config_options(conn._user(), *choice)
    return _Reply({"configOptions": options, "_meta": {"acf": meta}}, after=gate.set)


async def session_set_config_option(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    """Choose this chat's model or effort. Applies from the next model call."""
    chat_id = conn._own_chat(params, write=True)
    config_id, value = params.get("configId"), params.get("value")
    user = conn._user()
    if not isinstance(value, str) or len(value) > 300:
        raise RpcError(INVALID_PARAMS, "value must be one of the option's values")
    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        current = chat.model or models.user_default(user)
        if config_id == "model":
            if value not in {o["value"] for o in models.config_options(user, current)[0]["options"]}:
                raise RpcError(INVALID_PARAMS, f"Unknown model: {value}")
            chat.model = value
            if chat.effort and chat.effort not in models.info(value).efforts:
                chat.effort = ""
        elif config_id == "effort":
            if value not in models.info(current).efforts:
                raise RpcError(INVALID_PARAMS, f"Unknown effort for this model: {value}")
            chat.effort = value
        else:
            raise RpcError(INVALID_PARAMS, f"Unknown config option: {config_id}")
        choice = (chat.model, chat.effort)
    return {"configOptions": models.config_options(user, *choice)}


async def session_prompt(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    chat_id = conn._own_chat(params, write=True)
    text = skills.reference(conn.user_id, prompt_text(params.get("prompt")))  # /name calls a skill
    conn._watch(chat_id)
    run, queued = agent.start(conn._user(), chat_id, text)
    task = conn._follow(run, chat_id, skip_user=None if queued else text)
    await asyncio.wait({task})
    done = run.result or {}
    if done.get("error"):
        raise RpcError(RUN_FAILED, done["error"])
    return {"stopReason": done.get("stop_reason") or "end_turn"}


METHODS = {
    "initialize": initialize,
    "authenticate": authenticate,
    "session/new": session_new,
    "session/load": session_load,
    "session/list": session_list,
    "session/prompt": session_prompt,
    "session/set_config_option": session_set_config_option,
}


# ------------------------------------------------------------------ endpoint


def _same_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin")
    if not origin:
        return True  # not a browser
    return urlparse(origin).netloc == ws.headers.get("host", "") or origin.rstrip("/") == config.settings.public_url


def authenticate_ws(ws: WebSocket) -> int | None:
    """User id for a bearer ACP token, or for the web app's session cookie on a same-origin request."""
    auth = ws.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    with session_scope() as db:
        if bearer:
            user = user_for_acp_token(db, bearer)
        elif ws.cookies.get(COOKIE) and _same_origin(ws):
            user = user_for_session(db, ws.cookies[COOKIE])
        else:
            user = None
        return user.id if user else None


@router.websocket("/api/acp")
async def acp_endpoint(ws: WebSocket) -> None:
    user_id = authenticate_ws(ws)
    if user_id is None:
        await ws.close(code=1008, reason="Not signed in")  # before accept: the handshake gets HTTP 403
        return
    await ws.accept()
    await Connection(ws, user_id).serve()
