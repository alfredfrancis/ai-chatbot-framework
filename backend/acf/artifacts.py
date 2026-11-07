"""A chat's artifacts: the workspace files it was given and the files the agent made in it.

Worked out from the stored messages, so nothing extra is recorded while the agent runs:
- uploaded: files attached to the chat's user messages (`[Attached file: name](file:///workspace/…)` lines)
- produced: paths the agent wrote or edited, and files changed in the workspace while one of the chat's
  bash commands (background ones too) was running. The last part goes by modification time, so a file
  another chat changed at the same moment can show up as well.
Files that no longer exist, hidden paths and the steering files (context.md, memory.md) are left out.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy.orm import Session

from acf import workspace
from acf.db import Message

SLACK = 0.05  # seconds before a command's measured start (its result is saved, and timed, just after it ends)
MAX_SCAN = 5000  # workspace files looked at for changes made by commands


def _ts(dt: datetime) -> float:
    return dt.replace(tzinfo=UTC).timestamp()


def _rel(root: Path, user_id: int, path: str) -> str | None:
    try:
        target = workspace.resolve(user_id, path)
    except ValueError:
        return None
    return str(target.relative_to(root)) if target != root else None


def _visible(rel: str) -> bool:
    return rel not in workspace.MANAGED_FILES and not any(p.startswith(".") for p in Path(rel).parts)


def _command_windows(msgs: list[Message]) -> list[tuple[float, float]]:
    """(start, end) of every bash command the chat ran, as epoch seconds."""
    calls = {tc["id"]: tc for m in msgs if m.role == "assistant" for tc in m.tool_calls or [] if tc.get("id")}
    notes = {m.background: m for m in msgs if m.role == "user" and m.background}
    windows = []
    for m in msgs:
        if m.role != "tool" or calls.get(m.tool_call_id or "", {}).get("name") != "bash":
            continue
        end = _ts(m.created_at)
        start = end - ((m.raw or {}).get("duration_ms") or 0) / 1000
        if m.background:
            note = notes.get(m.background)
            end = _ts(note.created_at) if note else time.time()
        windows.append((start - SLACK, end))
    return windows


def _changed_during(root: Path, windows: list[tuple[float, float]]) -> list[tuple[float, str]]:
    if not windows:
        return []
    found = []
    for i, p in enumerate(root.rglob("*")):
        if i >= MAX_SCAN:
            break
        rel = p.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or not p.is_file():
            continue
        mtime = p.stat().st_mtime
        if any(a <= mtime <= b for a, b in windows):
            found.append((mtime, str(rel)))
    return sorted(found)


def chat_artifacts(db: Session, chat_id: int, user_id: int) -> list[dict]:
    """[{path, name, kind: uploaded|produced, size, modified_at}]: attached and written files in message order,
    then files changed by commands, oldest change first."""
    root = workspace.workspace_dir(user_id).resolve()
    msgs = db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id).all()
    kinds: dict[str, str] = {}  # rel path -> kind; the first sighting wins

    def add(path: str | None, kind: str) -> None:
        rel = _rel(root, user_id, path) if path else None
        if rel and _visible(rel):
            kinds.setdefault(rel, kind)

    for m in msgs:
        if m.role == "user" and not m.background:
            for _, uri in workspace.ATTACHED_RE.findall(m.content or ""):
                add(unquote(uri[len("file:///workspace/") :]), "uploaded")
        elif m.role == "assistant":
            for tc in m.tool_calls or []:
                if tc.get("name") in ("write", "edit"):
                    add(str((tc.get("arguments") or {}).get("path") or ""), "produced")
    for _, rel in _changed_during(root, _command_windows(msgs)):
        add(rel, "produced")

    out = []
    for rel, kind in kinds.items():
        p = root / rel
        if not p.is_file():
            continue
        st = p.stat()
        modified = datetime.fromtimestamp(st.st_mtime, UTC).replace(tzinfo=None).isoformat() + "Z"
        out.append({"path": rel, "name": p.name, "kind": kind, "size": st.st_size, "modified_at": modified})
    return out
