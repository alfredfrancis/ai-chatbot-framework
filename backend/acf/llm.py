"""Model access through LangChain's `init_chat_model`.

Any LangChain chat provider works (`anthropic`, `openai`, `ollama`, `google_genai`, `bedrock`… — the
matching `langchain-<provider>` package must be installed). `openai` with a base URL covers every
OpenAI-compatible server (Ollama, OpenRouter, vLLM, LiteLLM).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from acf import config

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-4.1-mini"}
# Claude models that accept output_config.effort.
_EFFORT_MODELS = ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-haiku-5", "claude-opus-4-8")


class LLMError(RuntimeError):
    pass


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
            model=user.llm_model or s.llm_model or DEFAULT_MODELS.get(provider, ""),
            api_key=user.llm_api_key or s.llm_api_key,
            base_url=user.llm_base_url or s.llm_base_url,
        )


def make_model(cfg: LLMConfig) -> BaseChatModel:
    if not cfg.model:
        raise LLMError(f"No model set for provider '{cfg.provider}'. Choose one in Settings.")
    kwargs: dict[str, Any] = {"max_retries": 2}
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.provider == "anthropic":
        kwargs["max_tokens"] = 16000
        kwargs["default_request_timeout"] = 600
        if cfg.model.startswith(_EFFORT_MODELS):
            kwargs["output_config"] = {"effort": "medium"}
    elif cfg.provider == "openai":
        kwargs["timeout"] = 600
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


def estimate_tokens(obj: Any) -> int:
    """Cheap token estimate (~4 characters per token)."""
    return len(str(obj)) // 4
