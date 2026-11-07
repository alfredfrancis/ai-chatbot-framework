"""Runtime settings, read from environment variables (prefix ACF_)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"ACF_{name}", default)


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
    compact_tokens: int = field(default_factory=lambda: int(_env("COMPACT_TOKENS", "120000")))
    compact_keep_tokens: int = field(default_factory=lambda: int(_env("COMPACT_KEEP_TOKENS", "20000")))
    max_agent_steps: int = field(default_factory=lambda: int(_env("MAX_AGENT_STEPS", "40")))

    # Sandbox
    sandbox: str = field(default_factory=lambda: _env("SANDBOX", "docker"))  # docker | local
    sandbox_prefix: str = field(default_factory=lambda: _env("SANDBOX_PREFIX", "acf-sbx"))
    sandbox_image: str = field(default_factory=lambda: _env("SANDBOX_IMAGE", "acf-sandbox:latest"))
    # Host path of data_dir, when AI Chatbot Framework itself runs in a container and talks to the host's Docker.
    sandbox_host_data_dir: str = field(default_factory=lambda: _env("SANDBOX_HOST_DATA_DIR"))
    sandbox_network: str = field(default_factory=lambda: _env("SANDBOX_NETWORK", "bridge"))
    sandbox_memory: str = field(default_factory=lambda: _env("SANDBOX_MEMORY", "1g"))
    sandbox_cpus: str = field(default_factory=lambda: _env("SANDBOX_CPUS", "1"))
    command_timeout: int = field(default_factory=lambda: int(_env("COMMAND_TIMEOUT", "120")))

    # Extra one-click MCP servers for the Connections page (JSON list; see acf/mcp_presets.py).
    mcp_presets_file: str = field(default_factory=lambda: _env("MCP_PRESETS_FILE"))

    # Scheduler
    scheduler_enabled: bool = field(default_factory=lambda: _env("SCHEDULER", "true").lower() == "true")
    scheduler_interval: float = field(default_factory=lambda: float(_env("SCHEDULER_INTERVAL", "20")))

    def __post_init__(self) -> None:
        if bool(self.admin_email) != bool(self.admin_password):
            raise ValueError("Set both ACF_ADMIN_EMAIL and ACF_ADMIN_PASSWORD, or neither")
        if self.admin_email and "@" not in self.admin_email:
            raise ValueError("ACF_ADMIN_EMAIL must be an email address")
        if self.admin_password and len(self.admin_password) < 8:
            raise ValueError("ACF_ADMIN_PASSWORD must be at least 8 characters")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.db_url:
            self.db_url = f"sqlite:///{self.data_dir / 'acf.db'}"

    def default_model(self, provider: str) -> str:
        if self.llm_model:
            return self.llm_model
        return "claude-opus-5-5" if provider == "anthropic" else "gpt-4.1-mini"


settings = Settings()


def reload_settings() -> Settings:
    """Re-read the environment (used by tests)."""
    global settings
    settings = Settings()
    return settings
