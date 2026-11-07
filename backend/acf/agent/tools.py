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


@dataclass
class ToolResult:
    content: str
    is_error: bool = False


@dataclass
class ToolContext:
    user_id: int


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[dict[str, Any], ToolContext], Awaitable[ToolResult]]
    # Tools that only read can run concurrently when the model calls several at once.
    read_only: bool = False
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
    timeout = min(int(args.get("timeout") or config.settings.command_timeout), 900)
    try:
        res = await get_sandbox(ctx.user_id).exec(str(args["command"]), timeout)
    except SandboxError as e:
        return ToolResult(str(e), True)
    return ToolResult(truncate(res.as_text(), ctx), res.exit_code != 0)


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
        read_only=True,
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
        label=lambda a: str(a.get("path", "")),
    ),
    Tool(
        "bash",
        "Run a shell command in the user's private Linux sandbox (cwd /workspace; Python, Node, uv available). "
        "Use it to list and search files (ls, find, grep), run scripts, and install packages.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "description": "Seconds, default 120, max 900"},
            },
            "required": ["command"],
        },
        _bash,
        label=lambda a: str(a.get("command", ""))[:160],
    ),
]
