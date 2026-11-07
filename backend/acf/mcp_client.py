"""MCP servers from a Claude-Desktop-style JSON config.

{
  "mcpServers": {
    "files":  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]},
    "linear": {"url": "https://mcp.linear.app/mcp"},
    "custom": {"url": "https://example.com/mcp", "headers": {"X-Api-Key": "…"}, "oauth": {"client_id": "…"}}
  }
}

Local (stdio) servers are started INSIDE the user's sandbox. Remote servers use Streamable HTTP and
OAuth when the server asks for it (HTTP 401).

Each connection lives in its own asyncio task so that the SDK's task groups and cancel scopes are
always entered and exited in the same task.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from acf import oauth
from acf.agent.tools import Tool, ToolContext, ToolResult
from acf.sandbox import Sandbox

CONNECT_TIMEOUT = 60
CALL_TIMEOUT = 300
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class ConfigError(ValueError):
    pass


@dataclass
class ServerConfig:
    name: str
    transport: str  # stdio | http
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    oauth: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


def parse_config(text: str) -> dict[str, ServerConfig]:
    try:
        data = json.loads(text or "{}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON on line {e.lineno}: {e.msg}") from e
    if not isinstance(data, dict):
        raise ConfigError("The configuration must be a JSON object")
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ConfigError('"mcpServers" must be an object')
    out: dict[str, ServerConfig] = {}
    for name, cfg in servers.items():
        if not _NAME_RE.match(name):
            raise ConfigError(f'Server name "{name}" may only use letters, numbers, - and _ (max 40)')
        if not isinstance(cfg, dict):
            raise ConfigError(f'"{name}" must be an object')
        enabled = cfg.get("enabled", True) is not False and cfg.get("disabled", False) is not True
        if cfg.get("url"):
            if not str(cfg["url"]).startswith(("http://", "https://")):
                raise ConfigError(f'"{name}": url must start with http:// or https://')
            raw_oauth = cfg.get("oauth") or {}
            out[name] = ServerConfig(
                name=name,
                transport="http",
                url=cfg["url"],
                headers={str(k): str(v) for k, v in (cfg.get("headers") or {}).items()},
                oauth=raw_oauth if isinstance(raw_oauth, dict) else {},
                enabled=enabled,
            )
        elif cfg.get("command"):
            args = cfg.get("args") or []
            if not isinstance(args, list):
                raise ConfigError(f'"{name}": args must be a list')
            out[name] = ServerConfig(
                name=name,
                transport="stdio",
                command=str(cfg["command"]),
                args=[str(a) for a in args],
                env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
                enabled=enabled,
            )
        else:
            raise ConfigError(f'"{name}" needs either a "command" (local) or a "url" (remote)')
    return out


def tool_name(server: str, tool: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]", "_", f"mcp__{server}__{tool}")
    return name[:64]


def _result_text(result: Any) -> str:
    parts: list[str] = []
    for block in result.content or []:
        kind = getattr(block, "type", "")
        if kind == "text":
            parts.append(block.text)
        elif kind == "resource":
            res = block.resource
            parts.append(getattr(res, "text", None) or f"[resource {getattr(res, 'uri', '')}]")
        elif kind == "resource_link":
            parts.append(f"[link {getattr(block, 'uri', '')}]")
        else:
            parts.append(f"[{kind} content]")
    if not parts and result.structured_content is not None:
        parts.append(json.dumps(result.structured_content))
    return "\n".join(parts) or "(no output)"


class NeedsAuth(Exception):
    pass


class _Connection:
    def __init__(self, cfg: ServerConfig, user_id: int, sandbox: Sandbox):
        self.cfg = cfg
        self.user_id = user_id
        self.sandbox = sandbox
        self.tools: list[Any] = []
        self.error: str | None = None
        self.needs_auth = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self._task: asyncio.Task | None = None

    @asynccontextmanager
    async def _client(self):
        cfg = self.cfg
        if cfg.transport == "stdio":
            await self.sandbox.ensure()
            command, args, cwd = self.sandbox.stdio_command(cfg.command, cfg.args, cfg.env)
            env = cfg.env if self.sandbox.kind == "local" else None
            params = StdioServerParameters(command=command, args=args, env=env, cwd=cwd)
            async with Client(params, read_timeout_seconds=CALL_TIMEOUT) as client:
                yield client
            return
        headers = dict(cfg.headers)
        token = await oauth.access_token(self.user_id, cfg.name, cfg.url)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif "authorization" not in {k.lower() for k in headers}:
            status, _ = await oauth.probe(cfg.url, headers)
            if status == 401:
                raise NeedsAuth()
            if status == 0:
                raise ConnectionError(f"Could not reach {urlparse(cfg.url).netloc}. Check the address.")
        async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(CALL_TIMEOUT, connect=20)) as http:
            async with Client(
                streamable_http_client(cfg.url, http_client=http), read_timeout_seconds=CALL_TIMEOUT
            ) as client:
                yield client

    async def _run(self) -> None:
        try:
            async with self._client() as client:
                cursor = None
                while True:
                    page = await client.list_tools(cursor=cursor)
                    self.tools.extend(page.tools)
                    cursor = getattr(page, "next_cursor", None)
                    if not cursor:
                        break
                self._ready.set()
                while True:
                    item = await self._queue.get()
                    if item is None:
                        break
                    fut, tool, args = item
                    try:
                        res = await client.call_tool(tool, args)
                        if not fut.done():
                            fut.set_result(res)
                    except Exception as e:  # noqa: BLE001
                        if not fut.done():
                            fut.set_exception(e)
        except NeedsAuth:
            self.needs_auth = True
            self.error = "Sign-in required"
        except BaseException as e:  # noqa: BLE001 - surface any failure to the user
            if isinstance(e, asyncio.CancelledError):
                self.error = self.error or "Connection cancelled"
            else:
                self.error = _describe(e)
                if self.cfg.transport == "http" and "401" in self.error:
                    self.needs_auth = True
                    self.error = "Sign-in required"
        finally:
            self._ready.set()
            while not self._queue.empty():
                item = self._queue.get_nowait()
                if item and not item[0].done():
                    item[0].set_exception(RuntimeError(self.error or "Connection closed"))

    async def start(self, timeout: float = CONNECT_TIMEOUT) -> None:
        self._task = asyncio.create_task(self._run())
        try:
            await asyncio.wait_for(self._ready.wait(), timeout)
        except TimeoutError:
            self.error = f"Timed out after {int(timeout)}s while connecting"
            self._task.cancel()

    @property
    def ok(self) -> bool:
        return self._ready.is_set() and self.error is None

    async def call(self, tool: str, args: dict) -> tuple[str, bool]:
        if not self.ok:
            return f"Server {self.cfg.name} is not connected: {self.error}", True
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((fut, tool, args))
        try:
            res = await asyncio.wait_for(fut, CALL_TIMEOUT)
        except TimeoutError:
            return f"Tool {tool} timed out", True
        except Exception as e:  # noqa: BLE001
            return f"Tool {tool} failed: {_describe(e)}", True
        return _result_text(res), bool(res.is_error)

    async def close(self) -> None:
        if self._task and not self._task.done():
            await self._queue.put(None)
            try:
                await asyncio.wait_for(asyncio.shield(self._task), 10)
            except (TimeoutError, Exception):  # noqa: BLE001
                self._task.cancel()


def _describe(e: BaseException) -> str:
    # Unwrap exception groups from anyio task groups.
    while isinstance(e, BaseExceptionGroup) and e.exceptions:
        e = e.exceptions[0]
    msg = str(e) or e.__class__.__name__
    return msg[:500]


class McpHub:
    """All enabled MCP servers for one user, connected for the duration of an agent run."""

    def __init__(self, user_id: int, config_text: str, sandbox: Sandbox):
        self.user_id = user_id
        self.sandbox = sandbox
        try:
            self.configs = parse_config(config_text)
            self.config_error = None
        except ConfigError as e:
            self.configs = {}
            self.config_error = str(e)
        self.connections: dict[str, _Connection] = {}
        self._routes: dict[str, tuple[_Connection, str]] = {}

    async def __aenter__(self) -> McpHub:
        conns = [_Connection(c, self.user_id, self.sandbox) for c in self.configs.values() if c.enabled]
        await asyncio.gather(*(c.start() for c in conns))
        for c in conns:
            self.connections[c.cfg.name] = c
            for t in c.tools if c.ok else []:
                self._routes[tool_name(c.cfg.name, t.name)] = (c, t.name)
        return self

    async def __aexit__(self, *exc) -> None:
        await asyncio.gather(*(c.close() for c in self.connections.values()), return_exceptions=True)

    def tools(self) -> list[Tool]:
        out = []
        for name, (conn, tool) in self._routes.items():
            t = next(x for x in conn.tools if x.name == tool)
            schema = t.input_schema or {"type": "object", "properties": {}}
            desc = t.description or t.title or tool
            hints = t.annotations
            read_only = bool(hints and getattr(hints, "read_only_hint", False))

            async def run(args: dict, _ctx: ToolContext, _name: str = name) -> ToolResult:
                text, is_error = await self.call(_name, args)
                return ToolResult(text, is_error)

            out.append(
                Tool(
                    name=name,
                    description=f"[{conn.cfg.name}] {desc}"[:1024],
                    parameters=schema,
                    run=run,
                    read_only=read_only,
                    label=lambda _a, _c=conn.cfg.name, _t=tool: f"{_c} · {_t}",
                )
            )
        return out

    async def call(self, name: str, args: dict) -> tuple[str, bool]:
        conn, tool = self._routes[name]
        return await conn.call(tool, args)

    def status(self) -> list[dict]:
        out = []
        for name, cfg in self.configs.items():
            conn = self.connections.get(name)
            if not cfg.enabled:
                state = "disabled"
            elif conn is None:
                state = "unknown"
            elif conn.needs_auth:
                state = "needs_auth"
            elif conn.ok:
                state = "connected"
            else:
                state = "error"
            out.append(
                {
                    "name": name,
                    "transport": cfg.transport,
                    "target": cfg.url if cfg.transport == "http" else " ".join([cfg.command, *cfg.args]),
                    "state": state,
                    "error": conn.error if conn and state == "error" else None,
                    "tools": [
                        {"name": t.name, "description": t.description or ""} for t in (conn.tools if conn else [])
                    ],
                    "signed_in": cfg.transport == "http" and oauth.has_tokens(self.user_id, name),
                }
            )
        return out
