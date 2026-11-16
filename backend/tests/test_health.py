"""/api/health says the process is alive; /api/health/ready says it should get traffic."""

import time

from acf import bus, db


async def test_live_answers_without_touching_the_database(client, monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: (_ for _ in ()).throw(RuntimeError("db is down")))
    r = await client.get("/api/health")
    assert r.status_code == 200 and r.json()["ok"] is True


async def test_ready_when_the_database_answers(client):
    r = await client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {"db": "ok", "bus": "ok"}


async def test_ready_needs_no_sign_in_and_reveals_nothing_more_than_live(client):
    r = await client.get("/api/health/ready")
    assert "version" not in r.text and "host" not in r.text


async def test_not_ready_when_the_database_is_down(client, monkeypatch):
    def down():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(db, "ping", down)
    r = await client.get("/api/health/ready")
    assert r.status_code == 503
    assert r.json() == {"db": "error", "bus": "ok"}
    assert (await client.get("/api/health")).status_code == 200


async def test_not_ready_when_the_database_hangs_past_the_timeout(client, monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: time.sleep(4))
    start = time.monotonic()
    r = await client.get("/api/health/ready")
    assert r.status_code == 503 and r.json()["db"] == "error"
    assert time.monotonic() - start < 3


async def test_not_ready_when_redis_is_down(client):
    bus.use(bus.RedisBus("redis://127.0.0.1:1/0"))  # nothing listens there
    try:
        r = await client.get("/api/health/ready")
    finally:
        bus.use(None)
    assert r.status_code == 503
    assert r.json() == {"db": "ok", "bus": "error"}
    assert (await client.get("/api/health")).status_code == 200


async def test_ready_with_redis(client, redis_url):
    shared = bus.RedisBus(redis_url)
    bus.use(shared)
    try:
        assert (await client.get("/api/health/ready")).json() == {"db": "ok", "bus": "ok"}
    finally:
        bus.use(None)
        await shared.close()
