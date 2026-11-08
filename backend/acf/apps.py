"""Personal apps: small screens the agent (or a skill) makes for the user, shown in the menu.

An app is a folder in the workspace, apps/<id>/:
- app.json: {"title", "description", "order", "files"} - how it shows in the menu, and the files outside
  its folder it may use
- app.oui:  the screen, in OpenUI Lang (https://openui.com). The web app renders it with its own component
  library (frontend/src/openui/library.tsx), so an app is built from design-system components, never HTML.

There is no app backend: the state is the files. The screen's Query()/Mutation() calls and buttons reach
the files, the agent, connected apps and the sandbox through one action API (`run_action`):
- read_file   {path}                     a file of the app: {text}, plus {data} if it is JSON
- update_file {path, content}            write a file in the app's folder (not app.json) or one in `files`
- ask_agent   {prompt, event?}           a message to the agent in the app's own chat (returns at once)
- run         {script, input?}           run apps/<id>/actions/<script>.sh in the sandbox, input as JSON in $1
- mcp         {server, tool, arguments}  call a read-only tool of a connected app; changes go via ask_agent

The format is documented for the agent in the built-in personal-apps skill.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from acf import workspace
from acf.agent import loop as agent
from acf.db import Chat, User, session_scope
from acf.mcp_client import McpHub
from acf.sandbox import get_sandbox

APPS_DIR = "apps"
MAX_APPS = 5
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
SCRIPT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
STATE_FILE = ".acf/apps.json"  # {"<app id>": {"chat_id": n}}
OUTPUT_LIMIT = 20_000
RUN_TIMEOUT = 60

Action = Literal["read_file", "update_file", "ask_agent", "run", "mcp"]
SCREEN = "app.oui"
MAX_SCREEN = 100_000


class AppError(ValueError):
    pass


class NotFound(AppError):
    pass


class Spec(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    description: str = Field("", max_length=200)
    order: int = 100
    files: list[str] = Field(default_factory=list, max_length=20)


@dataclass
class App:
    id: str
    spec: Spec | None
    error: str | None

    @property
    def title(self) -> str:
        return self.spec.title if self.spec else self.id

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.spec.description if self.spec else "",
            "error": self.error,
        }


def _load(user_id: int, app_id: str) -> App:
    rel = f"{APPS_DIR}/{app_id}/app.json"
    try:
        spec = Spec.model_validate(json.loads(workspace.read_file(user_id, rel)))
    except ValueError as e:  # JSON and validation errors
        detail = e.errors(include_url=False)[0] if isinstance(e, ValidationError) else None
        where = ".".join(str(p) for p in detail["loc"]) + ": " + detail["msg"] if detail else str(e)
        return App(app_id, None, f"{rel} is not valid: {where}")
    if not workspace.resolve(user_id, f"{APPS_DIR}/{app_id}/{SCREEN}").is_file():
        return App(app_id, spec, f"{APPS_DIR}/{app_id}/{SCREEN} is missing: write the screen in OpenUI Lang.")
    return App(app_id, spec, None)


def list_apps(user_id: int) -> list[App]:
    """The apps shown in the menu: at most MAX_APPS, by `order` then id."""
    root = workspace.resolve(user_id, APPS_DIR)
    if not root.is_dir():
        return []
    found = [_load(user_id, p.name) for p in root.iterdir() if ID_RE.match(p.name) and (p / "app.json").is_file()]
    found.sort(key=lambda a: (a.spec.order if a.spec else -1, a.id))
    return found[:MAX_APPS]


def get(user_id: int, app_id: str) -> App:
    for app in list_apps(user_id):
        if app.id == app_id:
            return app
    raise NotFound(f"No app {app_id!r}")


def _paths(app: App) -> tuple[str, list[str]]:
    assert app.spec
    return f"{APPS_DIR}/{app.id}/", app.spec.files


def _allowed(user_id: int, app: App, path: str) -> str:
    """The workspace path, if the app may read and write it: its own folder, or a file it lists."""
    try:
        rel = workspace.relative(user_id, path)
    except ValueError as e:
        raise AppError(str(e)) from e
    folder, files = _paths(app)
    listed = set()
    for f in files:
        try:
            listed.add(workspace.relative(user_id, f))
        except ValueError:
            continue
    own = rel.startswith(folder) and rel not in (f"{folder}app.json", f"{folder}{SCREEN}")
    if not own and rel not in listed:
        raise AppError(f"{app.title} can only change files in {folder} and the files listed in its app.json")
    return rel


def _json(text: str) -> Any:
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


def _state(user_id: int) -> dict[str, Any]:
    try:
        data = json.loads(workspace.read_file(user_id, STATE_FILE) or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _chat_id(user_id: int, app_id: str) -> int | None:
    entry = _state(user_id).get(app_id)
    chat_id = entry.get("chat_id") if isinstance(entry, dict) else None
    return chat_id if isinstance(chat_id, int) else None


def detail(user_id: int, app_id: str) -> dict[str, Any]:
    """The app as the UI shows it: its OpenUI Lang source, and whether the agent works on it."""
    app = get(user_id, app_id)
    chat_id = _chat_id(user_id, app_id)
    run = agent.RUNS.get(chat_id) if chat_id else None
    source = workspace.read_file(user_id, f"{APPS_DIR}/{app_id}/{SCREEN}")[:MAX_SCREEN] if app.spec else ""
    return {**app.summary(), "source": source, "chat_id": chat_id, "running": bool(run and not run.done)}


# ------------------------------------------------------------------ actions


def _text(args: dict, key: str, limit: int, required: bool = True) -> str:
    value = args.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise AppError(f"{key} must be {'a non-empty' if required else 'a'} string")
    if len(value) > limit:
        raise AppError(f"{key} is too long (max {limit} characters)")
    return value


def _app_chat(user: User, app: App) -> int:
    """The app's own chat (made on first use), where its messages to the agent go."""
    chat_id = _chat_id(user.id, app.id)
    with session_scope() as db:
        chat = db.get(Chat, chat_id) if chat_id else None
        if chat is None or chat.user_id != user.id:
            chat = Chat(user_id=user.id, title=f"{app.title} app"[:200])
            db.add(chat)
            db.flush()
            state = _state(user.id)
            state[app.id] = {"chat_id": chat.id}
            workspace.write_file(user.id, STATE_FILE, json.dumps(state, indent=2))
        return chat.id


def ask_agent_message(app: App, prompt: str, event: str = "") -> str:
    head = f"[App: {app.title}, {APPS_DIR}/{app.id}/app.json] {event or 'The user pressed a button.'}"
    return f"{head}\n{prompt}"


async def run_action(user: User, app_id: str, action: Action, args: dict[str, Any]) -> dict[str, Any]:
    app = get(user.id, app_id)
    if not app.spec:
        raise AppError(app.error or "This app is not valid")
    if action == "read_file":
        rel = _allowed(user.id, app, _text(args, "path", 300))
        text = workspace.read_file(user.id, rel)
        return {"ok": True, "path": rel, "text": text, "data": _json(text) if rel.endswith(".json") else None}
    if action == "update_file":
        rel = _allowed(user.id, app, _text(args, "path", 300))
        workspace.write_file(user.id, rel, _text(args, "content", workspace.MAX_FILE_BYTES, required=False))
        return {"ok": True, "path": rel}
    if action == "ask_agent":
        message = ask_agent_message(app, _text(args, "prompt", 20_000), _text(args, "event", 2000, required=False))
        chat_id = _app_chat(user, app)
        _, queued = agent.start(user, chat_id, message)
        return {"ok": True, "chat_id": chat_id, "queued": queued}
    if action == "run":
        script = _text(args, "script", 40)
        rel = f"{APPS_DIR}/{app.id}/actions/{script}.sh"
        if not SCRIPT_RE.match(script) or not workspace.resolve(user.id, rel).is_file():
            raise AppError(f"No script {rel}")
        payload = json.dumps(args.get("input", {}))
        result = await get_sandbox(user.id).exec(f"sh {shlex.quote(rel)} {shlex.quote(payload)}", RUN_TIMEOUT)
        if result.exit_code != 0 or result.timed_out:
            raise AppError(f"{rel} failed: {result.as_text()[-2000:]}")
        return {"ok": True, "output": result.stdout[:OUTPUT_LIMIT]}
    # mcp
    server, tool = _text(args, "server", 40), _text(args, "tool", 200)
    arguments = args.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise AppError("arguments must be a JSON object")
    async with McpHub(user.id, user.mcp_config, get_sandbox(user.id)) as hub:
        if hub.lookup(server, tool) is None:
            raise AppError(f"No tool {tool!r} in a connected app named {server!r}")
        if not hub.read_only(server, tool):
            raise AppError(f"{server} · {tool} can change things: send it to the agent with ask_agent instead")
        result = await hub.call(server, tool, arguments)
    if result.is_error:
        raise AppError(result.content[:2000])
    text = result.content[:OUTPUT_LIMIT]
    return {"ok": True, "text": text, "data": _json(text)}
