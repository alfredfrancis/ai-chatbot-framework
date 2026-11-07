"""A small ACP client for tests, talking to the app in-process over an ASGI WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
from typing import Any


class Rejected(Exception):
    def __init__(self, code: int):
        super().__init__(f"WebSocket rejected ({code})")
        self.code = code


class RpcError(Exception):
    def __init__(self, error: dict):
        super().__init__(error["message"])
        self.code, self.message = error["code"], error["message"]


class AsgiWebSocket:
    """Drive an ASGI app's WebSocket endpoint from the same event loop (httpx has no WebSocket support)."""

    def __init__(self, app, path: str, headers: dict[str, str] | None = None):
        self.app, self.path, self.headers = app, path, headers or {}
        self._in: asyncio.Queue = asyncio.Queue()
        self._out: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def __aenter__(self) -> AsgiWebSocket:
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "path": self.path,
            "raw_path": self.path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"test")] + [(k.lower().encode(), v.encode()) for k, v in self.headers.items()],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
            "subprotocols": [],
            "state": {},
            "extensions": {},
        }
        self._task = asyncio.create_task(self.app(scope, self._in.get, self._out.put))
        await self._in.put({"type": "websocket.connect"})
        first = await asyncio.wait_for(self._out.get(), 10)
        if first["type"] != "websocket.accept":
            await self._task
            raise Rejected(first.get("code", 403))
        return self

    async def send_text(self, text: str) -> None:
        await self._in.put({"type": "websocket.receive", "text": text})

    async def receive_text(self) -> str | None:
        msg = await self._out.get()
        if msg["type"] == "websocket.close":
            return None
        return msg.get("text")

    async def __aexit__(self, *exc) -> None:
        await self._in.put({"type": "websocket.disconnect", "code": 1000})
        if self._task:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._task, 10)


class Acp:
    """JSON-RPC over the socket: requests resolve futures; notifications are collected."""

    def __init__(self, ws: AsgiWebSocket):
        self.ws = ws
        self.ids = itertools.count(1)
        self.pending: dict[int, asyncio.Future] = {}
        self.notifications: list[dict[str, Any]] = []
        self.changed = asyncio.Event()
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        while (text := await self.ws.receive_text()) is not None:
            msg = json.loads(text)
            if "id" in msg and msg["id"] in self.pending:
                self.pending.pop(msg["id"]).set_result(msg)
            else:
                self.notifications.append(msg)
            self.changed.set()

    async def raw(self, payload: str) -> None:
        await self.ws.send_text(payload)

    async def request(self, method: str, params: dict | None = None, timeout: float = 60) -> Any:
        mid = next(self.ids)
        fut = asyncio.get_running_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send_text(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}))
        msg = await asyncio.wait_for(fut, timeout)
        if "error" in msg:
            raise RpcError(msg["error"])
        return msg["result"]

    async def notify(self, method: str, params: dict) -> None:
        await self.ws.send_text(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}))

    async def wait_for(self, pred, timeout: float = 30) -> dict:
        """Wait until a notification matching pred arrives; returns it."""

        async def loop():
            while True:
                for n in self.notifications:
                    if pred(n):
                        return n
                self.changed.clear()
                await self.changed.wait()

        return await asyncio.wait_for(loop(), timeout)

    def updates(self, sid: str | None = None) -> list[dict]:
        return [
            n["params"]["update"]
            for n in self.notifications
            if n.get("method") == "session/update" and (sid is None or n["params"]["sessionId"] == sid)
        ]

    def close(self) -> None:
        self._reader.cancel()


@contextlib.asynccontextmanager
async def acp_connect(client, headers: dict[str, str] | None = None):
    """Open an ACP connection as the httpx test client's signed-in user (its session cookie)."""
    h = dict(headers or {})
    cookie = client.cookies.get("acf_session")
    if cookie and "authorization" not in {k.lower() for k in h}:
        h["cookie"] = f"acf_session={cookie}"
    async with AsgiWebSocket(client._transport.app, "/api/acp", h) as ws:
        conn = Acp(ws)
        try:
            yield conn
        finally:
            conn.close()


def joined(chunks: list[dict]) -> dict[Any, str]:
    out: dict[Any, str] = {}
    for i, u in enumerate(chunks):
        key = u.get("_meta", {}).get("acf", {}).get("messageId", f"#{i}")
        out[key] = out.get(key, "") + u["content"]["text"]
    return out


class Turn:
    """What one session/prompt produced."""

    def __init__(self, updates: list[dict], notices: list[str], stop_reason: str | None, error: str | None):
        self.updates, self.notices, self.stop_reason, self.error = updates, notices, stop_reason, error

    def of(self, kind: str) -> list[dict]:
        return [u for u in self.updates if u["sessionUpdate"] == kind]

    @property
    def texts(self) -> list[str]:
        """Agent messages in order, each joined from its streamed chunks (grouped by _meta.acf.messageId)."""
        return list(joined(self.of("agent_message_chunk")).values())

    @property
    def thoughts(self) -> list[str]:
        return list(joined(self.of("agent_thought_chunk")).values())

    @property
    def final(self) -> str:
        return self.texts[-1] if self.texts else ""

    @property
    def results(self) -> list[dict]:
        """Finished tool calls: {id, status, text, durationMs}."""
        return [
            {
                "id": u["toolCallId"],
                "status": u["status"],
                "text": u["content"][0]["content"]["text"],
                "durationMs": u["_meta"]["acf"]["durationMs"],
            }
            for u in self.of("tool_call_update")
            if u["status"] in ("completed", "failed")
        ]
