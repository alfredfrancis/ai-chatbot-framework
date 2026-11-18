from __future__ import annotations

import functools
import json
import os
import shutil
import socket
import string
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

# Settings come from ACF_* variables: drop any the shell or a dev container set (e.g. ACF_LLM_MODEL), so the
# suite runs on its own configuration. ACF_TEST_* select test infrastructure and are kept.
for _name in [n for n in os.environ if n.startswith("ACF_") and not n.startswith("ACF_TEST_")]:
    del os.environ[_name]


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
            "ACF_AUTO_TITLES": "false",  # an extra model call after first replies; tests that want it turn it on
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


K8S_NAMESPACE = os.environ.get("ACF_TEST_K8S_NAMESPACE", "")
K8S_CLAIM = "acf-data"
K8S_APP = "acf"  # the app's ServiceAccount
K8S_IMAGE = os.environ.get("ACF_TEST_SANDBOX_IMAGE", "python:3.12-alpine")
GUARDRAILS = Path(__file__).resolve().parents[2] / "deploy" / "kubernetes"
# The tests' own kubectl calls are the cluster admin's, whatever KUBECONFIG the app is given.
_ADMIN_KUBECONFIG = os.environ.get("KUBECONFIG")


@functools.cache
def kubernetes_available() -> bool:
    """ACF_TEST_K8S_NAMESPACE names a namespace the tests create (and delete) on the cluster kubectl reaches."""
    if not K8S_NAMESPACE or not shutil.which("kubectl"):
        return False
    readyz = ["kubectl", "get", "--raw", "/readyz", "--request-timeout=10s"]
    return subprocess.run(readyz, capture_output=True).returncode == 0


def kubectl(*args: str, stdin: dict | str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "KUBECONFIG"}
    if _ADMIN_KUBECONFIG:
        env["KUBECONFIG"] = _ADMIN_KUBECONFIG
    text = json.dumps(stdin) if isinstance(stdin, dict) else stdin
    res = subprocess.run(["kubectl", *args], input=text, capture_output=True, text=True, timeout=180, env=env)
    if check and res.returncode != 0:
        raise AssertionError(f"kubectl {' '.join(args)}: {res.stderr or res.stdout}")
    return res


GUARDRAIL_FILES = ("namespace", "rbac", "admission-policy", "network-policy")


def guardrails(namespace: str, files: tuple[str, ...] = GUARDRAIL_FILES) -> str:
    """deploy/kubernetes/ for a namespace, filled in as `envsubst` or a chart would."""
    values = {
        "NAMESPACE": namespace,
        "SERVICE_ACCOUNT": K8S_APP,
        "IMAGE": K8S_IMAGE,
        "DATA_CLAIM": K8S_CLAIM,
        "RUNTIME_CLASS": "",
    }
    docs = [string.Template((GUARDRAILS / f"{f}.yaml").read_text()).substitute(values) for f in files]
    return "".join(docs)  # each file starts with ---


def plain_pod(name: str, namespace: str, labels: dict[str, str] | None = None) -> dict:
    """A pod that is not a sandbox, allowed by Pod Security `restricted`."""
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "namespace": namespace, "labels": labels or {}},
        "spec": {
            "terminationGracePeriodSeconds": 0,
            "automountServiceAccountToken": False,
            "securityContext": {"runAsNonRoot": True, "runAsUser": 1000, "seccompProfile": {"type": "RuntimeDefault"}},
            "containers": [
                {
                    "name": "c",
                    "image": K8S_IMAGE,
                    "command": ["sleep", "infinity"],
                    "securityContext": {"allowPrivilegeEscalation": False, "capabilities": {"drop": ["ALL"]}},
                }
            ],
        },
    }


def wait_for_admission_policy(namespace: str) -> None:
    """A new ValidatingAdmissionPolicy is in force a moment after it is created: wait until it refuses the app a pod
    that isn't a sandbox."""
    dry_run = ["--as", f"system:serviceaccount:{namespace}:{K8S_APP}", "create", "--dry-run=server", "-f", "-"]
    pod = plain_pod("not-a-sandbox", namespace)
    for _ in range(150):
        if "ValidatingAdmissionPolicy" in kubectl(*dry_run, stdin=pod, check=False).stderr:
            return
        time.sleep(0.2)
    raise AssertionError(f"the admission policy is not in force in {namespace}")


@pytest.fixture(scope="session")
def k8s_cluster(acf_env, tmp_path_factory):
    """The test namespace as in production: the guardrails of deploy/kubernetes/, and a ReadWriteMany data claim
    on the data dir (here a hostPath volume, valid on a one-node cluster). Yields the namespace and a kubeconfig
    that acts as the app's ServiceAccount. Starts from scratch and is deleted afterwards."""
    pv = f"{K8S_NAMESPACE}-data"
    rendered = guardrails(K8S_NAMESPACE)
    kubectl("delete", "-f", "-", "--ignore-not-found", "--wait", stdin=rendered)
    kubectl("delete", "pv", pv, "--ignore-not-found", "--wait")
    kubectl("apply", "-f", "-", stdin=rendered)
    wait_for_admission_policy(K8S_NAMESPACE)
    volume = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {"name": pv, "labels": {"acf.test": K8S_NAMESPACE}},
        "spec": {
            "capacity": {"storage": "1Gi"},
            "accessModes": ["ReadWriteMany"],
            "persistentVolumeReclaimPolicy": "Retain",
            "storageClassName": "",
            "hostPath": {"path": acf_env, "type": "Directory"},
            "claimRef": {"namespace": K8S_NAMESPACE, "name": K8S_CLAIM},
        },
    }
    claim = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": K8S_CLAIM, "namespace": K8S_NAMESPACE},
        "spec": {
            "accessModes": ["ReadWriteMany"],
            "storageClassName": "",
            "volumeName": pv,
            "resources": {"requests": {"storage": "1Gi"}},
        },
    }
    kubectl("apply", "-f", "-", stdin=volume)
    kubectl("apply", "-f", "-", stdin=claim)
    kubectl("wait", "-n", K8S_NAMESPACE, "--for=jsonpath={.status.phase}=Bound", f"pvc/{K8S_CLAIM}", "--timeout=60s")
    cluster = json.loads(kubectl("config", "view", "--raw", "--minify", "-o", "json").stdout)["clusters"][0]
    token = kubectl("create", "token", K8S_APP, "-n", K8S_NAMESPACE, "--duration=4h").stdout.strip()
    app = {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{"name": "test", "cluster": cluster["cluster"]}],
        "users": [{"name": K8S_APP, "user": {"token": token}}],
        "contexts": [{"name": K8S_APP, "context": {"cluster": "test", "user": K8S_APP}}],
        "current-context": K8S_APP,
    }
    app_kubeconfig = tmp_path_factory.mktemp("kube") / "app.json"
    app_kubeconfig.write_text(json.dumps(app))
    yield K8S_NAMESPACE, str(app_kubeconfig)
    kubectl("delete", "-f", "-", "--ignore-not-found", "--wait", stdin=rendered, check=False)
    kubectl("delete", "pv", pv, "--wait", check=False)


@pytest.fixture
def k8s_sandbox(k8s_cluster, monkeypatch):
    """ACF_SANDBOX=kubernetes in the test namespace, with kubectl acting as the app's ServiceAccount; the sandbox
    pods are deleted afterwards."""
    from acf import config

    namespace, app_kubeconfig = k8s_cluster
    for name, value in {
        "sandbox": "kubernetes",
        "sandbox_image": K8S_IMAGE,
        "k8s_namespace": namespace,
        "k8s_data_claim": K8S_CLAIM,
    }.items():
        monkeypatch.setattr(config.settings, name, value)
    monkeypatch.setenv("KUBECONFIG", app_kubeconfig)
    yield namespace
    kubectl("delete", "pods", "-n", namespace, "-l", "acf.sandbox=1", "--wait", check=False)


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
