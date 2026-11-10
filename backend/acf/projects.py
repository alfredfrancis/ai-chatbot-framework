"""Projects: ongoing work with its own instructions and, optionally, a folder in the workspace.

A chat started in a project gets the project's instructions (and where its folder is) in its system
prompt, each turn, so edits reach chats that already exist. A task made for a project runs as a chat in
it. Deleting a project keeps its chats, tasks and files; they just stop belonging to it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from acf import workspace
from acf.db import Chat, Project, Task, utcnow


def own(db: Session, user_id: int, project_id: int) -> Project:
    """The user's project. Raises ValueError if there is none with that id."""
    project = db.get(Project, project_id)
    if project is None or project.user_id != user_id:
        raise ValueError(f"No project with id {project_id}")
    return project


def clean_folder(user_id: int, folder: str) -> str:
    """A folder for a project as a path relative to the workspace; it is made if it does not exist.
    "" means no folder. Raises ValueError for a path outside the workspace, a hidden one or a file."""
    if not folder.strip():
        return ""
    rel = workspace.relative(user_id, folder)
    if rel in ("", "."):
        raise ValueError("Pick a folder inside your files, not the whole workspace")
    if any(part.startswith(".") for part in rel.split("/")):
        raise ValueError("Hidden folders can't be used for a project")
    target = workspace.resolve(user_id, rel)
    if target.exists() and not target.is_dir():
        raise ValueError(f"{rel} is a file, not a folder")
    target.mkdir(parents=True, exist_ok=True)
    return rel


def create(db: Session, user_id: int, fields: dict[str, Any]) -> Project:
    project = Project(user_id=user_id, **{**fields, "folder": clean_folder(user_id, fields.get("folder") or "")})
    db.add(project)
    db.flush()
    return project


def update(project: Project, fields: dict[str, Any]) -> Project:
    """Change a project; None values are left as they are."""
    fields = {k: v for k, v in fields.items() if v is not None}
    if "folder" in fields:
        fields["folder"] = clean_folder(project.user_id, fields["folder"])
    for k, v in fields.items():
        setattr(project, k, v)
    project.updated_at = utcnow()
    return project


def delete(db: Session, project: Project) -> None:
    """Remove a project. Its chats, tasks and files stay."""
    for model in (Chat, Task):
        db.query(model).filter_by(user_id=project.user_id, project_id=project.id).update(
            {model.project_id: None}, synchronize_session=False
        )
    db.delete(project)


def counts(db: Session, user_id: int) -> dict[int, dict[str, int]]:
    """How many chats and tasks each of the user's projects has."""
    out: dict[int, dict[str, int]] = {}
    for key, model, extra in (("chats", Chat, [Chat.parent_id.is_(None)]), ("tasks", Task, [])):
        rows = (
            db.query(model.project_id, func.count(model.id))
            .filter(model.user_id == user_id, model.project_id.is_not(None), *extra)
            .group_by(model.project_id)
            .all()
        )
        for project_id, n in rows:
            out.setdefault(project_id, {})[key] = n
    return out


def as_dict(p: Project, count: dict[str, int] | None = None) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "instructions": p.instructions,
        "folder": p.folder,
        "chats": (count or {}).get("chats", 0),
        "tasks": (count or {}).get("tasks", 0),
        "created_at": p.created_at.isoformat() + "Z",
        "updated_at": p.updated_at.isoformat() + "Z",
    }
