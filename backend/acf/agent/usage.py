"""Context usage: how full the model's context window is and what fills it.

Measured after every model call and sent to the chat as an ACP `usage_update`. `used` is the provider's
own count (input + output tokens of the latest call) when it reports one, else an estimate. The parts are
always estimates (~4 characters per token), so they show proportions, not exact counts.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from acf import config
from acf.llm import estimate_tokens

DEFAULT_WINDOW = 128_000


def window(model: Any, own: int = 0) -> int:
    """The context window: the model's token window from the models list or the user's settings (`own`), else
    ACF_CONTEXT_WINDOW, else the model's profile, else a common default."""
    if own > 0:
        return own
    if config.settings.context_window > 0:
        return config.settings.context_window
    profile = getattr(model, "profile", None) or {}
    size = profile.get("max_input_tokens") if isinstance(profile, dict) else None
    return int(size) if isinstance(size, int) and size > 0 else DEFAULT_WINDOW


def _message_tokens(m: BaseMessage) -> int:
    calls = getattr(m, "tool_calls", None)
    return estimate_tokens(m.content) + (estimate_tokens(calls) if calls else 0)


def measure(
    sections: list[tuple[str, str]],
    tools: list[dict[str, Any]],
    skill_names: list[str],
    apps: dict[str, list[str]],
    history: list[BaseMessage],
    ai: AIMessage | None,
    size: int,
) -> dict[str, Any]:
    """The context after the latest model call: system prompt, tools, skills and messages."""

    def part(*keys: str) -> int:
        return sum(estimate_tokens(text) for k, text in sections if k in keys)

    tool_names = [t["function"]["name"] for t in tools]
    app_tools = [f"{server}: {', '.join(names)}" for server, names in apps.items()]  # used through mcp_call
    parts = [
        {"name": "System prompt", "tokens": part("instructions", "context", "project", "memory")},
        {"name": "Tools", "tokens": estimate_tokens(tools) + part("apps"), "items": tool_names + app_tools},
        {"name": "Skills", "tokens": part("skills"), "items": skill_names},
        {"name": "Messages", "tokens": sum(_message_tokens(m) for m in history), "count": len(history)},
    ]
    meta = (ai.usage_metadata if ai is not None else None) or {}
    reported = int(meta.get("input_tokens") or 0)
    used = reported + int(meta.get("output_tokens") or 0) if reported else sum(p["tokens"] for p in parts)
    return {
        "used": used,
        "size": size,
        "percent": round(100 * used / size, 1) if size else 0,
        "measured": bool(reported),
        "parts": parts,
    }


def update(usage: dict[str, Any]) -> dict[str, Any]:
    """An ACP `usage_update` session update; the breakdown rides in `_meta.acf`."""
    breakdown = {k: usage[k] for k in ("percent", "measured", "parts")}
    return {"sessionUpdate": "usage_update", "used": usage["used"], "size": usage["size"], "_meta": {"acf": breakdown}}
