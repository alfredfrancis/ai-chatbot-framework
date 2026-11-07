"""Per-user workspace folder. It is mounted into the user's sandbox at /workspace.

Two Markdown files steer the agent:
- context.md: written by the user ("about me", preferences, instructions)
- memory.md:  written mostly by the agent (facts it was asked to remember)
"""

from __future__ import annotations

from pathlib import Path

from acf import config

CONTEXT_FILE = "context.md"
MEMORY_FILE = "memory.md"
MANAGED_FILES = (CONTEXT_FILE, MEMORY_FILE)
MAX_FILE_BYTES = 5_000_000

DEFAULT_CONTEXT = """# About me
Write anything AI Chatbot Framework should know about you: who you are, how you like answers, what you work on.

# Preferences
- Keep answers short and clear.
"""

DEFAULT_MEMORY = """# Memory
Things AI Chatbot Framework has been asked to remember.
"""


def user_root(user_id: int) -> Path:
    return config.settings.data_dir / "users" / str(user_id)


def workspace_dir(user_id: int) -> Path:
    path = user_root(user_id) / "workspace"
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        (path / CONTEXT_FILE).write_text(DEFAULT_CONTEXT)
        (path / MEMORY_FILE).write_text(DEFAULT_MEMORY)
    return path


def host_workspace_dir(user_id: int) -> str:
    """Path of the workspace as seen by the Docker daemon (differs when AI Chatbot Framework runs in a container)."""
    local = workspace_dir(user_id)
    host_root = config.settings.sandbox_host_data_dir
    if not host_root:
        return str(local)
    return str(Path(host_root) / local.relative_to(config.settings.data_dir))


def resolve(user_id: int, rel: str) -> Path:
    """Resolve a user-supplied relative path inside the workspace, refusing escapes."""
    root = workspace_dir(user_id).resolve()
    rel = rel.strip().lstrip("/")
    if rel.startswith("workspace/"):
        rel = rel[len("workspace/") :]
    target = (root / rel).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Path is outside the workspace: {rel}")
    return target


def read_file(user_id: int, name: str) -> str:
    path = resolve(user_id, name)
    if not path.exists():
        return ""
    return path.read_text(errors="replace")[:MAX_FILE_BYTES]


def write_file(user_id: int, name: str, content: str) -> None:
    if len(content.encode()) > MAX_FILE_BYTES:
        raise ValueError("File is too large (max 5 MB)")
    path = resolve(user_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def append_memory(user_id: int, fact: str) -> None:
    current = read_file(user_id, MEMORY_FILE) or DEFAULT_MEMORY
    if not current.endswith("\n"):
        current += "\n"
    write_file(user_id, MEMORY_FILE, current + f"- {fact.strip()}\n")


def list_files(user_id: int, limit: int = 500) -> list[dict]:
    root = workspace_dir(user_id)
    out = []
    for p in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        if p.is_file():
            out.append({"path": str(p.relative_to(root)), "size": p.stat().st_size})
        if len(out) >= limit:
            break
    return out
