"""Chat titles: after a chat's first reply, the model names it in a few words.

Until then a chat is named by its first message (`workspace.message_title`), which is often long or a pasted
paragraph. Once the first run ends, a short call (the first message and the reply, no tools) asks the chat's
model for a title of a few words. It replaces the title only if that is still the one taken from the first
message, so a title the user, an app or a task set is kept. Clients hear of it as a `title` chat event.
ACF_AUTO_TITLES=false turns it off.
"""

from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from acf import config, workspace
from acf.db import Chat, Message, User, session_scope
from acf.llm import LLMConfig, make_model
from acf.llm import text_of as _text_of

log = logging.getLogger("acf.titles")
MAX_TITLE = 80
EXCERPT = 1500  # characters of the first message and of the reply the model sees

PROMPT = """[Title] Name this chat in 2 to 6 words, as a person would name a document: say what it is about, in \
the language of the user's message, sentence case, no quotes, no full stop. Reply with the title only."""

_active: dict[int, asyncio.Task] = {}


def clean(text: str) -> str:
    """A model's reply as a title: its first line, without quotes, a "Title:" label or a full stop."""
    line = (text.strip().splitlines() or [""])[0].strip()
    if line.lower().startswith("title:"):
        line = line[6:].strip()
    line = line.strip("\"'“”‘’`*# ").rstrip(".").strip()
    return line[:MAX_TITLE].strip()


def _first_exchange(chat_id: int) -> tuple[str, str] | None:
    """The first user message and the reply to it, if the chat is still named by that message."""
    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        if chat is None or chat.parent_id is not None:
            return None
        rows = db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.id).all()
        users = [m for m in rows if m.role == "user" and not m.background]
        if len(users) != 1 or chat.title != workspace.message_title(users[0].content or ""):
            return None
        reply = next((m.content for m in reversed(rows) if m.role == "assistant" and m.content), "")
        return users[0].content or "", reply or ""


def maybe_start(user: User, chat_id: int) -> asyncio.Task | None:
    """Name the chat in the background if it is new and still named by its first message."""
    if not config.settings.auto_titles or chat_id in _active:
        return None
    exchange = _first_exchange(chat_id)
    if exchange is None:
        return None
    task = asyncio.create_task(_name(user, chat_id, *exchange))
    _active[chat_id] = task
    task.add_done_callback(lambda _: _active.pop(chat_id, None))
    return task


async def wait(chat_id: int) -> None:
    """Wait for the chat's title, if one is being made (tests)."""
    task = _active.get(chat_id)
    if task:
        await asyncio.shield(task)


async def _name(user: User, chat_id: int, first: str, reply: str) -> None:
    from acf.agent import loop  # loop starts this

    try:
        model = make_model(LLMConfig.for_chat(user, chat_id))
        messages = [
            SystemMessage("You name chats."),
            HumanMessage(f"{PROMPT}\n\nUser:\n{first[:EXCERPT]}\n\nAssistant:\n{reply[:EXCERPT]}"),
        ]
        title = clean(_text_of(await model.ainvoke(messages)))
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001 - a title is a nicety; the first message stays the name
        log.exception("could not name chat %s", chat_id)
        return
    if not title:
        return
    with session_scope() as db:
        chat = db.get(Chat, chat_id)
        first_user = (
            db.query(Message).filter(Message.chat_id == chat_id, Message.role == "user").order_by(Message.id).first()
        )
        if chat is None or first_user is None or chat.title != workspace.message_title(first_user.content or ""):
            return  # renamed meanwhile
        chat.title = title
    loop._broadcast(chat_id, {"type": "title", "title": title})
