"""Database models (SQLite by default) and session helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from acf import config, secrets_box


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EncryptedText(TypeDecorator):
    """Text encrypted at rest (acf.secrets_box); code reads and writes plain strings."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return secrets_box.encrypt(value)

    def process_result_value(self, value, dialect):
        return secrets_box.decrypt(value)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Per-user model settings (see acf.models); empty values fall back to server defaults.
    # The default model: provider + model id (empty model = the server's default model).
    llm_provider: Mapped[str] = mapped_column(String(64), default="")
    llm_model: Mapped[str] = mapped_column(Text, default="")
    llm_effort: Mapped[str] = mapped_column(String(16), default="")
    # JSON {provider: {"api_key": …, "base_url": …}}: the user's key and address for each provider.
    llm_connections: Mapped[str] = mapped_column(EncryptedText, default="{}")
    # {model key: {"enabled": bool, "context_window": int, "custom": bool}}: the user's model list.
    llm_models: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mcp_config: Mapped[str] = mapped_column(EncryptedText, default='{\n  "mcpServers": {}\n}\n')


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class AcpToken(Base):
    """The optional access token external ACP clients use (one per user, stored hashed)."""

    __tablename__ = "acp_tokens"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hint: Mapped[str] = mapped_column(String(16), default="")  # last characters, shown in Settings
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Project(Base):
    """A named piece of ongoing work: instructions for the agent and, optionally, a folder in the workspace.
    Chats and tasks belong to it through their project_id (see acf.projects)."""

    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(500), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    folder: Mapped[str] = mapped_column(String(500), default="")  # relative to the workspace; "" = none
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Chat(Base):
    __tablename__ = "chats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New chat")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    # The project this chat belongs to. Like parent_id it has no foreign key; deleting a project clears it.
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # A sub-agent's session: the chat whose run started it. Kept out of chat lists, read-only, deleted with it
    # (by the API: no foreign key, as adding one to an existing SQLite table means copying the table).
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # The model ("provider:model") and effort this chat runs on; "" = the user's default.
    model: Mapped[str] = mapped_column(String(300), default="")
    effort: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    """One message in provider-neutral form.

    role: user | assistant | tool | summary | note (a background review's record; not sent to the model)
    A background command's output is a user-role note (the model reads it as a message) that carries the
    job id in raw.background and the tool call that started it in tool_call_id.
    assistant messages may carry tool_calls [{id, name, arguments}] and the provider's raw content
    blocks (kept verbatim so they can be replayed unchanged on the next request).
    """

    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user | assistant | tool | summary | note
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False)
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    @property
    def background(self) -> str | None:
        """Background job id: on the tool result that started it, and on the user-role note with its output."""
        return (self.raw or {}).get("background") if self.role in ("tool", "user") else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls or [],
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "is_error": self.is_error,
            "duration_ms": (self.raw or {}).get("duration_ms") if self.role == "tool" or self.background else None,
            "background": self.background,
            "agent": (self.raw or {}).get("agent") if self.role == "tool" else None,
            "created_at": self.created_at.isoformat() + "Z",
        }


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    schedule: Mapped[str] = mapped_column(String(100))  # 5-field cron expression; "" for a one-off task
    run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # one-off: when, naive UTC
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(20), default="")  # ok | error | running
    last_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # its runs are chats in it
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OAuthToken(Base):
    """OAuth state for one (user, MCP server) pair."""

    __tablename__ = "oauth_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    server_name: Mapped[str] = mapped_column(String(200))
    server_url: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")  # authorization server metadata
    client_json: Mapped[str] = mapped_column(EncryptedText, default="{}")  # registered client info
    tokens_json: Mapped[str] = mapped_column(EncryptedText, default="{}")
    pending_state: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    pending_verifier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    def get(self, attr: str) -> dict[str, Any]:
        return json.loads(getattr(self, attr) or "{}")

    def put(self, attr: str, value: dict[str, Any]) -> None:
        setattr(self, attr, json.dumps(value))


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def normalize_url(url: str) -> str:
    """Accept plain postgres:// / postgresql:// URLs and use the psycopg 3 driver for them."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


BASELINE_REVISION = "0001"  # the schema as `create_all` made it before migrations existed


def migrate(engine=None) -> None:
    """Bring the schema up to date with the migrations in acf/migrations (Alembic). A database made by an
    older version, before migrations existed, is marked as the baseline first and then upgraded."""
    from importlib.resources import files

    from alembic import command
    from alembic.config import Config

    engine = engine or _engine
    assert engine is not None
    cfg = Config()
    cfg.set_main_option("script_location", str(files("acf") / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "users" in tables and "alembic_version" not in tables:
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")


def init_db() -> None:
    """Connect and migrate the schema. PostgreSQL in Docker deployments; SQLite for quick local runs."""
    global _engine, _SessionLocal
    url = normalize_url(config.settings.db_url)
    kwargs: dict[str, Any] = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    else:
        kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine, "connect")
        def _pragma(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    migrate(_engine)
    _SessionLocal = sessionmaker(_engine, expire_on_commit=False)
    encrypt_existing()


# Columns holding secrets: (table, column) pairs typed EncryptedText.
SECRET_COLUMNS = [
    (table.name, col.name)
    for table in Base.metadata.sorted_tables
    for col in table.columns
    if isinstance(col.type, EncryptedText)
]


def encrypt_existing() -> int:
    """Encrypt secrets stored in plain text by earlier versions, and refuse to start with the wrong key.
    Returns the number of values encrypted."""
    assert _engine is not None
    done = 0
    with _engine.begin() as conn:
        for table, col in SECRET_COLUMNS:
            rows = conn.execute(text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"))
            checked = False
            for row_id, value in rows.fetchall():
                if value.startswith(secrets_box.PREFIX):
                    if not checked:
                        secrets_box.decrypt(value)  # raises SecretKeyError for the wrong key
                        checked = True
                    continue
                conn.execute(
                    text(f"UPDATE {table} SET {col} = :v WHERE id = :id"),
                    {"v": secrets_box.encrypt(value), "id": row_id},
                )
                done += 1
    return done


@contextmanager
def session_scope() -> Iterator[Session]:
    assert _SessionLocal is not None, "init_db() not called"
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except BaseException:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    """Request DB session. Use as `Depends(get_db, scope="function")` so the commit happens before the
    response is sent: with the default scope a client could act on the reply before its writes land."""
    with session_scope() as s:
        yield s
