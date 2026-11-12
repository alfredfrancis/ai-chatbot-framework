"""The models users can pick: the operator's catalogue, each user's own list, and a chat's choice.

The catalogue is the built-in list below, or the JSON list in ACF_MODELS_FILE, which replaces it:

    [{"provider": "anthropic", "id": "claude-opus-5-5", "name": "Claude Opus 5.5",
      "efforts": ["low", "medium", "high", "max"], "effort": "medium",
      "context_window": 200000, "max_context_window": 1000000}]

`efforts` are the effort levels the model accepts (none: it has no effort setting), `effort` the default.
`context_window` is the token window the chat's context meter and compaction use (0 = the model's own, from
LangChain's profile); users may set their own up to `max_context_window` (0 = no limit). Only models of
allowed providers (ACF_LLM_PROVIDERS) are offered. Users may add models of their own unless
ACF_CUSTOM_MODELS=false, which limits everyone to the catalogue.

A model is named by its key, "<provider>:<model id>" (the id may itself hold colons, e.g. "llama3:8b").
Each user keeps, per key, whether it is on in their model picker, their token window, and whether they added
it (User.llm_models).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from acf import config

PROVIDER_ID = re.compile(r"[a-z][a-z0-9_-]{1,40}")
MIN_WINDOW = 1000

_CLAUDE_EFFORTS = ["low", "medium", "high", "max"]
_OPENAI_EFFORTS = ["minimal", "low", "medium", "high"]
# Models added by hand get the effort levels of their family.
_EFFORT_FAMILIES = {
    "anthropic": (
        ("claude-opus-5", "claude-sonnet-5", "claude-fable-5", "claude-haiku-5", "claude-opus-4-8"),
        _CLAUDE_EFFORTS,
        "medium",
    ),
    "openai": (("gpt-5", "o3", "o4"), _OPENAI_EFFORTS, "medium"),
}
PROVIDER_NAMES = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google_genai": "Google",
    "mistralai": "Mistral",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "xai": "xAI",
    "fireworks": "Fireworks",
    "together": "Together",
    "perplexity": "Perplexity",
    "ollama": "Ollama",
}


@dataclass
class ModelInfo:
    provider: str
    id: str
    name: str = ""
    efforts: list[str] = field(default_factory=list)
    effort: str = ""
    context_window: int = 0
    max_context_window: int = 0

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.id}"


BUILTIN = [
    ModelInfo("anthropic", "claude-opus-5-5", "Claude Opus 5.5", _CLAUDE_EFFORTS, "medium"),
    ModelInfo("anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5", _CLAUDE_EFFORTS, "medium"),
    ModelInfo("anthropic", "claude-haiku-5-5", "Claude Haiku 5.5", _CLAUDE_EFFORTS, "medium"),
    ModelInfo("anthropic", "claude-fable-5-2", "Claude Fable 5.2", _CLAUDE_EFFORTS, "medium"),
    ModelInfo("openai", "gpt-5", "GPT-5", _OPENAI_EFFORTS, "medium"),
    ModelInfo("openai", "gpt-5-mini", "GPT-5 mini", _OPENAI_EFFORTS, "medium"),
    ModelInfo("openai", "gpt-4.1-mini", "GPT-4.1 mini"),
]
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-4.1-mini"}


def split(key: str) -> tuple[str, str]:
    """ "provider:model" -> (provider, model); a key without a provider is a model of the server's provider."""
    provider, sep, model = key.partition(":")
    if not sep or not PROVIDER_ID.fullmatch(provider):
        return config.settings.llm_provider, key
    return provider, model


def _load_file(path: str) -> list[ModelInfo]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Could not read models file {path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"Models file {path} must contain a JSON list")
    out = []
    for entry in data:
        if not isinstance(entry, dict) or not entry.get("id") or not PROVIDER_ID.fullmatch(str(entry.get("provider"))):
            raise ValueError(f"Models file {path}: every entry needs a provider and an id")
        efforts = [str(e) for e in entry.get("efforts") or []]
        effort = str(entry.get("effort") or (efforts[0] if efforts else ""))
        if effort and effort not in efforts:
            raise ValueError(f"Models file {path}: {entry['id']}: effort '{effort}' is not one of its efforts")
        out.append(
            ModelInfo(
                provider=str(entry["provider"]),
                id=str(entry["id"]),
                name=str(entry.get("name") or ""),
                efforts=efforts,
                effort=effort,
                context_window=int(entry.get("context_window") or 0),
                max_context_window=int(entry.get("max_context_window") or 0),
            )
        )
    return out


def catalogue() -> list[ModelInfo]:
    """The operator's models, of providers this server offers."""
    s = config.settings
    models = _load_file(s.models_file) if s.models_file else BUILTIN
    return [m for m in models if s.provider_allowed(m.provider)]


def _guess(provider: str, model_id: str) -> ModelInfo:
    """A model that isn't in the catalogue: effort levels of its family, if known."""
    prefixes, efforts, effort = _EFFORT_FAMILIES.get(provider, ((), [], ""))
    if model_id.startswith(prefixes):
        return ModelInfo(provider, model_id, "", list(efforts), effort)
    return ModelInfo(provider, model_id)


def info(key: str) -> ModelInfo:
    provider, model_id = split(key)
    for m in catalogue():
        if m.provider == provider and m.id == model_id:
            return m
    return _guess(provider, model_id)


def in_catalogue(provider: str, model_id: str) -> bool:
    return any(m.provider == provider and m.id == model_id for m in catalogue())


def server_default() -> str:
    s = config.settings
    return f"{s.llm_provider}:{s.llm_model or DEFAULT_MODELS.get(s.llm_provider, '')}"


def user_default(user: Any) -> str:
    """The user's default model key (the server's when they haven't chosen one)."""
    if user.llm_model:
        return f"{user.llm_provider or config.settings.llm_provider}:{user.llm_model}"
    return server_default()


def prefs(user: Any) -> dict[str, dict[str, Any]]:
    return dict(user.llm_models or {})


def connections(user: Any) -> dict[str, dict[str, str]]:
    """The user's per-provider settings: {provider: {"api_key": …, "base_url": …}}."""
    try:
        data = json.loads(user.llm_connections or "{}")
    except json.JSONDecodeError:
        return {}
    return {
        p: {"api_key": str(c.get("api_key") or ""), "base_url": str(c.get("base_url") or "")}
        for p, c in data.items()
        if isinstance(c, dict)
    }


def uses_server_key(provider: str, base_url: str) -> bool:
    """The server's API key only ever goes to the server's own provider and address."""
    s = config.settings
    return provider == s.llm_provider and base_url.rstrip("/") in ("", s.llm_base_url.rstrip("/"))


def usable(user: Any, provider: str) -> bool:
    """Whether a request to this provider would carry a key (the user's or the server's)."""
    conn = connections(user).get(provider, {})
    if conn.get("api_key"):
        return True
    return uses_server_key(provider, conn.get("base_url", "")) and bool(config.settings.llm_api_key)


def window_for(user: Any, key: str) -> int:
    """The token window for this user and model (0 = the model's own)."""
    own = int(prefs(user).get(key, {}).get("context_window") or 0)
    return own or info(key).context_window


def resolve_effort(key: str, effort: str) -> str:
    """The effort to send: the chosen one when the model accepts it, else the model's default ("" = none)."""
    m = info(key)
    return effort if effort in m.efforts else m.effort


def user_models(user: Any) -> list[dict[str, Any]]:
    """The user's model list: the catalogue plus models they added, each with whether it's on."""
    p = prefs(user)
    s = config.settings
    seen: dict[str, ModelInfo] = {m.key: m for m in catalogue()}
    custom = []
    for key, pref in p.items():
        if pref.get("custom") and key not in seen:
            provider, model_id = split(key)
            if s.provider_allowed(provider) and s.custom_models:
                seen[key] = _guess(provider, model_id)
                custom.append(key)
    default = user_default(user)
    out = []
    for key, m in seen.items():
        pref = p.get(key, {})
        ready = usable(user, m.provider)
        enabled = bool(pref["enabled"]) if "enabled" in pref else ready
        out.append(
            {
                **asdict(m),
                "key": key,
                "name": m.name or m.id,
                "custom": key in custom,
                "enabled": enabled or key == default,
                "has_key": ready,
                "window": int(pref.get("context_window") or 0) or m.context_window,
            }
        )
    return out


def allowed(provider: str, model_id: str) -> bool:
    """Whether this server lets anyone run this model."""
    s = config.settings
    return s.provider_allowed(provider) and (s.custom_models or in_catalogue(provider, model_id))


def config_options(user: Any, model_key: str = "", effort: str = "") -> list[dict[str, Any]]:
    """ACP session config options for a chat: the model picker and, for models that have one, effort."""
    current = model_key or user_default(user)
    listed = [m for m in user_models(user) if m["enabled"] or m["key"] == current]
    if not any(m["key"] == current for m in listed):
        listed.append({**asdict(info(current)), "key": current, "name": info(current).name or split(current)[1]})
    options = [
        {"value": m["key"], "name": m["name"], "description": f"{PROVIDER_NAMES.get(m['provider'], m['provider'])}"}
        for m in listed
    ]
    out: list[dict[str, Any]] = [
        {
            "id": "model",
            "name": "Model",
            "category": "model",
            "type": "select",
            "currentValue": current,
            "options": options,
        }
    ]
    m = info(current)
    if m.efforts:
        out.append(
            {
                "id": "effort",
                "name": "Effort",
                "category": "thought_level",
                "type": "select",
                "currentValue": resolve_effort(current, effort or user.llm_effort or ""),
                "options": [{"value": e, "name": e.capitalize()} for e in m.efforts],
            }
        )
    return out
