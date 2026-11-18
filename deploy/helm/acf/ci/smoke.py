"""Install the chart on a cluster and use it as a user would. Test only; starts from scratch on every run and
cleans up after itself (--keep leaves everything installed).

    KUBECONFIG=/etc/rancher/k3s/k3s.yaml .venv/bin/python deploy/helm/acf/ci/smoke.py

Needs kubectl and helm on PATH, root (it makes a hostPath volume under /opt/acf-k3-data), and on the node the
app image acf:dev and the images of ci/deps.yaml and ci/smoke-values.yaml (postgres:17.6-alpine,
redis:7.4-alpine, python:3.12-alpine as the sandbox image). One node only: the ReadWriteMany volume is a
hostPath. `kubectl port-forward` needs socat on a node whose runtime is Docker (cri-dockerd).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import websockets

ROOT = Path(__file__).resolve().parents[4]
CHART = ROOT / "deploy" / "helm" / "acf"
VALUES = CHART / "ci" / "smoke-values.yaml"
sys.path.insert(0, str(ROOT / "backend"))
from tests.acp_client import Acp, RpcError, Turn  # noqa: E402

NS = "acf-k3-smoke"
DEPS = "acf-k3-deps"
RELEASE = "acf"
PV = f"{NS}-data"
DATA = Path("/opt/acf-k3-data") / NS
PORT = 18080
APP = "app.kubernetes.io/component=app"
REDIS = f"redis://redis.{DEPS}.svc.cluster.local:6379/0"


def run(*args: str, stdin: str | None = None, check: bool = True, timeout: float = 600) -> subprocess.CompletedProcess:
    res = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
    if check and res.returncode != 0:
        raise AssertionError(f"{' '.join(args)}: {res.stderr or res.stdout}")
    return res


def kubectl(*args: str, **kw) -> subprocess.CompletedProcess:
    return run("kubectl", *args, **kw)


def helm(*args: str, **kw) -> subprocess.CompletedProcess:
    return run("helm", *args, **kw)


def as_app(*args: str, stdin: str) -> subprocess.CompletedProcess:
    return kubectl("--as", f"system:serviceaccount:{NS}:{RELEASE}", "-n", NS, *args, stdin=stdin, check=False)


def app_pods() -> list[str]:
    out = kubectl("get", "pods", "-n", NS, "-l", APP, "-o", "json").stdout
    return sorted(p["metadata"]["name"] for p in json.loads(out)["items"] if "deletionTimestamp" not in p["metadata"])


def migrate_job() -> dict:
    return json.loads(kubectl("get", "job", f"{RELEASE}-migrate", "-n", NS, "-o", "json").stdout)


def install_args(*extra: str) -> list[str]:
    return [RELEASE, str(CHART), "-n", NS, "-f", str(VALUES), "--wait", "--timeout", "5m", *extra]


def cleanup() -> None:
    helm("uninstall", RELEASE, "-n", NS, "--wait", check=False)
    for kind in ("validatingadmissionpolicybinding", "validatingadmissionpolicy"):
        names = [f"acf-sandbox-pods-{NS}", f"acf-sandbox-access-{NS}"]
        kubectl("delete", kind, *names, "--ignore-not-found", "--wait", check=False)
    kubectl("delete", "namespace", NS, DEPS, "--ignore-not-found", "--wait", "--timeout=180s", check=False)
    kubectl("delete", "pv", PV, "--ignore-not-found", "--wait", check=False)
    shutil.rmtree(DATA, ignore_errors=True)


def setup() -> None:
    cleanup()
    kubectl("create", "namespace", DEPS)
    fake = ROOT / "backend" / "tests" / "fakes" / "fake_llm.py"
    kubectl("create", "configmap", "fake-llm", "-n", DEPS, f"--from-file=fake_llm.py={fake}")
    kubectl("apply", "-n", DEPS, "-f", str(CHART / "ci" / "deps.yaml"))
    for name in ("postgres", "redis", "fake-llm"):
        kubectl("rollout", "status", "-n", DEPS, f"deploy/{name}", "--timeout=180s")
    DATA.mkdir(parents=True)
    shutil.chown(DATA, 10001, 10001)
    volume = {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {"name": PV},
        "spec": {
            "capacity": {"storage": "1Gi"},
            "accessModes": ["ReadWriteMany"],
            "persistentVolumeReclaimPolicy": "Retain",
            "storageClassName": "",
            "hostPath": {"path": str(DATA), "type": "Directory"},
            "claimRef": {"namespace": NS, "name": f"{RELEASE}-data"},
        },
    }
    kubectl("apply", "-f", "-", stdin=json.dumps(volume))


@contextlib.contextmanager
def forward(target: str, remote: int) -> Iterator[str]:
    """kubectl port-forward to a Service or pod; yields its local base URL."""
    proc = subprocess.Popen(
        ["kubectl", "port-forward", "-n", NS, target, f"{PORT}:{remote}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 30
        while True:
            with contextlib.suppress(OSError), socket.create_connection(("127.0.0.1", PORT), 1):
                break
            if proc.poll() is not None or time.monotonic() > deadline:
                raise AssertionError(f"port-forward {target}: {proc.stderr.read().decode() if proc.stderr else ''}")
            time.sleep(0.2)
        yield f"http://localhost:{PORT}"
    finally:
        proc.terminate()
        proc.wait(10)


class Ws:
    """The socket interface tests.acp_client.Acp reads and writes, over a real WebSocket."""

    def __init__(self, conn):
        self.conn = conn

    async def send_text(self, text: str) -> None:
        await self.conn.send(text)

    async def receive_text(self) -> str | None:
        try:
            return await self.conn.recv()
        except websockets.ConnectionClosed:
            return None


@contextlib.asynccontextmanager
async def acp(base: str, cookie: str):
    url = base.replace("http://", "ws://") + "/api/acp"
    headers = {"Cookie": f"acf_session={cookie}"}
    async with websockets.connect(url, additional_headers=headers, origin=base) as conn:
        client = Acp(Ws(conn))
        try:
            await client.request("initialize", {"protocolVersion": 1, "clientCapabilities": {}})
            yield client
        finally:
            client.close()


async def prompt(client: Acp, sid: str, text: str) -> Turn:
    start = len(client.notifications)
    stop_reason = error = None
    try:
        params = {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}
        stop_reason = (await client.request("session/prompt", params, timeout=300))["stopReason"]
    except RpcError as e:
        error = e.message
    mine = [n for n in client.notifications[start:] if n.get("params", {}).get("sessionId") == sid]
    updates = [n["params"]["update"] for n in mine if n["method"] == "session/update"]
    return Turn(updates, [], stop_reason, error)


class Smoke:
    def __init__(self) -> None:
        self.cookie = ""
        self.sid = ""
        self.user_id = 0
        self.results: list[tuple[str, bool, str]] = []

    async def step0_install(self) -> str:
        kubectl("create", "namespace", NS)
        refused = helm("install", *install_args("--dry-run=server"), check=False)
        assert refused.returncode != 0 and "needs Pod Security `restricted`" in refused.stderr, refused.stderr
        # The namespace as deploy/kubernetes/namespace.yaml makes it.
        namespace = (CHART / "guardrails" / "namespace.yaml").read_text().replace("${NAMESPACE}", NS)
        kubectl("apply", "-f", "-", stdin=namespace)
        helm("install", *install_args())
        job = migrate_job()
        assert job["status"].get("succeeded") == 1, job["status"]
        return f"unlabelled namespace refused ({refused.stderr.strip()[-110:]}); installed; migrate Job succeeded"

    async def step1_sign_up(self) -> str:
        with forward(f"svc/{RELEASE}", 80) as base:
            async with httpx.AsyncClient(base_url=base, timeout=30) as http:
                r = await http.post(
                    "/api/auth/signup", json={"email": "smoke@example.com", "password": "correct horse", "name": "S"}
                )
                assert r.status_code == 200, r.text
                self.cookie = http.cookies["acf_session"]
                self.user_id = r.json()["user"]["id"]
        return f"user {self.user_id} signed up through svc/{RELEASE}"

    async def step2_sandbox_command(self) -> str:
        with forward(f"svc/{RELEASE}", 80) as base:
            async with acp(base, self.cookie) as client:
                self.sid = (await client.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
                turn = await prompt(client, self.sid, "run: echo hi > made.txt && id -u")
        assert turn.error is None, turn.error
        output = turn.results[0]["text"].strip()
        assert output.endswith("[exit code 0]"), output
        uid = int(output.splitlines()[0])
        assert uid != 0, f"the sandbox ran as root: {output}"
        pod = json.loads(kubectl("get", "pod", f"acf-sandbox-{self.user_id}", "-n", NS, "-o", "json").stdout)
        assert pod["spec"]["securityContext"]["runAsUser"] == uid
        return f"`id -u` in pod acf-sandbox-{self.user_id} printed {uid}; reply {turn.final!r}"

    async def step3_app_pod_restart(self) -> str:
        [old] = app_pods()
        kubectl("delete", "pod", old, "-n", NS, "--wait")
        kubectl("rollout", "status", f"deploy/{RELEASE}", "-n", NS, "--timeout=180s")
        [new] = app_pods()
        assert new != old
        with forward(f"svc/{RELEASE}", 80) as base:
            async with httpx.AsyncClient(base_url=base, timeout=30, cookies={"acf_session": self.cookie}) as http:
                chat = (await http.get(f"/api/chats/{self.sid}")).json()
                made = (await http.get("/api/files/content", params={"path": "made.txt"})).json()
        texts = [json.dumps(m) for m in chat["messages"]]
        assert any("echo hi > made.txt" in t for t in texts), texts
        assert made["content"] == "hi\n", made
        return f"pod {old} replaced by {new}; chat {self.sid} has {len(texts)} messages; made.txt = {made['content']!r}"

    async def step4_upgrade_runs_migrate(self) -> str:
        before = migrate_job()
        helm("upgrade", *install_args("--set", f"podAnnotations.smoke-upgrade=u{int(time.time())}"))
        after = migrate_job()
        assert after["metadata"]["uid"] != before["metadata"]["uid"], "the migrate Job was not run again"
        assert after["status"].get("succeeded") == 1, after["status"]
        logs = kubectl("logs", f"job/{RELEASE}-migrate", "-n", NS).stdout
        assert "Database schema is at revision" in logs, logs
        revision = json.loads(helm("status", RELEASE, "-n", NS, "-o", "json").stdout)["version"]
        line = logs.strip().splitlines()[-1]
        return f"release revision {revision}; new migrate Job {after['metadata']['uid'][:8]} succeeded: {line}"

    async def step5_two_replicas(self) -> str:
        refused = helm("upgrade", *install_args("--set", "replicas=2"), check=False)
        assert refused.returncode != 0 and "needs Redis" in refused.stderr, refused.stderr
        helm("upgrade", *install_args("--set", "replicas=2", "--set", f"redis.url={REDIS}"))
        pods = app_pods()
        assert len(pods) == 2, pods
        seen = []
        for pod in pods:
            with forward(f"pod/{pod}", 8000) as base:
                async with httpx.AsyncClient(base_url=base, timeout=30) as http:
                    ready = (await http.get("/api/health/ready")).json()
                assert ready == {"db": "ok", "bus": "ok"}, ready
                async with acp(base, self.cookie) as client:
                    sid = (await client.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
                    turn = await prompt(client, sid, "run: cat made.txt")
            output = turn.results[0]["text"].strip() if turn.results else ""
            assert turn.error is None and output.splitlines()[0] == "hi", (turn.error, turn.results)
            seen.append(f"{pod}: ready {ready}, chat {sid} ran `cat made.txt` -> {output!r}")
        return "without Redis: refused (" + refused.stderr.strip().splitlines()[-1][:120] + "); " + "; ".join(seen)

    async def step6_sandbox_admitted(self) -> str:
        labels = json.loads(kubectl("get", "namespace", NS, "-o", "json").stdout)["metadata"]["labels"]
        assert labels.get("pod-security.kubernetes.io/enforce") == "restricted", labels
        listed = json.loads(kubectl("get", "pods", "-n", NS, "-l", "acf.sandbox=1", "-o", "json").stdout)["items"]
        names = [p["metadata"]["name"] for p in listed]
        assert names == [f"acf-sandbox-{self.user_id}"], names
        pod = listed[0]
        assert pod["status"]["phase"] == "Running", pod["status"]["phase"]
        # The live pod, as the app's ServiceAccount would send it again. Admission runs before the API server
        # finds the name taken, so AlreadyExists means Pod Security and both admission policies let it through.
        spec = {k: v for k, v in pod["spec"].items() if k != "nodeName"}
        meta = {"name": pod["metadata"]["name"], "namespace": NS, "labels": pod["metadata"]["labels"]}
        same = {"apiVersion": "v1", "kind": "Pod", "metadata": meta, "spec": spec}
        res = as_app("create", "--dry-run=server", "-f", "-", stdin=json.dumps(same))
        assert "AlreadyExists" in res.stderr or "already exists" in res.stderr, res.stderr
        foreign = json.loads(json.dumps(same))
        foreign["spec"]["containers"][0]["image"] = "alpine:3.20"
        bad = as_app("create", "--dry-run=server", "-f", "-", stdin=json.dumps(foreign))
        assert f"ValidatingAdmissionPolicy 'acf-sandbox-pods-{NS}'" in bad.stderr, bad.stderr
        return (
            f"listed {names} (Running, runAsUser {pod['spec']['securityContext']['runAsUser']}); its spec resent as "
            f"the app: {res.stderr.strip()[:90]!r}; with a foreign image: refused by acf-sandbox-pods-{NS}"
        )

    async def run(self) -> bool:
        steps = [
            self.step0_install,
            self.step1_sign_up,
            self.step2_sandbox_command,
            self.step3_app_pod_restart,
            self.step4_upgrade_runs_migrate,
            self.step5_two_replicas,
            self.step6_sandbox_admitted,
        ]
        for step in steps:
            name = step.__name__
            try:
                evidence = await step()
                self.results.append((name, True, evidence))
            except Exception as e:  # noqa: BLE001 - reported, and the later steps depend on this one
                self.results.append((name, False, f"{type(e).__name__}: {e}"))
                break
        for name, ok, evidence in self.results:
            print(f"{'PASS' if ok else 'FAIL'} {name}: {evidence}")
        return len(self.results) == len(steps) and all(ok for _, ok, _ in self.results)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--keep", action="store_true", help="leave the release and namespaces installed")
    p.add_argument("--cleanup", action="store_true", help="only remove what an earlier run left")
    args = p.parse_args()
    if args.cleanup:
        cleanup()
        return
    ok = False
    try:
        setup()
        ok = asyncio.run(Smoke().run())
    finally:
        if not args.keep:
            cleanup()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
