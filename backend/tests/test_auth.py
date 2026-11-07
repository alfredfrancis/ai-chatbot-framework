import time

import pytest


async def test_signup_login_logout(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401

    r = await client.post("/api/auth/signup", json={"email": "Ana@Example.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "ana@example.com"
    assert (await client.get("/api/auth/me")).status_code == 200

    dup = await client.post("/api/auth/signup", json={"email": "ana@example.com", "password": "password123"})
    assert dup.status_code == 409

    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401

    bad = await client.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope-nope"})
    assert bad.status_code == 401
    ok = await client.post("/api/auth/login", json={"email": "ana@example.com", "password": "password123"})
    assert ok.status_code == 200
    assert (await client.get("/api/auth/me")).json()["user"]["email"] == "ana@example.com"


async def test_short_password_rejected(client):
    r = await client.post("/api/auth/signup", json={"email": "x@example.com", "password": "short"})
    assert r.status_code == 422


async def test_users_are_isolated(client, user):
    chat = (await client.post("/api/chats", json={})).json()
    await client.post("/api/auth/logout")
    await client.post("/api/auth/signup", json={"email": "other@example.com", "password": "password123"})
    assert (await client.get(f"/api/chats/{chat['id']}")).status_code == 404
    assert (await client.get("/api/chats")).json() == []


@pytest.fixture
def env(monkeypatch):
    """Set ACF_* variables for one test; settings are re-read and restored afterwards."""
    from acf import config

    def set_env(**values: str) -> None:
        for k, v in values.items():
            monkeypatch.setenv(f"ACF_{k}", v)
        config.reload_settings()

    yield set_env
    monkeypatch.undo()
    config.reload_settings()


def test_signup_default_follows_admin(env):
    from acf import config

    env()
    assert config.settings.allow_signup is True
    env(ADMIN_EMAIL="boss@example.com", ADMIN_PASSWORD="password123")
    assert config.settings.allow_signup is False
    env(ALLOW_SIGNUP="true")
    assert config.settings.allow_signup is True


def test_admin_env_must_be_complete(env):
    with pytest.raises(ValueError, match="both"):
        env(ADMIN_EMAIL="boss@example.com")
    with pytest.raises(ValueError, match="8 characters"):
        env(ADMIN_PASSWORD="short")


async def test_admin_account_from_env(client, env):
    from acf import auth, db, skills

    email = f"boss-{time.time_ns()}@example.com"
    env(ADMIN_EMAIL=email.upper(), ADMIN_PASSWORD="first password", ADMIN_NAME="Boss")
    with db.session_scope() as s:
        user_id = auth.ensure_admin(s).id
    assert (skills.skills_root(user_id) / "skill-creator" / "SKILL.md").exists()

    r = await client.post("/api/auth/login", json={"email": email, "password": "first password"})
    assert r.status_code == 200
    assert r.json()["user"] == {"id": user_id, "email": email, "name": "Boss"}

    # Signup is closed now that the main account exists.
    assert (await client.get("/api/auth/config")).json() == {"signup_allowed": False, "has_users": True}
    r = await client.post("/api/auth/signup", json={"email": "x@example.com", "password": "password123"})
    assert r.status_code == 403

    # Changing the password in the environment replaces it and signs old sessions out.
    env(ADMIN_PASSWORD="second password")
    with db.session_scope() as s:
        assert auth.ensure_admin(s).id == user_id
    assert (await client.get("/api/auth/me")).status_code == 401
    bad = await client.post("/api/auth/login", json={"email": email, "password": "first password"})
    assert bad.status_code == 401
    ok = await client.post("/api/auth/login", json={"email": email, "password": "second password"})
    assert ok.status_code == 200
