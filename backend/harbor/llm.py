"""Minimal LLM layer with two providers.

- anthropic: Claude via the official Anthropic SDK (default)
- openai:    any OpenAI-compatible Chat Completions endpoint (OpenAI, Ollama, OpenRouter, vLLM, LiteLLM…)

Messages are kept in a provider-neutral shape:
  {"role": "user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [{"id","name","arguments"}], "raw": {...}|None}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str, "is_error": bool}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import anthropic
import httpx

from harbor import config


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class LLMReply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    stop_reason: str = ""


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str

    @classmethod
    def for_user(cls, user: Any) -> LLMConfig:
        s = config.settings
        provider = user.llm_provider or s.llm_provider
        return cls(
            provider=provider,
            model=user.llm_model or s.default_model(provider),
            api_key=user.llm_api_key or s.llm_api_key,
            base_url=user.llm_base_url or s.llm_base_url,
        )


class LLMError(RuntimeError):
    pass


class LLM:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    async def complete(self, system: str, messages: list[dict], tools: list[ToolSpec]) -> LLMReply:
        raise NotImplementedError


# ---------------------------------------------------------------- Anthropic

# Models that accept output_config.effort and the server-side refusal fallback.
_MODERN_CLAUDE = ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-haiku-5", "claude-opus-4-8")


class AnthropicLLM(LLM):
    def __init__(self, cfg: LLMConfig):
        super().__init__(cfg)
        kwargs: dict[str, Any] = {"max_retries": 2, "timeout": 600}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        self.client = anthropic.AsyncAnthropic(**kwargs)

    @staticmethod
    def to_messages(messages: list[dict]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m["role"] == "user":
                block = {"type": "text", "text": m["content"] or " "}
                if out and out[-1]["role"] == "user":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            elif m["role"] == "assistant":
                raw = m.get("raw") or {}
                if raw.get("provider") == "anthropic" and raw.get("content"):
                    content = raw["content"]  # replay verbatim (keeps thinking blocks intact)
                else:
                    content = []
                    if m.get("content"):
                        content.append({"type": "text", "text": m["content"]})
                    for tc in m.get("tool_calls") or []:
                        content.append(
                            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]}
                        )
                if content:
                    out.append({"role": "assistant", "content": content})
            elif m["role"] == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"] or "(no output)",
                    "is_error": bool(m.get("is_error")),
                }
                # All results for one assistant turn go back in a single user message.
                if out and out[-1]["role"] == "user" and out[-1]["content"][-1]["type"] == "tool_result":
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        return out

    async def complete(self, system, messages, tools):
        params: dict[str, Any] = {
            "model": self.cfg.model,
            "max_tokens": 16000,
            "system": system,
            "messages": self.to_messages(messages),
        }
        if tools:
            params["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
            ]
        modern = self.cfg.model.startswith(_MODERN_CLAUDE)
        if modern:
            params["output_config"] = {"effort": "medium"}
        try:
            if modern and not self.cfg.base_url:
                # Server-side fallback: if a safety classifier declines, the API retries on a fallback model.
                resp = await self.client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                resp = await self.client.messages.create(**params)
        except anthropic.AuthenticationError as e:
            raise LLMError("The Anthropic API key is missing or invalid. Add one in Settings.") from e
        except anthropic.RateLimitError as e:
            raise LLMError("The model is rate limited right now. Try again in a minute.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Model error ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"Could not reach the model: {e}") from e

        blocks = [
            b.to_dict() if hasattr(b, "to_dict") else b.model_dump(exclude_none=True) for b in resp.content
        ]
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        calls = [
            ToolCall(id=b["id"], name=b["name"], arguments=b.get("input") or {})
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        if resp.stop_reason == "refusal" and not text:
            text = "Sorry, I can't help with that request."
        return LLMReply(
            text=text,
            tool_calls=calls,
            raw={"provider": "anthropic", "content": blocks},
            stop_reason=resp.stop_reason or "",
        )


# ---------------------------------------------------------------- OpenAI-compatible


class OpenAICompatLLM(LLM):
    @staticmethod
    def to_messages(system: str, messages: list[dict]) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                msg: dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    msg["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                        }
                        for tc in m["tool_calls"]
                    ]
                out.append(msg)
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        return out

    async def complete(self, system, messages, tools):
        base = (self.cfg.base_url or "https://api.openai.com/v1").rstrip("/")
        body: dict[str, Any] = {"model": self.cfg.model, "messages": self.to_messages(system, messages)}
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
                }
                for t in tools
            ]
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"} if self.cfg.api_key else {}
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                r = await client.post(f"{base}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach the model at {base}: {e}") from e
        if r.status_code == 401:
            raise LLMError("The API key is missing or invalid. Add one in Settings.")
        if r.status_code >= 400:
            raise LLMError(f"Model error ({r.status_code}): {r.text[:500]}")
        choice = r.json()["choices"][0]
        msg = choice.get("message") or {}
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments")}
            calls.append(
                ToolCall(id=tc.get("id") or fn.get("name", "call"), name=fn.get("name", ""), arguments=args)
            )
        return LLMReply(
            text=(msg.get("content") or "").strip(),
            tool_calls=calls,
            stop_reason=choice.get("finish_reason") or "",
        )


def make_llm(cfg: LLMConfig) -> LLM:
    if cfg.provider == "anthropic":
        return AnthropicLLM(cfg)
    if cfg.provider == "openai":
        return OpenAICompatLLM(cfg)
    raise LLMError(f"Unknown LLM provider: {cfg.provider}")
