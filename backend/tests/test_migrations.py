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
        assert MigrationContext.configure(conn).get_current_revision() == "0004"
    db.migrate(engine)  # running again changes nothing
    engine.dispose()
