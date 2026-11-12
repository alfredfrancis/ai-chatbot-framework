"""Secrets are encrypted at rest in the database."""

import json

import pytest
from sqlalchemy import text

from acf import config, db, secrets_box
from acf.db import OAuthToken, User


def raw(table: str, col: str, row_id: int) -> str:
    with db._engine.connect() as conn:
        return conn.execute(text(f"SELECT {col} FROM {table} WHERE id = :id"), {"id": row_id}).scalar_one()


async def test_api_key_and_mcp_config_are_encrypted(client, user):
    await client.put("/api/settings/providers/anthropic", json={"api_key": "sk-very-secret"})
    cfg = {"mcpServers": {"crm": {"url": "https://crm.example/mcp", "headers": {"Authorization": "Bearer tok-123"}}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})

    stored_key, stored_cfg = raw("users", "llm_connections", user["id"]), raw("users", "mcp_config", user["id"])
    assert stored_key.startswith(secrets_box.PREFIX) and "sk-very-secret" not in stored_key
    assert stored_cfg.startswith(secrets_box.PREFIX) and "tok-123" not in stored_cfg
    # the app still reads plain values
    providers = (await client.get("/api/settings")).json()["providers"]
    assert next(p for p in providers if p["id"] == "anthropic")["has_api_key"]
    assert json.loads((await client.get("/api/mcp/config")).json()["config"]) == cfg


async def test_oauth_tokens_are_encrypted(client, user):
    with db.session_scope() as s:
        row = OAuthToken(user_id=user["id"], server_name="x", server_url="https://x.example")
        row.put("tokens_json", {"access_token": "at-secret", "refresh_token": "rt-secret"})
        row.put("client_json", {"client_id": "c", "client_secret": "cs-secret"})
        s.add(row)
        s.flush()
        row_id = row.id
    for col in ("tokens_json", "client_json"):
        stored = raw("oauth_tokens", col, row_id)
        assert stored.startswith(secrets_box.PREFIX) and "secret" not in stored
    with db.session_scope() as s:
        assert s.get(OAuthToken, row_id).get("tokens_json")["access_token"] == "at-secret"


async def test_plain_values_from_earlier_versions_are_encrypted_at_startup(client, user):
    with db._engine.begin() as conn:
        conn.execute(text("UPDATE users SET mcp_config = 'sk-legacy' WHERE id = :id"), {"id": user["id"]})
    with db.session_scope() as s:  # still readable before the migration
        assert s.get(User, user["id"]).mcp_config == "sk-legacy"
    assert db.encrypt_existing() >= 1
    assert raw("users", "mcp_config", user["id"]).startswith(secrets_box.PREFIX)
    with db.session_scope() as s:
        assert s.get(User, user["id"]).mcp_config == "sk-legacy"
    assert db.encrypt_existing() == 0  # nothing left to do


async def test_wrong_key_refuses_to_start(client, user, monkeypatch):
    await client.put("/api/settings/providers/anthropic", json={"api_key": "sk-very-secret"})
    monkeypatch.setattr(config.settings, "secret_key", "another-key-that-is-long-enough-for-the-check")
    with pytest.raises(secrets_box.SecretKeyError):
        db.encrypt_existing()


def test_short_secret_key_is_rejected(monkeypatch):
    monkeypatch.setenv("ACF_SECRET_KEY", "short")
    with pytest.raises(ValueError, match="ACF_SECRET_KEY"):
        config.Settings()


def test_round_trip_and_nonce():
    a, b = secrets_box.encrypt("hello"), secrets_box.encrypt("hello")
    assert a != b and secrets_box.decrypt(a) == secrets_box.decrypt(b) == "hello"
    assert secrets_box.encrypt("") == "" and secrets_box.decrypt(None) is None
