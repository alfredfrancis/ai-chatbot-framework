"""HTTP API. Everything is scoped to the signed-in user."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from harbor import agent, config, oauth, scheduler, workspace
from harbor.auth import (
    COOKIE,
    SESSION_DAYS,
    create_session,
    current_user,
    delete_session,
    hash_password,
    verify_password,
)
from harbor.db import Chat, Message, Task, User, get_db, session_scope, utcnow
from harbor.mcp_client import ConfigError, McpHub, parse_config
from harbor.sandbox import get_sandbox

router = APIRouter(prefix="/api")


def _iso(dt) -> str | None:
    return dt.isoformat() + "Z" if dt else None


# ------------------------------------------------------------------ auth


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    name: str = ""


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
    return {"ok": True}


@router.get("/auth/config")
def auth_config(db: Session = Depends(get_db)) -> dict:
    has_users = db.query(User.id).first() is not None
    return {"signup_allowed": config.settings.allow_signup or not has_users, "has_users": has_users}


@router.post("/auth/signup")
def signup(body: Credentials, resp: Response, db: Session = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address")
    has_users = db.query(User.id).first() is not None
    if has_users and not config.settings.allow_signup:
        raise HTTPException(403, "Sign-ups are closed on this server")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(
        email=email, name=body.name.strip() or email.split("@")[0], password_hash=hash_password(body.password)
    )
    db.add(user)
    db.flush()
    workspace.workspace_dir(user.id)
    _set_cookie(resp, create_session(db, user))
    return {"user": _user_dict(user)}


class Login(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(body: Login, resp: Response, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    _set_cookie(resp, create_session(db, user))
    return {"user": _user_dict(user)}


@router.post("/auth/logout")
def logout(request: Request, resp: Response, db: Session = Depends(get_db)) -> dict:
    token = request.cookies.get(COOKIE)
    if token:
        delete_session(db, token)
    resp.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _user_dict(user)}


# ------------------------------------------------------------------ chats


def _chat_dict(c: Chat) -> dict[str, Any]:
    return {"id": c.id, "title": c.title, "task_id": c.task_id, "updated_at": _iso(c.updated_at)}


def _own_chat(db: Session, user: User, chat_id: int) -> Chat:
    chat = db.get(Chat, chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(404, "Chat not found")
    return chat


@router.get("/chats")
def list_chats(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict]:
    rows = db.query(Chat).filter_by(user_id=user.id).order_by(Chat.updated_at.desc()).limit(200).all()
    return [_chat_dict(c) for c in rows]


class ChatIn(BaseModel):
    title: str = "New chat"


@router.post("/chats")
def create_chat(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    chat = Chat(user_id=user.id, title=body.title[:200] or "New chat")
    db.add(chat)
    db.flush()
    return _chat_dict(chat)


@router.get("/chats/{chat_id}")
def get_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    chat = _own_chat(db, user, chat_id)
    msgs = db.query(Message).filter_by(chat_id=chat.id).order_by(Message.id).all()
    return {**_chat_dict(chat), "messages": [m.to_dict() for m in msgs], "running": chat.id in agent.RUNNING}


@router.patch("/chats/{chat_id}")
def rename_chat(
    chat_id: int, body: ChatIn, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict:
    chat = _own_chat(db, user, chat_id)
    chat.title = body.title[:200] or chat.title
    return _chat_dict(chat)


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    db.delete(_own_chat(db, user, chat_id))
    return {"ok": True}


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


_active: dict[int, asyncio.Task] = {}


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: int, body: MessageIn, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    _own_chat(db, user, chat_id)
    if chat_id in agent.RUNNING or (chat_id in _active and not _active[chat_id].done()):
        raise HTTPException(409, "Harbor is still working on the previous message")
    queue: asyncio.Queue = asyncio.Queue()

    async def worker() -> None:
        # Runs to completion even if the browser disconnects.
        try:
            async for ev in agent.run(user, chat_id, body.content):
                await queue.put(ev)
        except Exception as e:  # noqa: BLE001
            await queue.put({"type": "error", "error": f"Something went wrong: {e}"})
        finally:
            await queue.put({"type": "done"})
            _active.pop(chat_id, None)

    _active[chat_id] = asyncio.create_task(worker())

    async def stream():
        while True:
            ev = await queue.get()
            yield agent.sse(ev)
            if ev["type"] == "done":
                break

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ memory & files

MEMORY_FILES = {"context": workspace.CONTEXT_FILE, "memory": workspace.MEMORY_FILE}


@router.get("/memory")
def get_memory(user: User = Depends(current_user)) -> dict:
    return {key: workspace.read_file(user.id, fname) for key, fname in MEMORY_FILES.items()}


class FileIn(BaseModel):
    content: str


@router.put("/memory/{key}")
def put_memory(key: str, body: FileIn, user: User = Depends(current_user)) -> dict:
    if key not in MEMORY_FILES:
        raise HTTPException(404, "Unknown file")
    try:
        workspace.write_file(user.id, MEMORY_FILES[key], body.content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True}


@router.get("/files")
def list_files(user: User = Depends(current_user)) -> list[dict]:
    return workspace.list_files(user.id)


MAX_UPLOAD = 25 * 1024 * 1024


@router.post("/files")
async def upload_file(
    file: UploadFile = File(...), folder: str = Form(""), user: User = Depends(current_user)
) -> dict:
    name = (file.filename or "upload").replace("\\", "/").split("/")[-1]
    rel = f"{folder.strip('/')}/{name}" if folder.strip("/") else name
    try:
        target = workspace.resolve(user.id, rel)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is too large (max 25 MB)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": rel, "size": len(data)}


@router.get("/files/content")
def file_content(path: str, user: User = Depends(current_user)) -> dict:
    try:
        target = workspace.resolve(user.id, path)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not target.is_file():
        raise HTTPException(404, "File not found")
    return {"path": path, "content": workspace.read_file(user.id, path)}


# ------------------------------------------------------------------ settings & sandbox


class SettingsIn(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str | None = None  # None = keep, "" = clear


@router.get("/settings")
def get_settings(user: User = Depends(current_user)) -> dict:
    s = config.settings
    return {
        "provider": user.llm_provider,
        "model": user.llm_model,
        "base_url": user.llm_base_url,
        "has_api_key": bool(user.llm_api_key),
        "defaults": {
            "provider": s.llm_provider,
            "model": s.default_model(user.llm_provider or s.llm_provider),
            "has_api_key": bool(s.llm_api_key),
        },
    }


@router.put("/settings")
def put_settings(body: SettingsIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    if body.provider not in ("", "anthropic", "openai"):
        raise HTTPException(400, "Provider must be anthropic or openai")
    u = db.get(User, user.id)
    u.llm_provider, u.llm_model, u.llm_base_url = body.provider, body.model.strip(), body.base_url.strip()
    if body.api_key is not None:
        u.llm_api_key = body.api_key.strip()
    db.flush()
    return get_settings(u)


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
    body: McpConfigIn, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict:
    try:
        parse_config(body.config)
    except ConfigError as e:
        raise HTTPException(400, str(e)) from e
    db.get(User, user.id).mcp_config = body.config
    return {"ok": True}


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
    schedule: str
    timezone: str = "UTC"
    enabled: bool = True


class TaskPatch(BaseModel):
    name: str | None = None
    prompt: str | None = None
    schedule: str | None = None
    timezone: str | None = None
    enabled: bool | None = None


def _task_dict(t: Task) -> dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "prompt": t.prompt,
        "schedule": t.schedule,
        "timezone": t.timezone,
        "enabled": t.enabled,
        "next_run_at": _iso(t.next_run_at),
        "last_run_at": _iso(t.last_run_at),
        "last_status": t.last_status,
        "last_chat_id": t.last_chat_id,
    }


def _own_task(db: Session, user: User, task_id: int) -> Task:
    t = db.get(Task, task_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "Task not found")
    return t


@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), user: User = Depends(current_user)) -> list[dict]:
    return [_task_dict(t) for t in db.query(Task).filter_by(user_id=user.id).order_by(Task.id).all()]


@router.post("/tasks")
def create_task(body: TaskIn, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    try:
        scheduler.validate(body.schedule, body.timezone)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    t = Task(user_id=user.id, **body.model_dump())
    t.next_run_at = scheduler.next_run(t.schedule, t.timezone) if t.enabled else None
    db.add(t)
    db.flush()
    return _task_dict(t)


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int, body: TaskPatch, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict:
    t = _own_task(db, user, task_id)
    data = body.model_dump(exclude_none=True)
    schedule, tz = data.get("schedule", t.schedule), data.get("timezone", t.timezone)
    try:
        scheduler.validate(schedule, tz)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    for k, v in data.items():
        setattr(t, k, v)
    t.next_run_at = scheduler.next_run(t.schedule, t.timezone, utcnow()) if t.enabled else None
    return _task_dict(t)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    db.delete(_own_task(db, user, task_id))
    return {"ok": True}


@router.post("/tasks/{task_id}/run")
async def run_task_now(
    task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)
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
