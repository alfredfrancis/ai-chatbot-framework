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
