"""MCP servers from a Claude-Desktop-style JSON config.

{
  "mcpServers": {
    "files":  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]},
    "linear": {"url": "https://mcp.linear.app/mcp"},
    "custom": {"url": "https://example.com/mcp", "headers": {"X-Api-Key": "…"}, "oauth": {"client_id": "…"}}
  }
}

Local (stdio) servers are started INSIDE the user's sandbox with `Sandbox.process()`, whatever the
sandbox provider; `_process_transport` speaks MCP over that byte stream. Remote servers use Streamable
HTTP and OAuth when the server asks for it (HTTP 401).

Each connection lives in its own asyncio task so that the SDK's task groups and cancel scopes are
always entered and exited in the same task.

The model never gets one schema per MCP tool. Each tool's definition is a file in the workspace
(.acf/mcp/<server>/<tool>.json), the system prompt lists only the names, and one `mcp_call` tool runs
them.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import anyio
import httpx2
import mcp_types
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.message import SessionMessage

from acf import oauth, workspace
from acf.agent.tools import Tool, ToolContext, ToolResult
from acf.sandbox import Sandbox, SandboxProcess

CONNECT_TIMEOUT = 60
CALL_TIMEOUT = 300
DEFINITIONS_DIR = ".acf/mcp"
CALL_TOOL = "mcp_call"
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_UNSAFE_FILE_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


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


def _definition_path(server: str, tool: str) -> str:
    return f"{DEFINITIONS_DIR}/{server}/{_UNSAFE_FILE_CHARS.sub('_', tool)}.json"


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


@asynccontextmanager
async def _process_transport(proc: SandboxProcess):
    """MCP's stdio transport (newline-delimited JSON-RPC) over a process in the sandbox. The process
    itself is stopped by `Sandbox.process()`, which owns it."""
    read_in, read_out = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    write_in, write_out = anyio.create_memory_object_stream[SessionMessage](0)

    async def reader() -> None:
        buffer = b""
        async with read_in:
            while chunk := await proc.read():
                *lines, buffer = (buffer + chunk).split(b"\n")
                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        msg: SessionMessage | Exception = SessionMessage(
                            mcp_types.jsonrpc_message_adapter.validate_json(line, by_name=False)
                        )
                    except ValueError as e:
                        msg = e  # the session reports it
                    try:
                        await read_in.send(msg)
                    except (anyio.ClosedResourceError, anyio.BrokenResourceError):
                        return

    async def writer() -> None:
        try:
            async with write_out:
                async for msg in write_out:
                    data = msg.message.model_dump_json(by_alias=True, exclude_unset=True) + "\n"
                    await proc.write(data.encode())
        except BrokenPipeError:
            await read_in.aclose()  # the server is gone: end the session instead of waiting forever

    async with anyio.create_task_group() as tg:
        tg.start_soon(reader)
        tg.start_soon(writer)
        try:
            yield read_out, write_in
        finally:
            tg.cancel_scope.cancel()


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
            async with self.sandbox.process([cfg.command, *cfg.args], cfg.env) as proc:
                async with Client(_process_transport(proc), read_timeout_seconds=CALL_TIMEOUT) as client:
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
        self._tools: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> McpHub:
        conns = [_Connection(c, self.user_id, self.sandbox) for c in self.configs.values() if c.enabled]
        await asyncio.gather(*(c.start() for c in conns))
        for c in conns:
            self.connections[c.cfg.name] = c
            if c.ok and c.tools:
                self._tools[c.cfg.name] = {t.name: t for t in sorted(c.tools, key=lambda t: t.name)}
                self._write_definitions(c.cfg.name)
        return self

    async def __aexit__(self, *exc) -> None:
        await asyncio.gather(*(c.close() for c in self.connections.values()), return_exceptions=True)

    def _write_definitions(self, server: str) -> None:
        # Rewrite only what changed: another chat of the same user may be reading these files right now.
        folder = f"{DEFINITIONS_DIR}/{server}"
        wanted = {
            _definition_path(server, name): json.dumps(
                {
                    "description": t.description or t.title or name,
                    "input_schema": t.input_schema or {"type": "object", "properties": {}},
                },
                indent=2,
            )
            for name, t in self._tools[server].items()
        }
        for old in workspace.resolve(self.user_id, folder).glob("*.json"):
            if f"{folder}/{old.name}" not in wanted:
                old.unlink()
        for rel, text in wanted.items():
            if workspace.read_file(self.user_id, rel) != text:
                workspace.write_file(self.user_id, rel, text)

    def catalog(self) -> dict[str, list[str]]:
        return {server: list(tools) for server, tools in self._tools.items()}

    def tool(self) -> Tool | None:
        if not self._tools:
            return None
        return Tool(
            CALL_TOOL,
            "Call a tool of a connected app. Read its definition file first for the arguments.",
            {
                "type": "object",
                "properties": {
                    "server": {"type": "string"},
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["server", "tool"],
            },
            self._call,
            read_only=self._read_only,
            # Tools of one app may share state: a tool that writes waits for earlier calls to the same app.
            resource=lambda a: f"mcp:{a.get('server', '')}",
            label=lambda a: f"{a.get('server', '')} · {a.get('tool', '')}",
        )

    def _lookup(self, args: dict) -> Any:
        return self._tools.get(str(args.get("server", "")), {}).get(str(args.get("tool", "")))

    def _read_only(self, args: dict) -> bool:
        t = self._lookup(args)
        return bool(t and t.annotations and getattr(t.annotations, "read_only_hint", False))

    async def _call(self, args: dict, _ctx: ToolContext) -> ToolResult:
        server, name = str(args.get("server", "")), str(args.get("tool", ""))
        if server not in self._tools:
            return ToolResult(f"No connected app named {server!r}. Connected: {', '.join(self._tools)}", True)
        if self._lookup(args) is None:
            return ToolResult(f"{server} has no tool {name!r}. Its tools: {', '.join(self._tools[server])}", True)
        arguments = args.get("arguments") or {}
        if not isinstance(arguments, dict):
            return ToolResult("arguments must be a JSON object", True)
        text, is_error = await self.connections[server].call(name, arguments)
        return ToolResult(text, is_error)

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
