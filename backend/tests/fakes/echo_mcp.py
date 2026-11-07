"""A dependency-free MCP stdio server (raw JSON-RPC), so it runs in any sandbox image with Python.

Tools: echo(text) (read-only), add(a, b), whereami() -> hostname and working directory.
"""

import json
import os
import socket
import sys

TOOLS = [
    {
        "name": "echo",
        "description": "Echo the given text back",
        "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "add",
        "description": "Add two numbers",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {
        "name": "whereami",
        "description": "Report host and directory",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def call(name, args):
    if name == "echo":
        return f"echo: {args.get('text', '')}"
    if name == "add":
        return str(args["a"] + args["b"])
    if name == "whereami":
        return f"host={socket.gethostname()} cwd={os.getcwd()}"
    raise KeyError(name)


def reply(msg_id, result=None, error=None):
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error:
        out["error"] = error
    else:
        out["result"] = result
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:
        continue  # notification
    if method == "initialize":
        reply(
            msg_id,
            {
                "protocolVersion": msg["params"].get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "echo", "version": "1.0"},
            },
        )
    elif method == "tools/list":
        reply(msg_id, {"tools": TOOLS})
    elif method == "tools/call":
        p = msg["params"]
        try:
            reply(msg_id, {"content": [{"type": "text", "text": call(p["name"], p.get("arguments") or {})}]})
        except Exception as e:  # noqa: BLE001
            reply(msg_id, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
    elif method == "ping":
        reply(msg_id, {})
    else:
        reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})
