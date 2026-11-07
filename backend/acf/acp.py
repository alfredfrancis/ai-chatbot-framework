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
  _acf/notice    {sessionId, text}                connection problems, summaries, step limit
  _acf/turn_end  {sessionId, stopReason, error?}  a run this connection follows has ended
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

from acf import config
from acf.agent import loop as agent
from acf.auth import COOKIE, user_for_acp_token, user_for_session
from acf.db import Chat, Message, User, session_scope, utcnow

log = logging.getLogger("acf.acp")
router = APIRouter()

PROTOCOL_VERSION = 1
MAX_PROMPT = 100_000
WORKSPACE = "/workspace"
SUMMARY_NOTICE = "Earlier messages were summarised to keep things fast."

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


def tool_kind(name: str) -> str:
    return {"read": "read", "write": "edit", "edit": "edit", "bash": "execute"}.get(name, "other")


def tool_title(name: str, args: dict[str, Any]) -> str:
    path = str(args.get("path", ""))
    if name == "bash":
        return f"Ran {str(args.get('command', '')).splitlines()[0][:200] if args.get('command') else ''}".strip()
    if name == "read":
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
            return f"Used skill {parts[1]}"
        return f"Read {path}"
    if name in ("write", "edit"):
        return f"{'Wrote' if name == 'write' else 'Edited'} {path}"
    if name == "mcp_call":
        return f"Used {args.get('server', '')} · {args.get('tool', '')}"
    if name.startswith("mcp__") and "__" in name[5:]:
        server, tool = name[5:].split("__", 1)
        return f"Used {server} · {tool}"
    return f"Used {name}"


def user_updates(m: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "sessionUpdate": "user_message_chunk",
            "content": _text(m["content"]),
            "_meta": {"acf": {"messageId": m["id"]}},
        }
    ]


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
    return [
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": m["tool_call_id"],
            "status": "failed" if m["is_error"] else "completed",
            "content": [{"type": "content", "content": _text(m["content"])}],
            "_meta": {"acf": {"durationMs": m["duration_ms"]}},
        }
    ]


def message_updates(m: dict[str, Any]) -> list[dict[str, Any]]:
    """One stored message as ACP updates; a summary becomes an `_acf/notice` (marked with `notice`)."""
    role = m["role"]
    if role == "user":
        return user_updates(m)
    if role == "assistant":
        return assistant_updates(m)
    if role == "tool":
        return tool_result_updates(m)
    if role == "summary":
        return [{"notice": SUMMARY_NOTICE}]
    return []


def prompt_text(blocks: Any) -> str:
    """ACP content blocks -> the text the agent reads. Text, resource links and embedded text resources."""
    if not isinstance(blocks, list) or not blocks:
        raise RpcError(INVALID_PARAMS, "prompt must be a non-empty list of content blocks")
    parts: list[str] = []
    for b in blocks:
        kind = b.get("type") if isinstance(b, dict) else None
        if kind == "text":
            parts.append(str(b.get("text", "")))
        elif kind == "resource_link":
            parts.append(f"[{b.get('name') or b.get('uri')}]({b.get('uri')})")
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
        self._watchers: dict[int, tuple[agent.Run, asyncio.Task]] = {}

    # -- io
    async def send(self, msg: dict[str, Any]) -> None:
        async with self._lock:
            await self.ws.send_text(json.dumps(msg))

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    async def _emit(self, sid: str, updates: list[dict[str, Any]]) -> None:
        for u in updates:
            if "notice" in u:
                await self.notify("_acf/notice", {"sessionId": sid, "text": u["notice"]})
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
                run = agent.RUNS.get(self._own_chat(params))
                if run:
                    run.stop()

    # -- helpers
    def _user(self) -> User:
        with session_scope() as db:
            user = db.get(User, self.user_id)
            if user is None:
                raise RpcError(INVALID_REQUEST, "This account no longer exists")
            return user

    def _own_chat(self, params: dict[str, Any]) -> int:
        sid = params.get("sessionId")
        if not isinstance(sid, str) or not sid.isdigit():
            raise RpcError(INVALID_PARAMS, "sessionId must be a session id from session/new or session/list")
        with session_scope() as db:
            chat = db.get(Chat, int(sid))
            if not chat or chat.user_id != self.user_id:
                raise RpcError(NOT_FOUND, f"Session {sid} not found")
            return chat.id

    def _follow(
        self,
        run: agent.Run,
        chat_id: int,
        *,
        skip_user: str | None = None,
        after_id: int = 0,
        answered: set[str] | None = None,
        gate: asyncio.Event | None = None,
    ) -> asyncio.Task:
        """Forward a run's events to this client (once per run), then send `_acf/turn_end`."""
        current = self._watchers.get(chat_id)
        if current and current[0] is run:
            return current[1]
        queue = run.listen()  # registered now, so nothing between here and the first await is missed
        # Streams whose message is already stored (and so replayed by session/load) are not re-sent.
        replayed = {e.get("stream") for e in run.events if e["type"] == "message" and e["message"]["id"] <= after_id}
        task = self._spawn(self._forward(run, chat_id, queue, skip_user, after_id, answered or set(), replayed, gate))
        self._watchers[chat_id] = (run, task)
        return task

    async def _forward(
        self,
        run: agent.Run,
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
                elif kind == "notice":
                    await self._emit(sid, [{"notice": e["text"]}])
                elif kind == "title":
                    update = {
                        "sessionUpdate": "session_info_update",
                        "title": e["title"],
                        "updatedAt": utcnow().isoformat() + "Z",
                    }
                    await self._emit(sid, [update])
            end: dict[str, Any] = {"sessionId": sid, "stopReason": run.stop_reason}
            if run.error:
                end["error"] = run.error
            await self.notify("_acf/turn_end", end)
        finally:
            run.unlisten(queue)
            if self._watchers.get(chat_id, (None,))[0] is run:
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
    with session_scope() as db:
        chat = Chat(user_id=conn.user_id, title="New chat")
        db.add(chat)
        db.flush()
        return {"sessionId": str(chat.id)}


async def session_list(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as db:
        rows = db.query(Chat).filter_by(user_id=conn.user_id).order_by(Chat.updated_at.desc()).limit(200).all()
        sessions = [
            {"sessionId": str(c.id), "cwd": WORKSPACE, "title": c.title, "updatedAt": c.updated_at.isoformat() + "Z"}
            for c in rows
        ]
    return {"sessions": sessions, "nextCursor": None}


async def session_load(conn: Connection, params: dict[str, Any]) -> _Reply:
    chat_id = conn._own_chat(params)
    sid = str(chat_id)
    run = agent.RUNS.get(chat_id)
    run = run if run and not run.done else None
    gate = asyncio.Event()
    with session_scope() as db:
        rows = [m.to_dict() for m in db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()]
    answered = {m["tool_call_id"] for m in rows if m["role"] == "tool"}
    if run:  # listen before replaying, so events emitted meanwhile are queued, not lost
        conn._follow(run, chat_id, after_id=rows[-1]["id"] if rows else 0, answered=answered, gate=gate)
    for m in rows:
        await conn._emit(sid, message_updates(m))
    return _Reply({"_meta": {"acf": {"running": run is not None}}}, after=gate.set)


async def session_prompt(conn: Connection, params: dict[str, Any]) -> dict[str, Any]:
    chat_id = conn._own_chat(params)
    text = prompt_text(params.get("prompt"))
    run, queued = agent.start(conn._user(), chat_id, text)
    task = conn._follow(run, chat_id, skip_user=None if queued else text)
    await asyncio.wait({task})
    if run.error:
        raise RpcError(RUN_FAILED, run.error)
    return {"stopReason": run.stop_reason}


METHODS = {
    "initialize": initialize,
    "authenticate": authenticate,
    "session/new": session_new,
    "session/load": session_load,
    "session/list": session_list,
    "session/prompt": session_prompt,
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
