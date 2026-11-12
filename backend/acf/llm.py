"""Model access through LangChain's `init_chat_model`.

Any LangChain chat provider works (`anthropic`, `openai`, `ollama`, `google_genai`, `bedrock`… — the
matching `langchain-<provider>` package must be installed). `openai` with a base URL covers every
OpenAI-compatible server (Ollama, OpenRouter, vLLM, LiteLLM).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage

from acf import config, models

# What "fast" means for a sub-agent, per provider (ACF_SUBAGENT_FAST_MODEL overrides it).
FAST_MODELS = {"anthropic": "claude-haiku-5-5", "openai": "gpt-4.1-mini"}


# Sent instead of a key when the user has none for their own provider or server.
NO_KEY = "not-set"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    effort: str = ""  # "" = the provider's own default
    context_window: int = 0  # the token window for the context meter and compaction (0 = the model's own)

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"

    @classmethod
    def for_user(cls, user: Any, model: str = "", effort: str = "") -> LLMConfig:
        """Settings for a model key ("provider:model"; "" = the user's default) and effort ("" = the user's,
        else the model's default).

        The key and address come from the user's settings for that provider. The server's API key is only ever
        sent to the server's own provider and address. For any other provider or server the user must bring a
        key; without one a placeholder is sent, so provider libraries can't pick up the server's key from the
        environment either.
        """
        s = config.settings
        key = model or models.user_default(user)
        provider, model_id = models.split(key)
        conn = models.connections(user).get(provider, {})
        own_key, own_url = conn.get("api_key", ""), conn.get("base_url", "")
        if models.uses_server_key(provider, own_url):  # empty server key: the provider library's own credentials
            api_key, base_url = own_key or s.llm_api_key, s.llm_base_url
        else:
            api_key, base_url = own_key or NO_KEY, own_url
        return cls(
            provider=provider,
            model=model_id or models.DEFAULT_MODELS.get(provider, ""),
            api_key=api_key,
            base_url=base_url,
            effort=models.resolve_effort(key, effort or user.llm_effort or ""),
            context_window=models.window_for(user, key),
        )

    @classmethod
    def for_chat(cls, user: Any, chat_id: int | None) -> LLMConfig:
        """Settings for a chat: its own model and effort, else the user's."""
        from acf.db import Chat, session_scope

        model = effort = ""
        if chat_id is not None:
            with session_scope() as db:
                chat = db.get(Chat, chat_id)
                if chat is not None:
                    model, effort = chat.model, chat.effort
        return cls.for_user(user, model, effort)

    def with_model(self, choice: str) -> LLMConfig:
        """These settings for a sub-agent: "inherit" (or nothing) keeps the model, "fast" is the provider's
        small model, anything else is a model id. The provider, address and key never change, so a model
        the main agent names can't send the key anywhere else."""
        choice = (choice or "inherit").strip()
        if choice == "inherit":
            return self
        if choice == "fast":
            choice = config.settings.subagent_fast_model or FAST_MODELS.get(self.provider) or self.model
        key = f"{self.provider}:{choice}"
        return replace(
            self,
            model=choice,
            effort=models.resolve_effort(key, self.effort),
            context_window=models.info(key).context_window,
        )


def make_model(cfg: LLMConfig) -> BaseChatModel:
    if not config.settings.provider_allowed(cfg.provider):
        raise LLMError(f"The provider '{cfg.provider}' is not available on this server. Choose another in Settings.")
    if not cfg.model:
        raise LLMError(f"No model set for provider '{cfg.provider}'. Choose one in Settings.")
    if not models.allowed(cfg.provider, cfg.model):
        raise LLMError(f"The model '{cfg.model}' is not available on this server. Choose another in Settings.")
    kwargs: dict[str, Any] = {"max_retries": 2}
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.provider == "anthropic":
        kwargs["max_tokens"] = 16000
        kwargs["default_request_timeout"] = 600
        if cfg.effort:
            kwargs["output_config"] = {"effort": cfg.effort}
    elif cfg.provider == "openai":
        kwargs["timeout"] = 600
        if cfg.effort:
            kwargs["reasoning_effort"] = cfg.effort
    try:
        return init_chat_model(cfg.model, model_provider=cfg.provider, **kwargs)
    except ImportError as e:
        raise LLMError(f"Provider '{cfg.provider}' is not installed: {e}") from e
    except Exception as e:  # noqa: BLE001 - bad provider names, missing keys…
        raise LLMError(f"Could not set up the model: {e}") from e


def friendly_error(e: BaseException) -> str:
    """Turn provider exceptions into one sentence a non-technical user understands."""
    name = type(e).__name__
    status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    msg = str(e)
    if status == 401 or name == "AuthenticationError":
        return "The model's API key is missing or invalid. Add one in Settings."
    if status == 429 or name == "RateLimitError":
        return "The model is rate limited right now. Try again in a minute."
    if name in ("APIConnectionError", "ConnectError", "ConnectionError") or "Connection error" in msg:
        return "Could not reach the model. Check the server address in Settings."
    if status:
        return f"Model error ({status}): {msg[:300]}"
    return f"Model error: {msg[:300]}"


def text_of(ai: AIMessage) -> str:
    """The visible text of a model answer (no thinking, no tool calls)."""
    if isinstance(ai.content, str):
        return ai.content.strip()
    return "\n".join(b.get("text", "") for b in ai.content if isinstance(b, dict) and b.get("type") == "text").strip()


def calls_of(ai: AIMessage) -> list[dict[str, Any]]:
    """The tool calls of a model answer; one with arguments that didn't parse carries an `error`."""
    return list(ai.tool_calls) + [
        {
            "id": c.get("id") or f"invalid_{i}",
            "name": c.get("name") or "unknown",
            "args": {},
            "error": c.get("error") or "Invalid arguments",
        }
        for i, c in enumerate(ai.invalid_tool_calls)
    ]


def estimate_tokens(obj: Any) -> int:
    """Cheap token estimate (~4 characters per token)."""
    return len(str(obj)) // 4
