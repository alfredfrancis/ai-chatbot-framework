"""The narrow Docker API proxy, against a real Docker daemon: sandboxes work through it, everything
else is refused. Also checks the sandbox network and user. Skipped when no Docker daemon is available."""

import asyncio
import json
import os
import shutil
import subprocess

import httpx
import pytest

from acf import config, docker_proxy, workspace
from acf.sandbox import DockerSandbox
from tests.conftest import FAKES, docker_available, free_port, send

pytestmark = [pytest.mark.docker, pytest.mark.skipif(not docker_available(), reason="Docker not available")]

IMAGE = os.environ.get("ACF_TEST_SANDBOX_IMAGE", "python:3.12-alpine")
SOCKET = "/var/run/docker.sock"
OTHER = "acf-proxy-test-other"


def docker_direct(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "DOCKER_HOST"}
    return subprocess.run(["docker", *args], capture_output=True, text=True, env=env)


def direct_exec_create(container: str) -> str:
    """Create an exec on the real socket, bypassing the proxy."""
    cmd = ["curl", "-s", "--unix-socket", SOCKET, "-H", "Content-Type: application/json", "-d", '{"Cmd":["id"]}']
    out = subprocess.run([*cmd, f"http://d/containers/{container}/exec"], capture_output=True, text=True).stdout
    return json.loads(out)["Id"]


@pytest.fixture
async def proxied(monkeypatch):
    """Docker sandboxes, with the app reaching Docker only through the proxy."""
    monkeypatch.setattr(config.settings, "sandbox", "docker")
    monkeypatch.setattr(config.settings, "sandbox_image", IMAGE)
    port = free_port()
    server, proxy = await docker_proxy.serve("127.0.0.1", port, SOCKET)
    monkeypatch.setenv("DOCKER_HOST", f"tcp://127.0.0.1:{port}")
    created: list[int] = []
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=30) as api:
        yield created, api
    server.close()
    await proxy.aclose()
    await asyncio.wait_for(server.wait_closed(), 10)
    for uid in created:
        docker_direct("rm", "-f", f"{config.settings.sandbox_prefix}-{uid}")
    docker_direct("rm", "-f", OTHER)


async def test_sandbox_works_through_the_proxy(client, user, proxied):
    created, _ = proxied
    created.append(user["id"])
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    tool = (await send(client, chat_id, "run: hostname && id -u && echo hi > via-proxy.txt")).results[0]
    assert tool["status"] == "completed", tool
    host, uid = tool["text"].split("\n")[:2]
    assert host == "sandbox" and uid == str(os.getuid()) and uid != "0"
    assert (workspace.workspace_dir(user["id"]) / "via-proxy.txt").read_text() == "hi\n"
    # stdio MCP servers use `docker exec -i` (a hijacked, two-way stream)
    shutil.copy(FAKES / "echo_mcp.py", workspace.workspace_dir(user["id"]) / "echo_mcp.py")
    cfg = {"mcpServers": {"echo": {"command": "python3", "args": ["echo_mcp.py"]}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    turn = await send(client, chat_id, 'tool: mcp_call {"server": "echo", "tool": "whereami", "arguments": {}}')
    assert turn.final == "Result: host=sandbox cwd=/workspace"
    # timeouts, status and reset
    sbx = DockerSandbox(user["id"])
    assert (await sbx.exec("sleep 30", timeout=2)).timed_out
    assert (await client.get("/api/sandbox")).json()["state"] == "running"
    await client.post("/api/sandbox/reset")
    assert (await client.get("/api/sandbox")).json()["state"] == "missing"


async def test_sandbox_container_settings(client, user, proxied):
    created, _ = proxied
    created.append(user["id"])
    await DockerSandbox(user["id"]).exec("true")
    name = f"{config.settings.sandbox_prefix}-{user['id']}"
    info = json.loads(docker_direct("container", "inspect", name).stdout)
    hc = info[0]["HostConfig"]
    assert hc["Privileged"] is False and hc["CapDrop"] == ["ALL"] and "no-new-privileges" in hc["SecurityOpt"]
    assert hc["NetworkMode"] == config.settings.sandbox_network
    assert info[0]["Config"]["User"] != "0" and not info[0]["Config"]["User"].startswith("0:")
    net = json.loads(docker_direct("network", "inspect", config.settings.sandbox_network).stdout)[0]
    assert net["Options"]["com.docker.network.bridge.enable_icc"] == "false"
    assert net["Options"]["com.docker.network.bridge.name"] == config.settings.sandbox_bridge


async def test_sandboxes_cannot_reach_each_other(client, proxied):
    created, _ = proxied
    users = []
    for i in range(2):
        email = f"icc{i}-{os.getpid()}@x.example"
        r = await client.post("/api/auth/signup", json={"email": email, "password": "pw123456"})
        users.append(r.json()["user"]["id"])
    created.extend(users)
    a, b = DockerSandbox(users[0]), DockerSandbox(users[1])
    serve = "nohup python3 -m http.server 8000 >/dev/null 2>&1 & sleep 1"
    assert (await a.exec(serve)).exit_code == 0
    await b.exec("true")
    info = json.loads(docker_direct("container", "inspect", a.name).stdout)[0]
    ip = info["NetworkSettings"]["Networks"][config.settings.sandbox_network]["IPAddress"]
    get = f"urllib.request.urlopen('http://{ip}:8000', timeout=3)"
    fetch = f"python3 -c \"import urllib.request; {get}; print('reached')\""
    assert "reached" in (await a.exec(fetch)).stdout  # control: the server is up
    res = await b.exec(fetch)
    assert res.exit_code != 0 and "reached" not in res.stdout


def _create_body(**overrides) -> dict:
    s = config.settings
    body = {
        "Image": IMAGE,
        "User": "1000:1000",
        "Labels": {"acf.sandbox": "1", "acf.user": "4242"},
        "HostConfig": {
            "Binds": [f"{s.sandbox_host_data_dir or s.data_dir}/users/4242/workspace:/workspace"],
            "NetworkMode": s.sandbox_network,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges"],
            "Memory": 1024**3,
            "NanoCpus": 10**9,
            "PidsLimit": 512,
        },
    }
    for key, value in overrides.items():
        if key.startswith("HostConfig."):
            body["HostConfig"][key.split(".", 1)[1]] = value
        else:
            body[key] = value
    return body


async def _create(api, body: dict, name: str | None = None):
    name = name or f"{config.settings.sandbox_prefix}-4242"
    return await api.post(f"/v1.47/containers/create?name={name}", json=body)


@pytest.mark.parametrize(
    "overrides",
    [
        {"HostConfig.Privileged": True},
        {"HostConfig.Binds": ["/:/host"]},
        {"HostConfig.Binds": ["/var/run/docker.sock:/var/run/docker.sock"]},
        {"HostConfig.Mounts": [{"Type": "bind", "Source": "/", "Target": "/host"}]},
        {"HostConfig.CapAdd": ["SYS_ADMIN"]},
        {"HostConfig.CapDrop": []},
        {"HostConfig.SecurityOpt": ["seccomp=unconfined"]},
        {"HostConfig.NetworkMode": "host"},
        {"HostConfig.PidMode": "host"},
        {"HostConfig.Devices": [{"PathOnHost": "/dev/sda", "PathInContainer": "/dev/sda"}]},
        {"HostConfig.PortBindings": {"80/tcp": [{"HostPort": "80"}]}},
        {"HostConfig.Memory": 0},
        {"HostConfig.MaskedPaths": []},
        {"HostConfig.ReadonlyPaths": []},
        {"HostConfig.Runtime": "runc-custom"},
        {"HostConfig.CgroupParent": "/"},
        {"HostConfig.UsernsMode": "host"},
        {"HostConfig.IpcMode": "host"},
        {"HostConfig.VolumesFrom": ["other"]},
        {"User": "0"},
        {"User": "root"},
        {"User": ""},
        {"Image": "alpine:latest"},
        {"Entrypoint": ["/bin/sh"]},
    ],
)
async def test_unsafe_containers_are_refused(proxied, overrides):
    _, api = proxied
    r = await _create(api, _create_body(**overrides))
    assert r.status_code == 403, (overrides, r.text)
    assert "Docker proxy" in r.json()["message"]


async def test_the_bind_must_be_that_users_workspace(proxied):
    _, api = proxied
    other_user = _create_body()
    other_user["HostConfig"]["Binds"] = [other_user["HostConfig"]["Binds"][0].replace("/4242/", "/1/")]
    assert (await _create(api, other_user)).status_code == 403
    assert (await _create(api, _create_body(), name="evil")).status_code == 403


async def test_a_valid_create_passes_the_proxy(proxied):
    _, api = proxied
    ws = config.settings.data_dir / "users" / "4242" / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    try:
        r = await _create(api, _create_body())
        assert r.status_code == 201, r.text
    finally:
        docker_direct("rm", "-f", f"{config.settings.sandbox_prefix}-4242")


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/v1.47/containers/json"),
        ("POST", "/v1.47/images/create?fromImage=alpine"),
        ("POST", "/v1.47/build"),
        ("GET", "/v1.47/images/json"),
        ("POST", "/v1.47/volumes/create"),
        ("GET", "/v1.47/info"),
        ("POST", "/v1.47/swarm/init"),
        ("GET", "/v1.47/networks/bridge"),
    ],
)
async def test_other_api_calls_are_refused(proxied, method, path):
    _, api = proxied
    r = await api.request(method, path, json={} if method == "POST" else None)
    assert r.status_code == 403, (path, r.text)


async def test_other_containers_are_off_limits(proxied):
    _, api = proxied
    assert docker_direct("create", "--name", OTHER, IMAGE, "sleep", "60").returncode == 0
    cid = docker_direct("container", "inspect", "-f", "{{.Id}}", OTHER).stdout.strip()
    for ref in (OTHER, cid):
        assert (await api.get(f"/v1.47/containers/{ref}/json")).status_code == 403
        assert (await api.post(f"/v1.47/containers/{ref}/start")).status_code == 403
        assert (await api.delete(f"/v1.47/containers/{ref}?force=1")).status_code == 403
        r = await api.post(f"/v1.47/containers/{ref}/exec", json={"Cmd": ["id"]})
        assert r.status_code == 403
    # an exec someone else created can't be started through the proxy either
    docker_direct("start", OTHER)
    exec_id = direct_exec_create(OTHER)
    assert (await api.post(f"/v1.47/exec/{exec_id}/start", json={"Detach": True})).status_code == 403


async def test_privileged_or_root_exec_is_refused(client, user, proxied):
    created, api = proxied
    created.append(user["id"])
    await DockerSandbox(user["id"]).exec("true")
    name = f"{config.settings.sandbox_prefix}-{user['id']}"
    for body in ({"Cmd": ["id"], "Privileged": True}, {"Cmd": ["id"], "User": "root"}, {"Cmd": ["id"], "User": "0"}):
        assert (await api.post(f"/v1.47/containers/{name}/exec", json=body)).status_code == 403, body
    assert (await api.post(f"/v1.47/containers/{name}/exec", json={"Cmd": ["id"]})).status_code == 201


async def test_only_the_sandbox_network_can_be_created(proxied):
    _, api = proxied
    s = config.settings
    good = {
        "Name": s.sandbox_network,
        "Driver": "bridge",
        "Options": {docker_proxy.ICC: "false", docker_proxy.BRIDGE_NAME: s.sandbox_bridge},
        "Labels": {"acf.sandbox": "1"},
    }
    for bad in (
        {**good, "Name": "other"},
        {**good, "Options": {docker_proxy.ICC: "true", docker_proxy.BRIDGE_NAME: s.sandbox_bridge}},
        {**good, "Driver": "macvlan"},
    ):
        assert (await api.post("/v1.47/networks/create", json=bad)).status_code == 403, bad


async def test_requests_are_bounded(proxied):
    _, api = proxied
    r = await api.post("/v1.47/containers/create?name=x", content=b"x" * (docker_proxy.MAX_BODY + 1))
    assert r.status_code == 413


async def test_root_owned_workspace_is_refused(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox", "docker")
    real_stat = type(workspace.workspace_dir(user["id"])).stat

    def fake_stat(self, *a, **kw):
        st = real_stat(self, *a, **kw)
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 0, 0, *tuple(st)[6:]))

    monkeypatch.setattr(type(workspace.workspace_dir(user["id"])), "stat", fake_stat)
    from acf.sandbox import SandboxError

    with pytest.raises(SandboxError, match="don't run as root"):
        await asyncio.wait_for(DockerSandbox(user["id"]).ensure(), 60)
