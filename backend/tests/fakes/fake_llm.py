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
  tool: <name> <json args>    -> calls any tool by name (one per line = several calls at once)
  slow: <seconds> <text>      -> waits, then "Echo: <text>" (a model that is still thinking)
  typing: <text>              -> "Echo: <text>", streamed one word every 0.3 s
  think: <text>               -> thinks "Considering: <text>", then "Echo: <text>"
  [background job …          -> "Background done: <the note>" (a background command finished)
  show system                 -> replies with the system prompt
  list tools                  -> replies with the tool names it was given
  anything else               -> "Echo: <text>"
After a tool result it replies "Result: <tool output>".
Both APIs stream (SSE) when the request asks for it; text is sent word by word.

Run standalone: python -m tests.fakes.fake_llm --port 9100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

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
        calls = []
        for line in text.splitlines():
            name, _, args = line.strip()[5:].strip().partition(" ")
            calls.append((name, json.loads(args or "{}")))
        return {"calls": calls, "text": ""}
    if low.startswith("typing:"):
        return {"text": f"Echo: {text[7:].strip()}", "word_delay": 0.3}
    if low.startswith("think:"):
        rest = text[6:].strip()
        return {"text": f"Echo: {rest}", "thinking": f"Considering: {rest}"}
    if low.startswith("slow:"):
        secs, _, rest = text[5:].strip().partition(" ")
        return {"text": f"Echo: {rest}", "delay": float(secs)}
    if low.startswith("[background job"):
        return {"text": f"Background done: {text[:2000]}"}
    if low == "show system":
        return {"text": system}
    if low == "list tools":
        return {"text": "Tools: " + ", ".join(tool_names)}
    if low == "show messages":
        return {"text": "Messages: " + " | ".join(history_users or [])}
    return {"text": f"Echo: {text}"}


def _pieces(text: str) -> list[str]:
    """Split text into word-sized stream deltas (whitespace kept)."""
    return re.findall(r"\s*\S+", text) or [text]


def _sse(gen: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream")


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
    await asyncio.sleep(d.get("delay", 0))
    content: list[dict] = [
        {"type": "thinking", "thinking": d.get("thinking", ""), "signature": "sig-" + uuid.uuid4().hex[:8]}
    ]
    if d.get("text"):
        content.append({"type": "text", "text": d["text"]})
    for name, args in d.get("calls", []):
        content.append({"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:12], "name": name, "input": args})
    message = {
        "id": "msg_" + uuid.uuid4().hex[:12],
        "type": "message",
        "role": "assistant",
        "model": body["model"],
        "content": content,
        "stop_reason": "tool_use" if d.get("calls") else "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }
    if not body.get("stream"):
        return message
    return _sse(_anthropic_stream(message, d.get("word_delay", 0)))


async def _anthropic_stream(message: dict, word_delay: float) -> AsyncIterator[str]:
    def ev(data: dict) -> str:
        return f"event: {data['type']}\ndata: {json.dumps(data)}\n\n"

    start = {**message, "content": [], "stop_reason": None, "usage": {"input_tokens": 10, "output_tokens": 1}}
    yield ev({"type": "message_start", "message": start})
    for i, block in enumerate(message["content"]):
        kind = block["type"]
        empty = {
            "thinking": {"type": "thinking", "thinking": "", "signature": ""},
            "text": {"type": "text", "text": ""},
        }
        first = empty.get(kind) or {**block, "input": {}}
        yield ev({"type": "content_block_start", "index": i, "content_block": first})
        if kind == "thinking":
            if block["thinking"]:
                yield ev(
                    {
                        "type": "content_block_delta",
                        "index": i,
                        "delta": {"type": "thinking_delta", "thinking": block["thinking"]},
                    }
                )
            yield ev(
                {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {"type": "signature_delta", "signature": block["signature"]},
                }
            )
        elif kind == "text":
            for piece in _pieces(block["text"]):
                await asyncio.sleep(word_delay)
                yield ev({"type": "content_block_delta", "index": i, "delta": {"type": "text_delta", "text": piece}})
        else:
            partial = json.dumps(block["input"])
            yield ev(
                {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {"type": "input_json_delta", "partial_json": partial},
                }
            )
        yield ev({"type": "content_block_stop", "index": i})
    delta = {"stop_reason": message["stop_reason"], "stop_sequence": None}
    yield ev({"type": "message_delta", "delta": delta, "usage": {"output_tokens": 10}})
    yield ev({"type": "message_stop"})


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
    await asyncio.sleep(d.get("delay", 0))
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
    if body.get("stream"):
        return _sse(_openai_stream(message, finish, d.get("word_delay", 0)))
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
    }


async def _openai_stream(message: dict, finish: str, word_delay: float) -> AsyncIterator[str]:
    def chunk(delta: dict, reason: str | None = None) -> str:
        data = {
            "id": "chatcmpl-x",
            "object": "chat.completion.chunk",
            "model": "fake",
            "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
        }
        return f"data: {json.dumps(data)}\n\n"

    yield chunk({"role": "assistant", "content": ""})
    for piece in _pieces(message["content"]) if message["content"] else []:
        await asyncio.sleep(word_delay)
        yield chunk({"content": piece})
    for i, call in enumerate(message.get("tool_calls", [])):
        yield chunk({"tool_calls": [{"index": i, **call}]})
    yield chunk({}, finish)
    yield "data: [DONE]\n\n"


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
