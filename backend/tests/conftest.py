from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import httpx
import pytest
import sqlalchemy
import uvicorn

FAKES = Path(__file__).parent / "fakes"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(app, port: int) -> uvicorn.Server:
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            return server
        time.sleep(0.05)
    raise RuntimeError("server did not start")


@pytest.fixture(scope="session")
def fake_llm_url() -> str:
    from tests.fakes.fake_llm import app

    port = free_port()
    serve(app, port)
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="session")
def oauth_mcp_url() -> str:
    from tests.fakes.oauth_mcp import app

    port = free_port()
    serve(app, port)
    return f"http://127.0.0.1:{port}"


@pytest.fixture(scope="session", autouse=True)
def acf_env(fake_llm_url):
    data = tempfile.mkdtemp(prefix="acf-test-")
    os.environ.update(
        {
            "ACF_DATA_DIR": data,
            "ACF_SANDBOX": "local",
            "ACF_LLM_PROVIDER": "anthropic",
            "ACF_LLM_BASE_URL": fake_llm_url,
            "ACF_LLM_API_KEY": "test-key",
            "ACF_SCHEDULER": "false",
        }
    )
    # ACF_TEST_DB_URL runs the suite against another database, e.g. PostgreSQL in CI.
    if os.environ.get("ACF_TEST_DB_URL"):
        os.environ["ACF_DB_URL"] = os.environ["ACF_TEST_DB_URL"]
    from acf import config, db

    config.reload_settings()
    db.init_db()
    if not config.settings.db_url.startswith("sqlite"):
        # Start every run from an empty schema, built by the migrations.
        old = sqlalchemy.MetaData()
        old.reflect(db._engine)
        old.drop_all(db._engine)
        db.migrate()
    yield data
    shutil.rmtree(data, ignore_errors=True)


@pytest.fixture
async def client():
    from acf.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120) as c:
        yield c


_counter = iter(range(10**6))


@pytest.fixture
async def user(client):
    email = f"user{next(_counter)}-{time.time_ns()}@example.com"
    r = await client.post("/api/auth/signup", json={"email": email, "password": "correct horse", "name": "Maya"})
    assert r.status_code == 200, r.text
    return r.json()["user"]


async def use_model(client, key: str, base_url: str | None = None, api_key: str | None = None):
    """Make `key` ("provider:model") the user's default model, with the provider's address and key if given."""
    provider, _, model = key.partition(":")
    if base_url is not None or api_key is not None:
        r = await client.put(
            f"/api/settings/providers/{provider}", json={"base_url": base_url or "", "api_key": api_key}
        )
        assert r.status_code == 200, r.text
    r = await client.post("/api/settings/models", json={"provider": provider, "id": model})
    assert r.status_code == 200, r.text
    r = await client.put("/api/settings", json={"model": key})
    assert r.status_code == 200, r.text
    return r.json()


async def prompt(acp, chat_id: int | str, text: str):
    """Send a prompt over an open ACP connection; returns the Turn it produced."""
    from tests.acp_client import RpcError, Turn

    sid = str(chat_id)
    start = len(acp.notifications)
    stop_reason = error = None
    try:
        stop_reason = (
            await acp.request("session/prompt", {"sessionId": sid, "prompt": [{"type": "text", "text": text}]})
        )["stopReason"]
    except RpcError as e:
        error = e.message
    mine = [n for n in acp.notifications[start:] if n.get("params", {}).get("sessionId") == sid]
    updates = [n["params"]["update"] for n in mine if n["method"] == "session/update"]
    notices = [n["params"]["text"] for n in mine if n["method"] == "_acf/notice"]
    return Turn(updates, notices, stop_reason, error)


async def send(client, chat_id: int, text: str):
    """Send a chat message over ACP (as the signed-in user) and wait for the run to finish."""
    from tests.acp_client import acp_connect

    async with acp_connect(client) as acp:
        return await prompt(acp, chat_id, text)


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session")
def redis_url():
    """A Redis for the bus: ACF_TEST_REDIS_URL, or a throwaway redis-server. Skips without either."""
    if os.environ.get("ACF_TEST_REDIS_URL"):
        yield os.environ["ACF_TEST_REDIS_URL"]
        return
    exe = shutil.which("redis-server")
    if not exe:
        pytest.skip("needs redis-server or ACF_TEST_REDIS_URL")
    port = free_port()
    proc = subprocess.Popen(
        [exe, "--port", str(port), "--bind", "127.0.0.1", "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"redis://127.0.0.1:{port}/0"
    for _ in range(100):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    yield url
    proc.terminate()
    proc.wait(10)
