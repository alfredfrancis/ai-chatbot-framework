"""model settings: a key and address per provider, the user's model list, a model and effort per chat

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12 07:17:45.494787
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import acf.db  # noqa: F401 - autogenerate writes custom column types as acf.db.<Type>
from acf import config, secrets_box

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Plain ALTER TABLE, not batch mode: on SQLite a batch copies and drops the users table, which (with
    # foreign keys on) deletes every row that references it.
    op.add_column("chats", sa.Column("model", sa.String(length=300), nullable=False, server_default=""))
    op.add_column("chats", sa.Column("effort", sa.String(length=16), nullable=False, server_default=""))
    op.add_column("users", sa.Column("llm_effort", sa.String(length=16), nullable=False, server_default=""))
    op.add_column("users", sa.Column("llm_connections", acf.db.EncryptedText(), nullable=False, server_default="{}"))
    op.add_column("users", sa.Column("llm_models", sa.JSON(), nullable=False, server_default="{}"))

    # The one key and address a user had become their settings for the provider they had chosen.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, llm_provider, llm_base_url, llm_api_key FROM users")).all()
    for uid, provider, base_url, api_key in rows:
        key = secrets_box.decrypt(api_key) or ""
        if not key and not base_url:
            continue
        data = {provider or config.settings.llm_provider: {"api_key": key, "base_url": base_url or ""}}
        conn.execute(
            sa.text("UPDATE users SET llm_connections = :c WHERE id = :id"),
            {"c": secrets_box.encrypt(json.dumps(data)), "id": uid},
        )

    op.drop_column("users", "llm_base_url")
    op.drop_column("users", "llm_api_key")


def downgrade() -> None:
    op.add_column("users", sa.Column("llm_api_key", sa.TEXT(), nullable=False, server_default=""))
    op.add_column("users", sa.Column("llm_base_url", sa.TEXT(), nullable=False, server_default=""))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, llm_provider, llm_connections FROM users")).all()
    for uid, provider, stored in rows:
        try:
            data = json.loads(secrets_box.decrypt(stored) or "{}")
        except json.JSONDecodeError:
            continue
        own = data.get(provider or config.settings.llm_provider) or {}
        conn.execute(
            sa.text("UPDATE users SET llm_api_key = :k, llm_base_url = :u WHERE id = :id"),
            {"k": secrets_box.encrypt(own.get("api_key", "")), "u": own.get("base_url", ""), "id": uid},
        )
    for table, column in [
        ("users", "llm_models"),
        ("users", "llm_connections"),
        ("users", "llm_effort"),
        ("chats", "effort"),
        ("chats", "model"),
    ]:
        op.drop_column(table, column)
