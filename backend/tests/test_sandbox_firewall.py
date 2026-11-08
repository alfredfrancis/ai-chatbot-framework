"""deploy/sandbox-firewall.sh, seen from inside a real sandbox. Runs when the firewall is installed on
this Docker host (ACF_TEST_FIREWALL=1); ACF_TEST_FIREWALL_PUBLIC=1 also checks that the internet works."""

import json
import os
import socket
import subprocess
import threading

import pytest

from acf import config
from acf.sandbox import DockerSandbox
from tests.conftest import docker_available

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not docker_available(), reason="Docker not available"),
    pytest.mark.skipif(os.environ.get("ACF_TEST_FIREWALL") != "1", reason="sandbox firewall not installed"),
]

IMAGE = os.environ.get("ACF_TEST_SANDBOX_IMAGE", "python:3.12-alpine")


def connect(ip: str, port: int) -> str:
    return f"python3 -c \"import socket; socket.create_connection(('{ip}', {port}), 3); print('open')\" 2>&1 || true"


@pytest.fixture
def host_server():
    """A TCP server on every host address, like a database or admin port would be."""
    srv = socket.create_server(("0.0.0.0", 0))
    srv.settimeout(0.5)
    stop = threading.Event()

    def accept():
        while not stop.is_set():
            try:
                srv.accept()[0].close()
            except OSError:
                pass

    threading.Thread(target=accept, daemon=True).start()
    yield srv.getsockname()[1]
    stop.set()
    srv.close()


@pytest.fixture
async def sandbox(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox", "docker")
    monkeypatch.setattr(config.settings, "sandbox_image", IMAGE)
    sbx = DockerSandbox(user["id"])
    await sbx.ensure()
    yield sbx
    docker("rm", "-f", sbx.name)


def docker(*args: str) -> str:
    return subprocess.run(["docker", *args], capture_output=True, text=True).stdout


def host_addresses() -> list[str]:
    out = subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split()
    return [a for a in out if ":" not in a]


async def test_sandbox_cannot_reach_the_host_or_private_addresses(sandbox, host_server):
    net = json.loads(docker("network", "inspect", config.settings.sandbox_network))[0]
    gateway = net["IPAM"]["Config"][0]["Gateway"]
    for ip in [gateway, *host_addresses()]:
        res = await sandbox.exec(connect(ip, host_server))
        assert "open" not in res.stdout, (ip, res.stdout)
    for ip, port in (("169.254.169.254", 80), ("10.0.0.1", 80), ("192.168.0.1", 80), ("172.17.0.1", host_server)):
        res = await sandbox.exec(connect(ip, port))
        assert "open" not in res.stdout, (ip, res.stdout)


@pytest.mark.skipif(os.environ.get("ACF_TEST_FIREWALL_PUBLIC") != "1", reason="no internet check requested")
async def test_sandbox_still_reaches_the_internet(sandbox):
    res = await sandbox.exec(connect("1.1.1.1", 443))
    assert "open" in res.stdout, res.stdout
    res = await sandbox.exec("python3 -c \"import socket; print(socket.gethostbyname('pypi.org'))\"")
    assert res.exit_code == 0, res.as_text()
