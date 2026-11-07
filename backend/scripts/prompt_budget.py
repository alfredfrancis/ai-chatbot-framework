"""Measure what one agent step sends to the model and how long the server takes to read it.

    python -m scripts.prompt_budget --user 1 --chat 6 [--runs 3] [--llama http://host.docker.internal:8090]

Rebuilds the exact request `Run._turn` sends (system prompt, bound tools, history), counts the tokens
of each part with llama-server's /tokenize, then sends the request with max_tokens=1 and the prompt
cache off to time a cold prefill.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time

import httpx
from langchain_core.messages import SystemMessage

from acf.agent import prompt
from acf.agent.loop import load_history
from acf.agent.tools import BUILTIN_TOOLS
from acf.db import User, init_db, session_scope
from acf.llm import LLMConfig, make_model
from acf.mcp_client import McpHub
from acf.sandbox import get_sandbox


def count(client: httpx.Client, llama: str, text: str) -> int:
    return len(client.post(f"{llama}/tokenize", json={"content": text}).json()["tokens"])


async def build_request(user_id: int, chat_id: int) -> tuple[dict, float]:
    with session_scope() as db:
        user = db.get(User, user_id)
        db.expunge(user)

    t0 = time.perf_counter()
    async with McpHub(user.id, user.mcp_config, get_sandbox(user.id)) as hub:
        mcp_connect_s = time.perf_counter() - t0
        tools = [t for t in [*BUILTIN_TOOLS, hub.tool()] if t]
        apps = hub.catalog()
    schemas = [t.schema() for t in tools]
    system = prompt.build(user.id, apps)
    history = load_history(chat_id)

    model = make_model(LLMConfig.for_user(user)).bind_tools(schemas)
    return model.bound._get_request_payload([SystemMessage(system), *history], **model.kwargs), mcp_connect_s


def main(user_id: int, chat_id: int, runs: int, llama: str, no_mcp: bool) -> None:
    init_db()
    payload, mcp_connect_s = asyncio.run(build_request(user_id, chat_id))
    with httpx.Client(timeout=900) as client:

        def rendered(messages: list[dict], tools: list[dict]) -> int:
            body = {"messages": messages, **({"tools": tools} if tools else {})}
            return count(client, llama, client.post(f"{llama}/apply-template", json=body).json()["prompt"])

        msgs, all_tools = payload["messages"], payload.get("tools", [])
        builtin_names = {t.name for t in BUILTIN_TOOLS}
        builtin = [t for t in all_tools if t["function"]["name"] in builtin_names]
        total = rendered(msgs, all_tools)
        no_tools = rendered(msgs, [])
        system_only = rendered(msgs[:1], [])
        parts = {
            "system prompt": system_only,
            f"builtin tools ({len(builtin)})": rendered(msgs, builtin) - no_tools,
            f"mcp tools ({len(all_tools) - len(builtin)})": total - rendered(msgs, builtin),
        }
        for role in ("user", "assistant", "tool"):
            parts[f"history: {role}"] = no_tools - rendered([m for m in msgs if m["role"] != role], [])
        biggest_tools = sorted(
            ((count(client, llama, json.dumps(s)), s["function"]["name"]) for s in all_tools), reverse=True
        )[:5]

        body = {**payload, "max_tokens": 1, "stream": False, "cache_prompt": False}
        if no_mcp:
            body["tools"] = builtin
        body.pop("stream_options", None)
        samples = []
        for _ in range(runs):
            r = client.post(f"{llama}/v1/chat/completions", json=body).json()
            samples.append((r["usage"]["prompt_tokens"], r["timings"]["prompt_ms"] / 1000))

    report = {
        "mcp_connect_s": round(mcp_connect_s, 2),
        "rendered_prompt_tokens": total,
        "parts_tokens": parts,
        "parts_share": {k: f"{v / total:.0%}" for k, v in parts.items()},
        "largest_tool_schemas": biggest_tools,
    }
    if samples:
        times = [s for _, s in samples]
        report["prompt_tokens"] = samples[0][0]
        report["cold_prefill_s"] = {
            "median": round(statistics.median(times), 1),
            "min": round(min(times), 1),
            "max": round(max(times), 1),
            "runs": runs,
        }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user", type=int, required=True)
    p.add_argument("--chat", type=int, required=True)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--llama", default="http://host.docker.internal:8090")
    p.add_argument("--no-mcp", action="store_true", help="time the request without MCP tool schemas")
    a = p.parse_args()
    main(a.user, a.chat, a.runs, a.llama, a.no_mcp)
