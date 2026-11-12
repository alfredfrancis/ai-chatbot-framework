"""The schema comes from Alembic migrations (acf/migrations); these keep them honest."""

from importlib.resources import files

import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from acf import db


def _config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(files("acf") / "migrations"))
    return cfg


def test_migrations_build_the_schema_the_models_describe():
    """A model change without a migration fails here (on SQLite and, in CI, PostgreSQL)."""
    with db._engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(ctx, db.Base.metadata) == []
        head = ScriptDirectory.from_config(_config()).get_current_head()
        assert ctx.get_current_revision() == head


def test_a_database_from_before_migrations_is_adopted_and_upgraded(tmp_path):
    """Older versions made the tables with create_all and no alembic_version: mark it as the baseline,
    then upgrade, keeping the data."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    # As the app connects: with foreign keys on, a migration that copies and drops a table deletes the rows
    # that reference it.
    sa.event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    cfg = _config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, db.BASELINE_REVISION)
        conn.execute(sa.text("DROP TABLE alembic_version"))
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, name, password_hash, created_at, llm_provider, "
                "llm_model, llm_base_url, llm_api_key, mcp_config) "
                "VALUES (1, 'a@b.c', '', 'x', '2026-01-01', '', '', '', '', '')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO tasks (user_id, name, prompt, schedule, timezone, enabled, last_status, "
                "created_at) VALUES (1, 'Old', 'p', '0 9 * * *', 'UTC', 1, '', '2026-01-01')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO chats (id, user_id, title, created_at, updated_at) "
                "VALUES (1, 1, 'Old chat', '2026-01-01', '2026-01-01')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO messages (chat_id, role, content, is_error, created_at) "
                "VALUES (1, 'user', 'hello', 0, '2026-01-01')"
            )
        )

    db.migrate(engine)

    with engine.connect() as conn:
        assert "run_at" in {c["name"] for c in sa.inspect(conn).get_columns("tasks")}
        assert conn.execute(sa.text("SELECT name, run_at FROM tasks")).all() == [("Old", None)]
        assert conn.execute(sa.text("SELECT title, parent_id FROM chats")).all() == [("Old chat", None)]
        assert conn.execute(sa.text("SELECT content FROM messages")).all() == [("hello",)]
        assert MigrationContext.configure(conn).get_current_revision() == "0005"
    db.migrate(engine)  # running again changes nothing
    engine.dispose()


def test_a_users_key_and_address_move_to_their_provider(tmp_path):
    """0005: the one key and address a user had become their settings for the provider they had chosen."""
    import json

    from acf import secrets_box

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'keys.db'}")
    cfg = _config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0004")
        for uid, provider, url, key in [
            (1, "openai", "http://ollama:11434/v1", "sk-old"),
            (2, "", "", "sk-server"),
            (3, "", "", ""),
        ]:
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, email, name, password_hash, created_at, llm_provider, llm_model, "
                    "llm_base_url, llm_api_key, mcp_config) "
                    "VALUES (:id, :e, '', 'x', '2026-01-01', :p, 'm', :u, :k, '')"
                ),
                {"id": uid, "e": f"{uid}@b.c", "p": provider, "u": url, "k": secrets_box.encrypt(key)},
            )
        command.upgrade(cfg, "0005")
        rows = dict(conn.execute(sa.text("SELECT id, llm_connections FROM users")).all())
        assert all(v == "{}" or v.startswith(secrets_box.PREFIX) for v in rows.values())
        got = {uid: json.loads(secrets_box.decrypt(v)) for uid, v in rows.items()}
        assert got[1] == {"openai": {"api_key": "sk-old", "base_url": "http://ollama:11434/v1"}}
        assert got[2] == {"anthropic": {"api_key": "sk-server", "base_url": ""}}
        assert got[3] == {}
        command.downgrade(cfg, "0004")
        back = conn.execute(sa.text("SELECT llm_base_url, llm_api_key FROM users WHERE id = 1")).one()
        assert back[0] == "http://ollama:11434/v1" and secrets_box.decrypt(back[1]) == "sk-old"
    engine.dispose()
