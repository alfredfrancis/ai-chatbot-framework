"""Real Docker sandbox tests. Skipped when no Docker daemon is available."""

import json
import os
import shutil

import pytest

from acf import config, workspace
from acf.sandbox import DockerSandbox
from tests.conftest import FAKES, docker_available, send

pytestmark = [pytest.mark.docker, pytest.mark.skipif(not docker_available(), reason="Docker not available")]

IMAGE = os.environ.get("ACF_TEST_SANDBOX_IMAGE", "python:3.12-alpine")


@pytest.fixture
def docker_sandbox():
    old = (config.settings.sandbox, config.settings.sandbox_image)
    config.settings.sandbox, config.settings.sandbox_image = "docker", IMAGE
    created = []
    yield created
    config.settings.sandbox, config.settings.sandbox_image = old
    import subprocess

    for uid in created:
        subprocess.run(["docker", "rm", "-f", f"{config.settings.sandbox_prefix}-{uid}"], capture_output=True)


async def test_commands_run_in_isolated_container(client, user, docker_sandbox):
    docker_sandbox.append(user["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, "run: hostname && pwd && id -u && echo hi > made-in-sandbox.txt")
    tool = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert "sandbox\n/workspace" in tool["content"], tool
    # the workspace is shared with the host side
    assert (workspace.workspace_dir(user["id"]) / "made-in-sandbox.txt").read_text() == "hi\n"
    status = (await client.get("/api/sandbox")).json()
    assert status["state"] == "running" and status["name"] == f"acf-sbx-{user['id']}"


async def test_one_container_per_user(client, user, docker_sandbox):
    docker_sandbox.append(user["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    await send(client, chat_id, "run: echo private > secret.txt")

    await client.post("/api/auth/logout")
    other = (await client.post("/api/auth/signup", json={"email": "b@sbx.example", "password": "password123"})).json()
    docker_sandbox.append(other["user"]["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, "run: ls /workspace; cat secret.txt")
    tool = next(e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "tool")
    assert "No such file" in tool["content"] and tool["is_error"]


async def test_timeout_kills_command(client, user, docker_sandbox):
    docker_sandbox.append(user["id"])
    sbx = DockerSandbox(user["id"])
    res = await sbx.exec("sleep 30", timeout=2)
    assert res.timed_out


async def test_stdio_mcp_runs_inside_sandbox(client, user, docker_sandbox):
    docker_sandbox.append(user["id"])
    shutil.copy(FAKES / "echo_mcp.py", workspace.workspace_dir(user["id"]) / "echo_mcp.py")
    cfg = {"mcpServers": {"echo": {"command": "python3", "args": ["echo_mcp.py"]}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    events = await send(client, chat_id, 'tool: mcp_call {"server": "echo", "tool": "whereami", "arguments": {}}')
    final = [e["message"] for e in events if e["type"] == "message" and e["message"]["role"] == "assistant"][-1]
    assert final["content"] == "Result: host=sandbox cwd=/workspace"


async def test_stale_container_is_replaced(client, user, docker_sandbox):
    """If the workspace folder is recreated (data wiped, id reused), the old container is replaced."""
    docker_sandbox.append(user["id"])
    sbx = DockerSandbox(user["id"])
    assert (await sbx.exec("echo one")).exit_code == 0
    shutil.rmtree(workspace.user_root(user["id"]))
    res = await sbx.exec("echo two > f.txt && cat f.txt")
    assert res.exit_code == 0 and res.stdout == "two\n", res
    assert (workspace.workspace_dir(user["id"]) / "f.txt").read_text() == "two\n"
