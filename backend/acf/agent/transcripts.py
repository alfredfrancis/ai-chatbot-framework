"""Past chats as plain Markdown in the workspace, so the agent can search them with grep.

After every run the chat is written to .acf/chats/<chat id>.md: its title, then each user message and
answer (tool calls as one line each; tool output is left out). Deleting the chat deletes the file. This
is "session search" with a file and the existing tools instead of a search tool.
"""

from __future__ import annotations

import logging

from acf import workspace
from acf.db import Chat, Message, session_scope

log = logging.getLogger("acf.transcripts")
DIR = ".acf/chats"
MAX_CHARS = 400_000  # per chat file; the oldest messages are dropped first
MAX_MESSAGE = 8_000  # per message


def path(chat_id: int) -> str:
    return f"{DIR}/{chat_id}.md"


def render(chat_id: int) -> str | None:
    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        if chat is None:
            return None
        title, created = chat.title, chat.created_at
        rows = [
            (m.role, m.content or "", [t.get("name", "") for t in m.tool_calls or []], m.created_at, m.background)
            for m in db.query(Message).filter_by(chat_id=chat_id).order_by(Message.id)
        ]
    parts: list[str] = []
    for role, content, calls, at, background in rows:
        stamp = at.strftime("%Y-%m-%d %H:%M")
        text = content.strip()[:MAX_MESSAGE]
        if role == "user" and not background:
            parts.append(f"## User ({stamp})\n{text}")
        elif role == "assistant" and (text or calls):
            used = f"\n(used: {', '.join(calls)})" if calls else ""
            parts.append(f"## Assistant ({stamp})\n{text}{used}".rstrip())
    head = f"# {title}\nChat {chat_id}, started {created.strftime('%Y-%m-%d %H:%M')} UTC\n"
    body = "\n\n".join(parts)
    if len(body) > MAX_CHARS:
        body = "… (earlier messages left out)\n\n" + body[-MAX_CHARS:]
    return f"{head}\n{body}\n"


def save(user_id: int, chat_id: int) -> None:
    try:
        text = render(chat_id)
        if text is not None:
            workspace.write_file(user_id, path(chat_id), text)
    except Exception:  # noqa: BLE001 - a transcript is a convenience; never fail a run over it
        log.exception("could not save the transcript of chat %s", chat_id)


def delete(user_id: int, chat_id: int) -> None:
    target = workspace.resolve(user_id, path(chat_id))
    target.unlink(missing_ok=True)
