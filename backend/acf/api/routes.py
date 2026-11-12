"""HTTP API. Everything is scoped to the signed-in user."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from acf import __version__, apps, artifacts, config, mcp_presets, models, oauth, projects, scheduler, skills, workspace
from acf.agent import loop as agent
from acf.agent import transcripts
from acf.auth import (
    COOKIE,
    SESSION_DAYS,
    create_acp_token,
    create_session,
    current_user,
    delete_session,
    hash_password,
    verify_password,
)
from acf.db import AcpToken, Chat, Message, Project, Task, User, get_db, session_scope
from acf.mcp_client import ConfigError, McpHub, parse_config
from acf.sandbox import get_sandbox

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


# ------------------------------------------------------------------ auth


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    name: str = Field("", max_length=200)


def _user_dict(u: User) -> dict[str, Any]:
    return {"id": u.id, "email": u.email, "name": u.name}


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=config.settings.cookie_secure,
        max_age=SESSION_DAYS * 86400,
        path="/",
    )


@router.get("/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@router.get("/auth/config")
def auth_config(db: Session = Depends(get_db, scope="function")) -> dict:
    has_users = db.query(User.id).first() is not None
    return {"signup_allowed": config.settings.allow_signup or not has_users, "has_users": has_users}


@router.post("/auth/signup")
def signup(body: Credentials, resp: Response, db: Session = Depends(get_db, scope="function")) -> dict:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address")
    has_users = db.query(User.id).first() is not None
    if has_users and not config.settings.allow_signup:
        raise HTTPException(403, "Sign-ups are closed on this server")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, name=body.name.strip() or email.split("@")[0], password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    workspace.workspace_dir(user.id)
    skills.seed(user.id)
    _set_cookie(resp, create_session(db, user))
    return {"user": _user_dict(user)}


class Login(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(body: Login, resp: Response, db: Session = Depends(get_db, scope="function")) -> dict:
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    _set_cookie(resp, create_session(db, user))
    return {"user": _user_dict(user)}


@router.post("/auth/logout")
def logout(request: Request, resp: Response, db: Session = Depends(get_db, scope="function")) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        delete_session(db, token)
    resp.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _user_dict(user)}


# ------------------------------------------------------------------ projects (see acf.projects)


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=500)
    instructions: str = Field("", max_length=20_000)
    folder: str = Field("", max_length=500)  # relative to the workspace; made if missing; "" = none


class ProjectPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    instructions: str | None = Field(None, max_length=20_000)
    folder: str | None = Field(None, max_length=500)


def _own_project(db: Session, user: User, project_id: int) -> Project:
    try:
        return projects.own(db, user.id, project_id)
    except ValueError as e:
        raise HTTPException(404, "Project not found") from e


@router.get("/projects")
def list_projects(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> list[dict]:
    counts = projects.counts(db, user.id)
    rows = db.query(Project).filter_by(user_id=user.id).order_by(Project.updated_at.desc(), Project.id.desc()).all()
    return [projects.as_dict(p, counts.get(p.id)) for p in rows]


@router.post("/projects")
def create_project(
    body: ProjectIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    try:
        return projects.as_dict(projects.create(db, user.id, body.model_dump()))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/projects/{project_id}")
def get_project(
    project_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    """A project with its chats (newest first) and tasks."""
    p = _own_project(db, user, project_id)
    chats = (
        db.query(Chat)
        .filter_by(user_id=user.id, project_id=p.id, parent_id=None)
        .order_by(Chat.updated_at.desc())
        .limit(200)
        .all()
    )
    tasks = db.query(Task).filter_by(user_id=user.id, project_id=p.id).order_by(Task.id).all()
    return {
        "project": projects.as_dict(p, projects.counts(db, user.id).get(p.id)),
        "chats": [_chat_dict(c) for c in chats],
        "tasks": [scheduler.as_dict(t) for t in tasks],
    }


@router.patch("/projects/{project_id}")
def update_project(
    project_id: int,
    body: ProjectPatch,
    db: Session = Depends(get_db, scope="function"),
    user: User = Depends(current_user),
) -> dict:
    p = _own_project(db, user, project_id)
    try:
        projects.update(p, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return projects.as_dict(p, projects.counts(db, user.id).get(p.id))


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    """Remove a project; its chats, tasks and files are kept."""
    projects.delete(db, _own_project(db, user, project_id))
    return {"ok": True}


# ------------------------------------------------------------------ chats


def _chat_dict(c: Chat) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "task_id": c.task_id,
        "project_id": c.project_id,
        "parent_id": c.parent_id,  # set on a sub-agent's session
        "updated_at": _iso(c.updated_at),
    }


def _own_chat(db: Session, user: User, chat_id: int) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(404, "Chat not found")
    return chat


@router.get("/chats")
def list_chats(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> list[dict]:
    rows = db.query(Chat).filter_by(user_id=user.id, parent_id=None).order_by(Chat.updated_at.desc()).limit(200).all()
    return [_chat_dict(c) for c in rows]


class ChatIn(BaseModel):
    title: str = "New chat"
    project_id: int | None = None  # on create: start the chat in this project


@router.post("/chats")
def create_chat(
    body: ChatIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    project = _own_project(db, user, body.project_id) if body.project_id is not None else None
    chat = Chat(user_id=user.id, title=body.title[:200] or "New chat", project_id=project.id if project else None)
    db.add(chat)
    db.flush()
    return _chat_dict(chat)


@router.get("/chats/{chat_id}")
def get_chat(chat_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> dict:
    chat = _own_chat(db, user, chat_id)
    msgs = db.query(Message).filter_by(chat_id=chat.id).order_by(Message.id).all()
    return {**_chat_dict(chat), "messages": [m.to_dict() for m in msgs], "running": agent.running(chat.id)}


@router.get("/chats/{chat_id}/artifacts")
def chat_artifacts(
    chat_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> list[dict]:
    """Files uploaded to and produced by this chat (see acf.artifacts)."""
    chat = _own_chat(db, user, chat_id)
    return artifacts.chat_artifacts(db, chat.id, user.id)


@router.patch("/chats/{chat_id}")
def rename_chat(
    chat_id: int, body: ChatIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    chat = _own_chat(db, user, chat_id)
    chat.title = body.title[:200] or chat.title
    return _chat_dict(chat)


@router.delete("/chats/{chat_id}")
def delete_chat(
    chat_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    chat = _own_chat(db, user, chat_id)
    for sub in db.query(Chat).filter_by(parent_id=chat.id).all():  # its sub-agents' sessions
        db.delete(sub)
    db.delete(chat)
    transcripts.delete(user.id, chat_id)
    return {"ok": True}


# ------------------------------------------------------------------ files (read-only browser + upload)

MAX_UPLOAD = 25 * 1024 * 1024


def _resolve(user: User, path: str):
    try:
        return workspace.resolve(user.id, path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/files")
def list_dir(path: str = "", user: User = Depends(current_user)) -> dict:
    target = _resolve(user, path)
    if not target.is_dir():
        raise HTTPException(404, "Folder not found")
    root = workspace.workspace_dir(user.id)
    entries = []
    for p in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if p.name.startswith("."):
            continue
        rel = str(p.relative_to(root))
        if p.is_dir():
            entries.append({"name": p.name, "path": rel, "type": "dir", "items": sum(1 for _ in p.iterdir())})
        else:
            entries.append({"name": p.name, "path": rel, "type": "file", "size": p.stat().st_size})
    return {"path": str(target.relative_to(root)) if target != root else "", "entries": entries}


TEXT_LIMIT = 512_000


@router.get("/files/content")
def file_content(path: str, user: User = Depends(current_user)) -> dict:
    target = _resolve(user, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    data = target.read_bytes()[: TEXT_LIMIT + 1]
    binary = b"\0" in data[:4096]
    return {
        "path": path,
        "size": target.stat().st_size,
        "binary": binary,
        "truncated": len(data) > TEXT_LIMIT,
        "content": "" if binary else data[:TEXT_LIMIT].decode(errors="replace"),
    }


@router.get("/files/raw")
def file_raw(path: str, download: bool = False, user: User = Depends(current_user)):
    target = _resolve(user, path)
    if not target.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(
        target,
        filename=target.name if download else None,
        content_disposition_type="attachment" if download else "inline",
    )


@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = Form(""),
    keep: bool = Form(False),
    user: User = Depends(current_user),
) -> dict:
    """Save a file in the workspace. `keep` never replaces a file: `a.csv` becomes `a (1).csv` (chat attachments)."""
    name = (file.filename or "upload").replace("\\", "/").split("/")[-1].strip() or "upload"
    folder = folder.strip("/")
    rel = f"{folder}/{name}" if folder else name
    target = _resolve(user, rel)
    if keep:
        stem, dot, ext = name.rpartition(".") if "." in name.lstrip(".") else (name, "", "")
        n = 1
        while target.exists():
            name = f"{stem} ({n}){dot}{ext}"
            rel = f"{folder}/{name}" if folder else name
            target = _resolve(user, rel)
            n += 1
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is too large (max 25 MB)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "size": len(data)}


# ------------------------------------------------------------------ skills


@router.get("/skills")
def list_skills(user: User = Depends(current_user)) -> list[dict]:
    return [s.to_dict() for s in skills.list_skills(user.id)]


@router.post("/skills")
async def upload_skill(file: UploadFile = File(...), user: User = Depends(current_user)) -> dict:
    data = await file.read(skills.MAX_ZIP_BYTES + 1)
    try:
        return skills.install(user.id, file.filename or "skill.zip", data).to_dict()
    except skills.SkillError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/skills/{name}")
def delete_skill(name: str, user: User = Depends(current_user)) -> dict:
    try:
        skills.remove(user.id, name)
    except skills.SkillError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}


# ------------------------------------------------------------------ personal apps (see acf.apps)


@router.get("/apps")
def list_apps(user: User = Depends(current_user)) -> list[dict]:
    return [a.summary() for a in apps.list_apps(user.id)]


@router.get("/apps/{app_id}")
def get_app(app_id: str, user: User = Depends(current_user)) -> dict:
    try:
        return apps.detail(user.id, app_id)
    except apps.NotFound as e:
        raise HTTPException(404, "App not found") from e


class AppActionIn(BaseModel):
    action: apps.Action
    args: dict[str, Any] = Field(default_factory=dict)


@router.post("/apps/{app_id}/actions")
async def app_action(app_id: str, body: AppActionIn, user: User = Depends(current_user)) -> dict:
    try:
        return await apps.run_action(user, app_id, body.action, body.args)
    except apps.NotFound as e:
        raise HTTPException(404, "App not found") from e
    except (apps.AppError, ValueError) as e:
        raise HTTPException(400, str(e)) from e


# ------------------------------------------------------------------ settings & sandbox


class SettingsIn(BaseModel):
    model: str = Field("", max_length=300)  # the default model, "provider:model" ("" = the server's)
    effort: str = Field("", max_length=16)  # "" = each model's own default


class ProviderIn(BaseModel):
    base_url: str = Field("", max_length=2000)
    api_key: str | None = Field(None, max_length=4000)  # None = keep, "" = clear


class ModelIn(BaseModel):
    provider: str = Field(max_length=64)
    id: str = Field(min_length=1, max_length=200)


class ModelPatch(BaseModel):
    key: str = Field(min_length=3, max_length=300)
    enabled: bool | None = None
    context_window: int | None = Field(None, ge=0, le=100_000_000)  # 0 = the model's own


def _check_provider(provider: str) -> None:
    if not models.PROVIDER_ID.fullmatch(provider):
        raise HTTPException(400, "Provider must be a LangChain provider id such as anthropic, openai or ollama")
    if not config.settings.provider_allowed(provider):
        names = ", ".join(config.settings.allowed_providers())
        raise HTTPException(400, f"This server doesn't offer '{provider}'. Available: {names}")


def _check_model(key: str) -> None:
    provider, model_id = models.split(key)
    _check_provider(provider)
    if not model_id.strip() or not models.allowed(provider, model_id):
        raise HTTPException(400, f"This server doesn't offer the model '{model_id}'.")


@router.get("/settings")
def get_settings(user: User = Depends(current_user)) -> dict:
    s = config.settings
    conns = models.connections(user)
    shown = [
        *dict.fromkeys(
            [p for p in ("anthropic", "openai") if s.provider_allowed(p)]
            + [s.llm_provider]
            + [p for p in conns if s.provider_allowed(p)]
        )
    ]
    return {
        "model": models.user_default(user) if user.llm_model else "",
        "effort": user.llm_effort,
        "custom_models": s.custom_models,
        "allowed_providers": s.allowed_providers(),
        "providers": [
            {
                "id": p,
                "name": models.PROVIDER_NAMES.get(p, p),
                "base_url": conns.get(p, {}).get("base_url", ""),
                "has_api_key": bool(conns.get(p, {}).get("api_key")),
                "server": p == s.llm_provider,
            }
            for p in shown
        ],
        "models": models.user_models(user),
        "defaults": {
            "model": models.server_default(),
            "provider": s.llm_provider,
            "base_url": s.llm_base_url,
            "has_api_key": bool(s.llm_api_key),
        },
    }


@router.put("/settings")
def put_settings(
    body: SettingsIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    u = db.get(User, user.id)
    if body.model:
        _check_model(body.model)
        u.llm_provider, u.llm_model = models.split(body.model)
    else:
        u.llm_provider, u.llm_model = "", ""
    if body.effort and not re.fullmatch(r"[a-z]{1,16}", body.effort):
        raise HTTPException(400, "Unknown effort level")
    u.llm_effort = body.effort
    db.flush()
    return get_settings(u)


@router.put("/settings/providers/{provider}")
def put_provider(
    provider: str,
    body: ProviderIn,
    db: Session = Depends(get_db, scope="function"),
    user: User = Depends(current_user),
) -> dict:
    _check_provider(provider)
    base_url = body.base_url.strip()
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(400, "The server address must start with http:// or https://")
    u = db.get(User, user.id)
    conns = models.connections(u)
    conn = conns.get(provider, {"api_key": "", "base_url": ""})
    conn["base_url"] = base_url
    if body.api_key is not None:
        conn["api_key"] = body.api_key.strip()
    if conn["api_key"] or conn["base_url"]:
        conns[provider] = conn
    else:
        conns.pop(provider, None)
    u.llm_connections = json.dumps(conns)
    db.flush()
    return get_settings(u)


@router.post("/settings/models")
def add_model(
    body: ModelIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    """Add a model of one's own to the list (on in the model picker)."""
    _check_provider(body.provider)
    model_id = body.id.strip()
    if not model_id or any(c.isspace() for c in model_id):
        raise HTTPException(400, "A model id has no spaces, e.g. llama3.1:8b")
    key = f"{body.provider}:{model_id}"
    u = db.get(User, user.id)
    listed = models.in_catalogue(body.provider, model_id)
    if not listed and not config.settings.custom_models:
        raise HTTPException(400, "This server only offers the models in the list.")
    prefs = models.prefs(u)
    prefs[key] = {**prefs.get(key, {}), "enabled": True, "custom": not listed}
    u.llm_models = prefs
    db.flush()
    return get_settings(u)


@router.patch("/settings/models")
def patch_model(
    body: ModelPatch, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    """Turn a model on or off in the picker, or set its token window."""
    u = db.get(User, user.id)
    entry = next((m for m in models.user_models(u) if m["key"] == body.key), None)
    if entry is None:
        raise HTTPException(404, "Model not found")
    pref = dict(models.prefs(u).get(body.key, {}))
    if body.enabled is not None:
        if not body.enabled and body.key == models.user_default(u):
            raise HTTPException(400, "This is your default model. Choose another default first.")
        pref["enabled"] = body.enabled
    if body.context_window is not None:
        cap = entry["max_context_window"]
        if body.context_window and body.context_window < models.MIN_WINDOW:
            raise HTTPException(400, f"A token window is at least {models.MIN_WINDOW:,} tokens.")
        if body.context_window and cap and body.context_window > cap:
            raise HTTPException(400, f"This model's token window is at most {cap:,} tokens.")
        pref["context_window"] = body.context_window
    u.llm_models = {**models.prefs(u), body.key: pref}
    db.flush()
    return get_settings(u)


@router.delete("/settings/models")
def delete_model(key: str, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> dict:
    """Remove a model one added (models from the server's list can only be turned off)."""
    u = db.get(User, user.id)
    prefs = models.prefs(u)
    if not prefs.get(key, {}).get("custom"):
        raise HTTPException(404, "Model not found")
    if key == models.user_default(u):
        raise HTTPException(400, "This is your default model. Choose another default first.")
    prefs.pop(key)
    u.llm_models = prefs
    db.flush()
    return get_settings(u)


@router.get("/models")
def model_options(
    model: Annotated[str, Query(max_length=300)] = "",
    effort: Annotated[str, Query(max_length=16)] = "",
    user: User = Depends(current_user),
) -> dict:
    """The model and effort choices for a new chat (the ACP config options it will have), as they are with
    `model` and `effort` chosen; a model that isn't on the user's list is ignored."""
    picker = models.config_options(user)[0]
    if model not in {o["value"] for o in picker["options"]}:
        model = ""
    return {"configOptions": models.config_options(user, model, effort)}


def _acp_token_dict(row: AcpToken | None) -> dict | None:
    if not row:
        return None
    return {"hint": row.hint, "created_at": _iso(row.created_at), "last_used_at": _iso(row.last_used_at)}


@router.get("/acp/token")
def get_acp_token(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> dict:
    """The optional access token for external ACP clients (never returned after creation)."""
    return {"token": _acp_token_dict(db.get(AcpToken, user.id)), "endpoint": "/api/acp"}


@router.post("/acp/token")
def create_acp_token_route(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> dict:
    token = create_acp_token(db, user)
    db.flush()
    return {"token": _acp_token_dict(db.get(AcpToken, user.id)), "value": token, "endpoint": "/api/acp"}


@router.delete("/acp/token")
def delete_acp_token(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> dict:
    row = db.get(AcpToken, user.id)
    if row:
        db.delete(row)
    return {"token": None, "endpoint": "/api/acp"}


@router.get("/sandbox")
async def sandbox_status(user: User = Depends(current_user)) -> dict:
    return await get_sandbox(user.id).status()


@router.post("/sandbox/reset")
async def sandbox_reset(user: User = Depends(current_user)) -> dict:
    await get_sandbox(user.id).reset()
    return {"ok": True}


# ------------------------------------------------------------------ MCP


class McpConfigIn(BaseModel):
    config: str


@router.get("/mcp/config")
def get_mcp_config(user: User = Depends(current_user)) -> dict:
    return {"config": user.mcp_config}


@router.put("/mcp/config")
def put_mcp_config(
    body: McpConfigIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    try:
        parse_config(body.config)
    except ConfigError as e:
        raise HTTPException(400, str(e)) from e
    db.get(User, user.id).mcp_config = body.config
    return {"ok": True}


class McpServerIn(BaseModel):
    """One server, as edited in the Connections form. Other keys of an existing entry (e.g. oauth) are kept."""

    transport: Literal["stdio", "http"]
    command: str = Field("", max_length=1000)
    args: list[Annotated[str, Field(max_length=4000)]] = Field(default_factory=list, max_length=100)
    env: dict[str, Annotated[str, Field(max_length=4000)]] = Field(default_factory=dict, max_length=100)
    url: str = Field("", max_length=2000)
    headers: dict[str, Annotated[str, Field(max_length=4000)]] = Field(default_factory=dict, max_length=100)
    enabled: bool = True
    rename_from: str | None = Field(None, max_length=40)


_FORM_KEYS = ("command", "args", "env", "url", "headers", "enabled", "disabled")


def _config_dict(text: str) -> dict:
    try:
        parse_config(text)
    except ConfigError as e:
        raise HTTPException(400, f"Fix the JSON configuration first: {e}") from e
    data = json.loads(text or "{}")
    data.setdefault("mcpServers", {})
    return data


def _save_config(db: Session, user: User, data: dict) -> None:
    text = json.dumps(data, indent=2) + "\n"
    try:
        parse_config(text)
    except ConfigError as e:
        raise HTTPException(400, str(e)) from e
    db.get(User, user.id).mcp_config = text


@router.put("/mcp/servers/{name}")
def put_mcp_server(
    name: str, body: McpServerIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    data = _config_dict(user.mcp_config)
    servers: dict = data["mcpServers"]
    old_name = body.rename_from or name
    if old_name != name and name in servers:
        raise HTTPException(409, f'A connection named "{name}" already exists')
    if old_name != name and old_name not in servers:
        raise HTTPException(404, f'No connection named "{old_name}"')
    entry = {k: v for k, v in (servers.get(old_name) or {}).items() if k not in _FORM_KEYS}
    if body.transport == "stdio":
        entry.pop("oauth", None)
        entry.update(command=body.command.strip(), args=body.args)
        if body.env:
            entry["env"] = body.env
    else:
        entry.update(url=body.url.strip())
        if body.headers:
            entry["headers"] = body.headers
    if not body.enabled:
        entry["enabled"] = False
    if old_name in servers:  # rebuild so a renamed server keeps its position
        data["mcpServers"] = {
            (name if k == old_name else k): (entry if k == old_name else v) for k, v in servers.items()
        }
    else:
        servers[name] = entry
    _save_config(db, user, data)
    if old_name != name:
        oauth.forget(user.id, old_name)
    return {"ok": True}


@router.delete("/mcp/servers/{name}")
def delete_mcp_server(
    name: str, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    data = _config_dict(user.mcp_config)
    if name not in data["mcpServers"]:
        raise HTTPException(404, f'No connection named "{name}"')
    del data["mcpServers"][name]
    _save_config(db, user, data)
    oauth.forget(user.id, name)
    return {"ok": True}


@router.get("/mcp/presets")
def get_mcp_presets(user: User = Depends(current_user)) -> dict:
    try:
        configured = parse_config(user.mcp_config)
    except ConfigError:
        configured = {}
    out = []
    for p in mcp_presets.presets():
        cfg = configured.get(p.id)
        out.append({**p.to_dict(), "added": bool(cfg and cfg.url == p.url)})
    return {"presets": out}


@router.post("/mcp/presets/{preset_id}")
def add_mcp_preset(
    preset_id: str, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    preset = mcp_presets.get(preset_id)
    if not preset:
        raise HTTPException(404, "Unknown app")
    data = _config_dict(user.mcp_config)
    servers = data["mcpServers"]
    existing = servers.get(preset.id)
    if existing is not None and existing.get("url") != preset.url:
        raise HTTPException(409, f'A connection named "{preset.id}" already exists. Rename or remove it first.')
    if existing is None:
        servers[preset.id] = {"url": preset.url}
    _save_config(db, user, data)
    return {"config": db.get(User, user.id).mcp_config}


@router.get("/mcp/servers")
async def mcp_servers(user: User = Depends(current_user)) -> dict:
    hub = McpHub(user.id, user.mcp_config, get_sandbox(user.id))
    if hub.config_error:
        return {"error": hub.config_error, "servers": []}
    async with hub:
        return {"error": None, "servers": hub.status()}


class OAuthStartIn(BaseModel):
    redirect_uri: str


@router.post("/mcp/servers/{name}/oauth/start")
async def mcp_oauth_start(name: str, body: OAuthStartIn, user: User = Depends(current_user)) -> dict:
    servers = parse_config(user.mcp_config)
    cfg = servers.get(name)
    if not cfg or cfg.transport != "http":
        raise HTTPException(404, "No remote server with that name")
    if not body.redirect_uri.startswith(("http://", "https://")):
        raise HTTPException(400, "Invalid redirect URI")
    try:
        url = await oauth.start(user.id, name, cfg.url, cfg.oauth, body.redirect_uri)
    except oauth.OAuthError as e:
        raise HTTPException(400, str(e)) from e
    return {"authorize_url": url}


@router.delete("/mcp/servers/{name}/oauth")
def mcp_oauth_forget(name: str, user: User = Depends(current_user)) -> dict:
    oauth.forget(user.id, name)
    return {"ok": True}


class OAuthCallbackIn(BaseModel):
    code: str
    state: str


@router.post("/oauth/callback")
async def oauth_callback(body: OAuthCallbackIn, user: User = Depends(current_user)) -> dict:
    try:
        name = await oauth.complete(user.id, body.state, body.code)
    except oauth.OAuthError as e:
        raise HTTPException(400, str(e)) from e
    return {"server": name}


# ------------------------------------------------------------------ tasks


class TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=20_000)
    schedule: str = Field("", max_length=100)  # cron; leave empty for a one-off task
    run_at: str | None = Field(None, max_length=40)  # one-off: ISO date-time, local to `timezone` without offset
    timezone: str = Field("UTC", max_length=64)
    enabled: bool = True
    project_id: int | None = None  # its runs are chats in this project


class TaskPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    prompt: str | None = Field(None, min_length=1, max_length=20_000)
    schedule: str | None = Field(None, max_length=100)
    run_at: str | None = Field(None, max_length=40)
    timezone: str | None = Field(None, max_length=64)
    enabled: bool | None = None


def _own_task(db: Session, user: User, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Task not found")
    return t


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)) -> list[dict]:
    return [scheduler.as_dict(t) for t in db.query(Task).filter_by(user_id=user.id).order_by(Task.id).all()]


@router.post("/tasks")
def create_task(
    body: TaskIn, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    try:
        t = scheduler.create(db, user.id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return scheduler.as_dict(t)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int, body: TaskPatch, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    t = _own_task(db, user, task_id)
    try:
        scheduler.update(t, body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return scheduler.as_dict(t)


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    db.delete(_own_task(db, user, task_id))
    return {"ok": True}


@router.post("/tasks/{task_id}/run")
async def run_task_now(
    task_id: int, db: Session = Depends(get_db, scope="function"), user: User = Depends(current_user)
) -> dict:
    _own_task(db, user, task_id)
    task = asyncio.create_task(scheduler.run_task(task_id))
    # Return as soon as the run has created its chat, so the UI can open it.
    for _ in range(100):
        await asyncio.sleep(0.05)
        with session_scope() as s:
            t = s.get(Task, task_id)
            if t and t.last_status == "running" and t.last_chat_id:
                return {"chat_id": t.last_chat_id, "status": "running"}
        if task.done():
            break
    chat_id = await task
    return {"chat_id": chat_id, "status": "done"}
