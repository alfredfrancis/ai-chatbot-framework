from __future__ import annotations

import json
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
def harbor_env(fake_llm_url):
    data = tempfile.mkdtemp(prefix="harbor-test-")
    os.environ.update(
        {
            "HARBOR_DATA_DIR": data,
            "HARBOR_SANDBOX": "local",
            "HARBOR_LLM_PROVIDER": "anthropic",
            "HARBOR_LLM_BASE_URL": fake_llm_url,
            "HARBOR_LLM_API_KEY": "test-key",
            "HARBOR_SCHEDULER": "false",
        }
    )
    from harbor import config, db

    config.reload_settings()
    db.init_db()
    yield data
    shutil.rmtree(data, ignore_errors=True)


@pytest.fixture
async def client():
    from harbor.main import create_app

    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=120) as c:
        yield c


_counter = iter(range(10**6))


@pytest.fixture
async def user(client):
    email = f"user{next(_counter)}-{time.time_ns()}@example.com"
    r = await client.post(
        "/api/auth/signup", json={"email": email, "password": "correct horse", "name": "Maya"}
    )
    assert r.status_code == 200, r.text
    return r.json()["user"]


async def send(client, chat_id: int, text: str) -> list[dict]:
    """Send a chat message and collect the SSE events."""
    events = []
    async with client.stream("POST", f"/api/chats/{chat_id}/messages", json={"content": text}) as r:
        assert r.status_code == 200, await r.aread()
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0
