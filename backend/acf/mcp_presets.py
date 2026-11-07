"""Ready-made remote MCP servers people can add in one click.

Every built-in entry is a Streamable HTTP endpoint whose provider supports OAuth with dynamic client
registration (RFC 7591), so it works without an API key or a pre-registered client: add it, press
Sign in. Operators can add or override entries with a JSON file (ACF_MCP_PRESETS_FILE):

    [{"id": "acme", "name": "Acme", "description": "Tickets and docs", "url": "https://mcp.acme.com/mcp"}]
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from acf import config

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class Preset:
    id: str  # also the server name in the user's config
    name: str
    description: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)


BUILTIN: list[Preset] = [
    Preset("linear", "Linear", "Issues, projects and cycles", "https://mcp.linear.app/mcp"),
    Preset("notion", "Notion", "Pages, databases and search", "https://mcp.notion.com/mcp"),
    Preset("atlassian", "Jira & Confluence", "Atlassian issues and wiki pages", "https://mcp.atlassian.com/v1/mcp"),
    Preset("sentry", "Sentry", "Errors, issues and releases", "https://mcp.sentry.dev/mcp"),
    Preset("monday", "monday.com", "Boards, items and updates", "https://mcp.monday.com/mcp"),
    Preset("canva", "Canva", "Designs and brand assets", "https://mcp.canva.com/mcp"),
    Preset("intercom", "Intercom", "Customer conversations and contacts", "https://mcp.intercom.com/mcp"),
    Preset("stripe", "Stripe", "Payments, customers and invoices", "https://mcp.stripe.com"),
    Preset("vercel", "Vercel", "Projects, deployments and logs", "https://mcp.vercel.com"),
    Preset("huggingface", "Hugging Face", "Models, datasets and Spaces", "https://huggingface.co/mcp"),
]


def _load_file(path: str) -> list[Preset]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"Could not read MCP presets file {path}: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"MCP presets file {path} must contain a JSON list")
    out = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"MCP presets file {path}: every entry must be an object")
        pid, url = str(item.get("id", "")), str(item.get("url", ""))
        if not _ID_RE.match(pid) or not url.startswith(("http://", "https://")) or not item.get("name"):
            raise ValueError(
                f'MCP presets file {path}: entry "{pid}" needs an id (letters, numbers, - _), name and url'
            )
        out.append(Preset(pid, str(item["name"]), str(item.get("description", "")), url))
    return out


def presets() -> list[Preset]:
    """Built-in presets, with entries from ACF_MCP_PRESETS_FILE overriding or extending them."""
    merged = {p.id: p for p in BUILTIN}
    if config.settings.mcp_presets_file:
        merged.update({p.id: p for p in _load_file(config.settings.mcp_presets_file)})
    return list(merged.values())


def get(preset_id: str) -> Preset | None:
    return next((p for p in presets() if p.id == preset_id), None)
