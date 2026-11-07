"""The four built-in tools, in the spirit of pi: read, write, edit, bash.

Everything else (listing, searching, running scripts, installing packages) goes through bash in the
user's sandbox. Memory and context files are plain files edited with these same tools.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from acf import config, workspace
from acf.sandbox import SandboxError, get_sandbox

MAX_READ_LINES = 2000
MAX_OUTPUT_CHARS = 30_000
SPILL_DIR = ".acf/outputs"


BACKGROUND_TIMEOUT = 3600  # seconds; default and limit for background commands


@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    background: str | None = None  # the job id, when the call started a background job


# start_job(label, work) -> job id: runs `work()` after the call returns and reports its result later.
StartJob = Callable[[str, Callable[[], Awaitable[ToolResult]]], str]


@dataclass
class ToolContext:
    user_id: int
    start_job: StartJob | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    # Calls that only read can run concurrently when the model makes several at once.
    read_only: Callable[[dict[str, Any]], bool] = field(default=lambda a: False)
    # What a call touches (a file path). Calls in one batch run at the same time, except that a call
    # waits for earlier calls on the same resource when either of them writes.
    resource: Callable[[dict[str, Any]], str | None] = field(default=lambda a: None)
    label: Callable[[dict[str, Any]], str] = field(default=lambda a: "")

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def truncate(text: str, ctx: ToolContext, keep_tail: bool = True) -> str:
    """Keep the model's context small: show the head and tail, spill the full text to a file."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    rel = f"{SPILL_DIR}/{secrets.token_hex(4)}.txt"
    workspace.write_file(ctx.user_id, rel, text[: workspace.MAX_FILE_BYTES])
    head = 4_000 if keep_tail else MAX_OUTPUT_CHARS - 2_000
    tail = MAX_OUTPUT_CHARS - head
    omitted = len(text) - head - tail
    return (
        f"{text[:head]}\n\n… [{omitted} characters omitted — full output saved to {rel}; "
        f"read it with offset/limit or grep it] …\n\n{text[-tail:]}"
    )


async def _read(args: dict, ctx: ToolContext) -> ToolResult:
    path = workspace.resolve(ctx.user_id, str(args["path"]))
    if path.is_dir():
        return ToolResult(f"{args['path']} is a folder. Use bash `ls` to list it.", True)
    if not path.is_file():
        return ToolResult(f"No such file: {args['path']}", True)
    raw = path.read_bytes()
    if b"\0" in raw[:4096]:
        return ToolResult(f"{args['path']} is a binary file ({len(raw)} bytes). Use bash to inspect it.", True)
    lines = raw.decode(errors="replace").splitlines()
    offset = max(int(args.get("offset") or 1), 1)
    limit = min(int(args.get("limit") or MAX_READ_LINES), MAX_READ_LINES)
    chunk = lines[offset - 1 : offset - 1 + limit]
    body = "\n".join(f"{i:>6}\t{line[:2000]}" for i, line in enumerate(chunk, start=offset))
    rest = len(lines) - (offset - 1 + len(chunk))
    if rest > 0:
        body += f"\n… {rest} more lines. Continue with offset={offset + len(chunk)}."
    if not lines:
        body = "(empty file)"
    return ToolResult(truncate(body, ctx, keep_tail=False))


async def _write(args: dict, ctx: ToolContext) -> ToolResult:
    content = str(args.get("content", ""))
    workspace.write_file(ctx.user_id, str(args["path"]), content)
    return ToolResult(f"Wrote {args['path']} ({len(content.splitlines())} lines)")


async def _edit(args: dict, ctx: ToolContext) -> ToolResult:
    rel = str(args["path"])
    path = workspace.resolve(ctx.user_id, rel)
    if not path.is_file():
        return ToolResult(f"No such file: {rel}. Use write to create it.", True)
    text = path.read_text(errors="replace")
    old, new = str(args["old_string"]), str(args.get("new_string", ""))
    if not old:
        return ToolResult("old_string must not be empty", True)
    count = text.count(old)
    if count == 0:
        return ToolResult(f"old_string was not found in {rel}. Read the file and copy the text exactly.", True)
    if count > 1 and not args.get("replace_all"):
        return ToolResult(
            f"old_string appears {count} times in {rel}. Add surrounding lines to make it unique, or set replace_all.",
            True,
        )
    workspace.write_file(
        ctx.user_id, rel, text.replace(old, new) if args.get("replace_all") else text.replace(old, new, 1)
    )
    return ToolResult(f"Edited {rel} ({count if args.get('replace_all') else 1} replacement)")


async def _bash(args: dict, ctx: ToolContext) -> ToolResult:
    command = str(args["command"])
    if args.get("background") and ctx.start_job:
        timeout = min(int(args.get("timeout") or BACKGROUND_TIMEOUT), BACKGROUND_TIMEOUT)

        async def work() -> ToolResult:
            return await _exec(command, timeout, ctx)

        job = ctx.start_job(command, work)
        return ToolResult(
            f"Started in the background as job {job}. Its output arrives as a message when it finishes; "
            "carry on meanwhile, or end your turn if there is nothing else to do.",
            background=job,
        )
    return await _exec(command, min(int(args.get("timeout") or config.settings.command_timeout), 900), ctx)


async def _exec(command: str, timeout: int, ctx: ToolContext) -> ToolResult:
    try:
        res = await get_sandbox(ctx.user_id).exec(command, timeout)
    except SandboxError as e:
        return ToolResult(str(e), True)
    return ToolResult(truncate(res.as_text(), ctx), res.exit_code != 0)


def _path(a: dict[str, Any]) -> str | None:
    return str(a["path"]).strip("/") if a.get("path") else None


BUILTIN_TOOLS: list[Tool] = [
    Tool(
        "read",
        "Read a text file from the workspace. Returns numbered lines. Use offset/limit for long files.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to /workspace"},
                "offset": {"type": "integer", "description": "1-based line to start at"},
                "limit": {"type": "integer", "description": f"Max lines (default {MAX_READ_LINES})"},
            },
            "required": ["path"],
        },
        _read,
        read_only=lambda a: True,
        resource=_path,
        label=lambda a: str(a.get("path", "")),
    ),
    Tool(
        "write",
        "Create or overwrite a file in the workspace. Prefer edit for changing existing files.",
        {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        _write,
        resource=_path,
        label=lambda a: str(a.get("path", "")),
    ),
    Tool(
        "edit",
        "Replace an exact piece of text in a file. old_string must match exactly (including whitespace) "
        "and be unique unless replace_all is true. Read the file first.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "replace_all": {"type": "boolean"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        _edit,
        resource=_path,
        label=lambda a: str(a.get("path", "")),
    ),
    Tool(
        "bash",
        "Run a shell command in the user's private Linux sandbox (cwd /workspace; Python, Node, uv available). "
        "Use it to list and search files (ls, find, grep), run scripts, and install packages. "
        "Set background to true for long jobs (builds, downloads, data processing): the call returns at once "
        "and the output arrives as a message when the command finishes.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {
                    "type": "integer",
                    "description": f"Seconds, default 120, max 900 (background: default and max {BACKGROUND_TIMEOUT})",
                },
                "background": {"type": "boolean", "description": "Run without waiting; get the output later"},
            },
            "required": ["command"],
        },
        _bash,
        label=lambda a: str(a.get("command", ""))[:160],
    ),
]
