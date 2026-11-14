"""Runtime settings, read from environment variables (prefix ACF_)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"ACF_{name}", default)


DEFAULT_PROVIDERS = "anthropic,openai,google_genai,mistralai,groq,deepseek,xai,fireworks,together,perplexity"


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", "./data")).resolve())
    db_url: str = field(default_factory=lambda: _env("DB_URL"))
    # Public URL of the web app; used to build OAuth redirect URIs.
    public_url: str = field(default_factory=lambda: _env("PUBLIC_URL", "http://localhost:8000").rstrip("/"))
    frontend_dist: Path = field(
        default_factory=lambda: Path(
            _env("FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist"))
        )
    )
    # Main account, created (and its password kept in sync) at startup when both are set.
    admin_email: str = field(default_factory=lambda: _env("ADMIN_EMAIL").strip().lower())
    admin_password: str = field(default_factory=lambda: _env("ADMIN_PASSWORD"))
    admin_name: str = field(default_factory=lambda: _env("ADMIN_NAME").strip())
    # Open sign-ups. Unset: open, unless a main account is configured.
    allow_signup: bool = field(
        default_factory=lambda: (
            _env("ALLOW_SIGNUP").strip().lower() == "true"
            if _env("ALLOW_SIGNUP").strip()
            else not _env("ADMIN_EMAIL").strip()
        )
    )
    # Encrypts secrets stored in the database (see acf/secrets_box.py). Any long random string.
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY"))
    cookie_secure: bool = field(default_factory=lambda: _env("COOKIE_SECURE", "false").lower() == "true")

    # LLM defaults (each user can override in Settings).
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "anthropic"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", ""))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", ""))
    llm_api_key: str = field(
        default_factory=lambda: (
            _env("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
        )
    )
    # Providers users may pick in Settings (comma-separated LangChain ids; "*" = any). The default lists
    # providers that take an API key, so a user can't make the server use credentials from its environment
    # (e.g. bedrock with the machine's cloud role). The server's own provider is always allowed.
    llm_providers: str = field(default_factory=lambda: _env("LLM_PROVIDERS").strip() or DEFAULT_PROVIDERS)
    # The models users can pick (JSON list; see acf/models.py). Unset: a built-in list.
    models_file: str = field(default_factory=lambda: _env("MODELS_FILE").strip())
    # Users may add models of their own to their list; false limits everyone to the models above.
    custom_models: bool = field(default_factory=lambda: _env("CUSTOM_MODELS", "true").strip().lower() != "false")
    # The model's context window in tokens, for the chat's context meter (0 = the model's own, from
    # LangChain's model profile; 128000 when unknown).
    context_window: int = field(default_factory=lambda: int(_env("CONTEXT_WINDOW", "0")))
    # Earlier messages are summarised when a chat grows past this many tokens; a model with a token window
    # set (in the models file or by the user) compacts at 80% of that window instead.
    compact_tokens: int = field(default_factory=lambda: int(_env("COMPACT_TOKENS", "120000")))
    compact_keep_tokens: int = field(default_factory=lambda: int(_env("COMPACT_KEEP_TOKENS", "20000")))
    max_agent_steps: int = field(default_factory=lambda: int(_env("MAX_AGENT_STEPS", "40")))
    # Sub-agents (the `agent` tool): how many of a run's sub-agents work at the same time; the rest wait
    # their turn (0 = no sub-agents).
    subagents: int = field(default_factory=lambda: int(_env("SUBAGENTS", "8")))
    # The model a sub-agent gets when the main agent asks for "fast" (unset: a small model of the user's
    # provider when one is known, else the user's own model).
    subagent_fast_model: str = field(default_factory=lambda: _env("SUBAGENT_FAST_MODEL").strip())
    # memory.md goes into every system prompt; writes past this many characters are refused.
    memory_limit: int = field(default_factory=lambda: int(_env("MEMORY_LIMIT", "4000")))
    # Every N user messages in a chat, a background pass reviews it and updates memory.md and skills (0 = off).
    review_interval: int = field(default_factory=lambda: int(_env("REVIEW_INTERVAL", "10")))
    # After a chat's first reply, the model gives it a short title (false: chats keep their first message as title).
    auto_titles: bool = field(default_factory=lambda: _env("AUTO_TITLES", "true").lower() == "true")
    # Skills not read for this many days move to skills/.archive/ (0 = never).
    skill_archive_days: int = field(default_factory=lambda: int(_env("SKILL_ARCHIVE_DAYS", "30")))

    # Sandbox
    sandbox: str = field(default_factory=lambda: _env("SANDBOX", "docker"))  # docker | local
    sandbox_prefix: str = field(default_factory=lambda: _env("SANDBOX_PREFIX", "acf-sbx"))
    sandbox_image: str = field(default_factory=lambda: _env("SANDBOX_IMAGE", "acf-sandbox:latest"))
    # Host path of data_dir, when AI Chatbot Framework itself runs in a container and talks to the host's Docker.
    sandbox_host_data_dir: str = field(default_factory=lambda: _env("SANDBOX_HOST_DATA_DIR"))
    # Sandboxes get their own bridge network with inter-container traffic off (created when missing).
    # deploy/sandbox-firewall.sh blocks it from private, link-local and metadata addresses by its
    # interface name (ACF_SANDBOX_BRIDGE). "none" cuts sandboxes off from the network.
    sandbox_network: str = field(default_factory=lambda: _env("SANDBOX_NETWORK", "acf-sandbox"))
    sandbox_bridge: str = field(default_factory=lambda: _env("SANDBOX_BRIDGE", "acf-sbx0"))
    # Container runtime, e.g. "runsc" (gVisor: a user-space kernel between sandboxes and the host).
    sandbox_runtime: str = field(default_factory=lambda: _env("SANDBOX_RUNTIME"))
    sandbox_memory: str = field(default_factory=lambda: _env("SANDBOX_MEMORY", "1g"))
    sandbox_cpus: str = field(default_factory=lambda: _env("SANDBOX_CPUS", "1"))
    command_timeout: int = field(default_factory=lambda: int(_env("COMMAND_TIMEOUT", "120")))

    # Extra one-click MCP servers for the Connections page (JSON list; see acf/mcp_presets.py).
    mcp_presets_file: str = field(default_factory=lambda: _env("MCP_PRESETS_FILE"))

    # Scheduler
    scheduler_enabled: bool = field(default_factory=lambda: _env("SCHEDULER", "true").lower() == "true")
    scheduler_interval: float = field(default_factory=lambda: float(_env("SCHEDULER_INTERVAL", "20")))

    # Several app processes: they share run state through Redis (see acf/bus.py) and need PostgreSQL and
    # one data folder. Unset: one process keeps it in memory.
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL"))
    redis_prefix: str = field(default_factory=lambda: _env("REDIS_PREFIX", "acf"))
    # A process that stops refreshing its chats, locks and jobs loses them after this many seconds.
    bus_ttl: float = field(default_factory=lambda: float(_env("BUS_TTL", "30")))
    # On shutdown (e.g. scaling in), running agents get this long to finish before they are stopped.
    shutdown_grace: float = field(default_factory=lambda: float(_env("SHUTDOWN_GRACE", "20")))

    def __post_init__(self) -> None:
        if bool(self.admin_email) != bool(self.admin_password):
            raise ValueError("Set both ACF_ADMIN_EMAIL and ACF_ADMIN_PASSWORD, or neither")
        if self.admin_email and "@" not in self.admin_email:
            raise ValueError("ACF_ADMIN_EMAIL must be an email address")
        if self.admin_password and len(self.admin_password) < 8:
            raise ValueError("ACF_ADMIN_PASSWORD must be at least 8 characters")
        if len(self.sandbox_bridge) > 15:
            raise ValueError("ACF_SANDBOX_BRIDGE must be at most 15 characters (a Linux interface name)")
        if self.secret_key and len(self.secret_key) < 32:
            raise ValueError("ACF_SECRET_KEY must be at least 32 characters (e.g. `openssl rand -base64 48`)")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_url:
            self.db_url = f"sqlite:///{self.data_dir / 'acf.db'}"

    def provider_allowed(self, provider: str) -> bool:
        allowed = {p.strip() for p in self.llm_providers.split(",") if p.strip()}
        return "*" in allowed or provider in allowed or provider == self.llm_provider

    def allowed_providers(self) -> list[str]:
        allowed = [p.strip() for p in self.llm_providers.split(",") if p.strip()]
        return allowed if "*" in allowed else sorted({*allowed, self.llm_provider})


settings = Settings()


def reload_settings() -> Settings:
    """Re-read the environment (used by tests)."""
    global settings
    settings = Settings()
    return settings
