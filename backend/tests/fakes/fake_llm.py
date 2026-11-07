"""A scripted, deterministic model server speaking both the Anthropic Messages API and the
OpenAI Chat Completions API. Used by backend tests and the end-to-end UI tests.

Rules (applied to the latest user text):
  run: <cmd>                  -> calls bash
  remember: <fact>            -> appends a bullet to memory.md via bash
  write: <path> | <content>   -> calls write
  edit: <path> | <old> | <new>-> calls edit
  read: <path> [<path> …]     -> calls read (several paths = parallel calls)
  show messages               -> lists every user message it received (steering/compaction checks)
  summarise the conversation… -> compaction summary
  tool: <name> <json args>    -> calls any tool by name
  show system                 -> replies with the system prompt
  list tools                  -> replies with the tool names it was given
  anything else               -> "Echo: <text>"
After a tool result it replies "Result: <tool output>".

Run standalone: python -m tests.fakes.fake_llm --port 9100
"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

from fastapi import FastAPI, Request

app = FastAPI()
REQUESTS: list[dict[str, Any]] = []


def decide(
    last_user: str | None,
    tool_result: str | None,
    system: str,
    tool_names: list[str],
    history_users: list[str] | None = None,
) -> dict:
    """Return {"text": str} and optionally {"calls": [(name, args), ...]}."""
    if last_user is None and tool_result is not None:
        return {"text": f"Result: {tool_result[:2000]}"}
    text = (last_user or "").strip()
    low = text.lower()
    if low.startswith("summarise the conversation"):
        return {"text": f"SUMMARY of {len(history_users or [])} user messages: " + " | ".join(history_users or [])}
    if low.startswith("run:"):
        return {"calls": [("bash", {"command": text[4:].strip()})], "text": "Running that now."}
    if low.startswith("remember:"):
        fact = text[9:].strip().replace("'", "")
        return {"calls": [("bash", {"command": f"printf -- '- %s\\n' '{fact}' >> memory.md"})], "text": ""}
    if low.startswith("write:"):
        path, _, content = text[6:].partition("|")
        return {"calls": [("write", {"path": path.strip(), "content": content.strip()})], "text": ""}
    if low.startswith("edit:"):
        path, old, new = (x.strip() for x in text[5:].split("|"))
        return {"calls": [("edit", {"path": path, "old_string": old, "new_string": new})], "text": ""}
    if low.startswith("read:"):
        paths = text[5:].split()
        return {"calls": [("read", {"path": p}) for p in paths], "text": ""}
    if low.startswith("tool:"):
        rest = text[5:].strip()
        name, _, args = rest.partition(" ")
        return {"calls": [(name, json.loads(args or "{}"))], "text": ""}
    if low == "show system":
        return {"text": system}
    if low == "list tools":
        return {"text": "Tools: " + ", ".join(tool_names)}
    if low == "show messages":
        return {"text": "Messages: " + " | ".join(history_users or [])}
    return {"text": f"Echo: {text}"}


def _texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    return [b.get("text", "") for b in content if b.get("type") == "text"]


# ------------------------------------------------------------- Anthropic


@app.post("/v1/messages")
async def messages(request: Request):
    body = await request.json()
    REQUESTS.append({"api": "anthropic", "headers": dict(request.headers), "body": body})
    msgs = body["messages"]
    last = msgs[-1]
    blocks = last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
    results = [b for b in blocks if b.get("type") == "tool_result"]
    texts = [b.get("text", "") for b in blocks if b.get("type") == "text" and b.get("text", "").strip()]
    tool_result = None
    if results:
        c = results[-1]["content"]
        tool_result = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c)
    last_user = texts[-1] if texts else None
    users = [t for m in msgs if m["role"] == "user" for t in _texts(m["content"]) if t.strip()]
    system = body.get("system") or ""
    if isinstance(system, list):
        system = " ".join(b.get("text", "") for b in system)
    d = decide(last_user, tool_result, system, [t["name"] for t in body.get("tools", [])], users)
    content: list[dict] = [{"type": "thinking", "thinking": "", "signature": "sig-" + uuid.uuid4().hex[:8]}]
    if d.get("text"):
        content.append({"type": "text", "text": d["text"]})
    for name, args in d.get("calls", []):
        content.append({"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:12], "name": name, "input": args})
    return {
        "id": "msg_" + uuid.uuid4().hex[:12],
        "type": "message",
        "role": "assistant",
        "model": body["model"],
        "content": content,
        "stop_reason": "tool_use" if d.get("calls") else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


# ------------------------------------------------------------- OpenAI


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    REQUESTS.append({"api": "openai", "headers": dict(request.headers), "body": body})
    msgs = body["messages"]
    last = msgs[-1]
    system = next((m["content"] for m in msgs if m["role"] == "system"), "")
    if isinstance(system, list):
        system = " ".join(_texts(system))
    tool_result = last["content"] if last["role"] == "tool" else None
    last_user = " ".join(_texts(last["content"])) if last["role"] == "user" else None
    users = [" ".join(_texts(m["content"])) for m in msgs if m["role"] == "user"]
    d = decide(last_user, tool_result, system, [t["function"]["name"] for t in body.get("tools", [])], users)
    message: dict[str, Any] = {"role": "assistant", "content": d.get("text") or None}
    if d.get("calls"):
        message["tool_calls"] = [
            {
                "id": "call_" + uuid.uuid4().hex[:12],
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
            for name, args in d["calls"]
        ]
    finish = "tool_calls" if d.get("calls") else "stop"
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
    }


@app.get("/_requests")
def requests_log():
    return REQUESTS


@app.delete("/_requests")
def clear_requests():
    REQUESTS.clear()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9100)
    args = p.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
