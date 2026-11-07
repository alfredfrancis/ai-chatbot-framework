"""A scripted, deterministic model server speaking both the Anthropic Messages API and the
OpenAI Chat Completions API. Used by backend tests and the end-to-end UI tests.

Rules (applied to the latest user text):
  run: <cmd>                  -> calls run_command
  remember: <fact>            -> calls remember
  write: <path> | <content>   -> calls write_file
  read: <path>                -> calls read_file
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


def decide(last_user: str | None, tool_result: str | None, system: str, tool_names: list[str]) -> dict:
    """Return {"text": str} or {"tool": name, "args": {...}, "text": str}."""
    if tool_result is not None:
        return {"text": f"Result: {tool_result[:2000]}"}
    text = (last_user or "").strip()
    low = text.lower()
    if low.startswith("run:"):
        return {"tool": "run_command", "args": {"command": text[4:].strip()}, "text": "Running that now."}
    if low.startswith("remember:"):
        return {"tool": "remember", "args": {"fact": text[9:].strip()}, "text": ""}
    if low.startswith("write:"):
        path, _, content = text[6:].partition("|")
        return {"tool": "write_file", "args": {"path": path.strip(), "content": content.strip()}, "text": ""}
    if low.startswith("read:"):
        return {"tool": "read_file", "args": {"path": text[5:].strip()}, "text": ""}
    if low.startswith("tool:"):
        rest = text[5:].strip()
        name, _, args = rest.partition(" ")
        return {"tool": name, "args": json.loads(args or "{}"), "text": ""}
    if low == "show system":
        return {"text": system}
    if low == "list tools":
        return {"text": "Tools: " + ", ".join(tool_names)}
    return {"text": f"Echo: {text}"}


# ------------------------------------------------------------- Anthropic


@app.post("/v1/messages")
async def messages(request: Request):
    body = await request.json()
    REQUESTS.append({"api": "anthropic", "headers": dict(request.headers), "body": body})
    msgs = body["messages"]
    last = msgs[-1]
    tool_result = last_user = None
    blocks = (
        last["content"] if isinstance(last["content"], list) else [{"type": "text", "text": last["content"]}]
    )
    results = [b for b in blocks if b.get("type") == "tool_result"]
    if results:
        c = results[-1]["content"]
        tool_result = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c)
    else:
        last_user = " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    system = body.get("system") or ""
    if isinstance(system, list):
        system = " ".join(b.get("text", "") for b in system)
    d = decide(last_user, tool_result, system, [t["name"] for t in body.get("tools", [])])
    content: list[dict] = [{"type": "thinking", "thinking": "", "signature": "sig-" + uuid.uuid4().hex[:8]}]
    if d.get("text"):
        content.append({"type": "text", "text": d["text"]})
    stop = "end_turn"
    if d.get("tool"):
        content.append(
            {
                "type": "tool_use",
                "id": "toolu_" + uuid.uuid4().hex[:12],
                "name": d["tool"],
                "input": d["args"],
            }
        )
        stop = "tool_use"
    return {
        "id": "msg_" + uuid.uuid4().hex[:12],
        "type": "message",
        "role": "assistant",
        "model": body["model"],
        "content": content,
        "stop_reason": stop,
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
    tool_result = last["content"] if last["role"] == "tool" else None
    last_user = last["content"] if last["role"] == "user" else None
    d = decide(last_user, tool_result, system, [t["function"]["name"] for t in body.get("tools", [])])
    message: dict[str, Any] = {"role": "assistant", "content": d.get("text") or None}
    finish = "stop"
    if d.get("tool"):
        message["tool_calls"] = [
            {
                "id": "call_" + uuid.uuid4().hex[:12],
                "type": "function",
                "function": {"name": d["tool"], "arguments": json.dumps(d["args"])},
            }
        ]
        finish = "tool_calls"
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
    p.add_argument("--port", type=int, default=9100)
    uvicorn.run(app, host="127.0.0.1", port=p.parse_args().port, log_level="warning")
