"""The schema comes from Alembic migrations (acf/migrations); these keep them honest."""

import contextlib
import os
import subprocess
import sys
import time
import uuid
from importlib.resources import files
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

from acf import config, db
from tests.conftest import free_port

ACF_MIGRATE = str(Path(sys.executable).parent / "acf-migrate")
BACKEND = Path(__file__).parents[1]


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
        assert conn.execute(sa.text("SELECT model FROM tasks")).all() == [("",)]  # the user's default model
        assert MigrationContext.configure(conn).get_current_revision() == "0006"
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


def test_acf_migrate_refuses_to_run_without_the_key_that_encrypted_the_database(tmp_path, monkeypatch):
    """0005 decrypts and re-encrypts users' keys: without ACF_SECRET_KEY acf-migrate stops with a message
    instead of making a key of its own (a container or Job has no data folder to keep it in)."""
    import json

    from acf import secrets_box

    secret = "migrate-secret-key-that-is-long-enough-0"
    monkeypatch.setattr(config.settings, "secret_key", secret)
    url = f"sqlite:///{tmp_path / 'keys.db'}"
    engine = sa.create_engine(url)
    cfg = _config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0004")
        conn.execute(
            sa.text(
                "INSERT INTO users (id, email, name, password_hash, created_at, llm_provider, llm_model, "
                "llm_base_url, llm_api_key, mcp_config) "
                "VALUES (1, 'a@b.c', '', 'x', '2026-01-01', 'openai', 'm', '', :k, '')"
            ),
            {"k": secrets_box.encrypt("sk-old")},
        )
    data = tmp_path / "data"
    data.mkdir()
    env = {**os.environ, "ACF_DB_URL": url, "ACF_DATA_DIR": str(data)}

    refused = subprocess.run([ACF_MIGRATE], env=env, capture_output=True, text=True, timeout=120)
    assert refused.returncode != 0
    assert "ACF_SECRET_KEY" in refused.stderr and "Traceback" not in refused.stderr, refused.stderr
    assert not (data / "secret.key").exists()
    assert db.schema_revision(engine) == "0004"

    env["ACF_SECRET_KEY"] = secret
    migrated = subprocess.run([ACF_MIGRATE], env=env, capture_output=True, text=True, timeout=120)
    assert migrated.returncode == 0, migrated.stderr
    assert not (data / "secret.key").exists()
    with engine.connect() as conn:
        stored = conn.execute(sa.text("SELECT llm_connections FROM users")).scalar_one()
    engine.dispose()
    assert json.loads(secrets_box.decrypt(stored)) == {"openai": {"api_key": "sk-old", "base_url": ""}}


def _head() -> str:
    return ScriptDirectory.from_config(_config()).get_current_head()


@pytest.fixture
def empty_postgres():
    """A new, empty PostgreSQL database on the test server, dropped afterwards."""
    if config.settings.db_url.startswith("sqlite"):
        pytest.skip("PostgreSQL only (ACF_TEST_DB_URL)")
    server = sa.make_url(db.normalize_url(config.settings.db_url))
    name = f"acf_migrate_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(server, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    yield server.set(database=name)
    with admin.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


def test_acf_migrate_processes_started_together_take_turns(empty_postgres):
    """Pods starting at once without Redis: every run succeeds and the schema is built exactly once."""
    env = {**os.environ, "ACF_DB_URL": empty_postgres.render_as_string(hide_password=False)}
    runs = [
        subprocess.Popen([ACF_MIGRATE], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) for _ in range(5)
    ]
    outputs = [p.communicate(timeout=120)[0].decode() for p in runs]
    assert [p.returncode for p in runs] == [0] * 5, "\n".join(outputs)
    engine = sa.create_engine(empty_postgres)
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all() == [_head()]
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(ctx, db.Base.metadata) == []
    engine.dispose()


def _start_app(env: dict[str, str]) -> tuple[subprocess.Popen, str]:
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "acf.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc, f"http://127.0.0.1:{port}"


def _healthy(proc: subprocess.Popen, url: str) -> bool:
    for _ in range(200):
        with contextlib.suppress(httpx.HTTPError):
            if httpx.get(f"{url}/api/health", timeout=1).status_code == 200:
                return True
        if proc.poll() is not None:
            return False
        time.sleep(0.1)
    return False


def test_app_processes_started_together_without_redis_all_start(empty_postgres):
    """Each migrates on start, encrypts stored secrets and makes the main account, taking turns in PostgreSQL."""
    env = {
        **os.environ,
        "ACF_DB_URL": empty_postgres.render_as_string(hide_password=False),
        "ACF_SECRET_KEY": "test-secret-key-that-is-long-enough-0000",
        "ACF_ADMIN_EMAIL": "owner@example.com",
        "ACF_ADMIN_PASSWORD": "owner password",
        "ACF_FRONTEND_DIST": "/nonexistent",
    }
    apps = [_start_app(env) for _ in range(4)]
    try:
        started = [_healthy(proc, url) for proc, url in apps]
    finally:
        for proc, _ in apps:
            proc.terminate()
    outputs = [proc.communicate(timeout=30)[0].decode() for proc, _ in apps]
    assert started == [True] * 4, "\n".join(outputs)
    engine = sa.create_engine(empty_postgres)
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT email FROM users")).scalars().all() == ["owner@example.com"]
    engine.dispose()


def test_without_migrate_on_start_the_app_refuses_an_old_schema_until_acf_migrate_runs(tmp_path):
    """ACF_MIGRATE_ON_START=false (pods, with acf-migrate as a Job): an old schema stops the app with a message
    naming acf-migrate; after acf-migrate the same app starts."""
    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = sa.create_engine(url)
    cfg = _config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "0005")
    engine.dispose()
    env = {**os.environ, "ACF_DB_URL": url, "ACF_MIGRATE_ON_START": "false", "ACF_FRONTEND_DIST": "/nonexistent"}

    proc, base = _start_app(env)
    try:
        assert not _healthy(proc, base)
        out = proc.communicate(timeout=30)[0].decode()
    finally:
        proc.kill()
    assert proc.returncode != 0
    assert "revision 0005" in out and "acf-migrate" in out, out

    migrated = subprocess.run([ACF_MIGRATE], env=env, capture_output=True, text=True, timeout=120)
    assert migrated.returncode == 0, migrated.stderr
    assert f"Database schema is at revision {_head()}" in migrated.stderr

    proc, base = _start_app(env)
    try:
        assert _healthy(proc, base)
    finally:
        proc.terminate()
        proc.wait(30)
