"""Real Kubernetes sandbox tests, the counterparts of test_sandbox_docker.py. Skipped without a cluster
(ACF_TEST_K8S_NAMESPACE and kubectl)."""

import json
import os
import secrets
import shutil

import pytest

from acf import config, workspace
from acf.sandbox import KubernetesSandbox, SandboxError, parse_bytes
from tests.conftest import FAKES, kubectl, kubernetes_available, send


def on_cluster(test):
    return pytest.mark.kubernetes(pytest.mark.skipif(not kubernetes_available(), reason="no Kubernetes cluster")(test))


def pod(sbx: KubernetesSandbox) -> dict:
    return json.loads(kubectl("get", "pod", "-n", config.settings.k8s_namespace, sbx.name, "-o", "json").stdout)


@on_cluster
async def test_commands_run_in_an_isolated_pod(client, user, k8s_sandbox):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    turn = await send(client, chat_id, "run: hostname && pwd && id -u && id -g && echo hi > made-in-sandbox.txt")
    host, cwd, uid, gid = turn.results[0]["text"].split("\n")[:4]
    owner = workspace.workspace_dir(user["id"]).stat()
    assert (host, cwd, uid, gid) == ("sandbox", "/workspace", str(owner.st_uid), str(owner.st_gid))
    assert uid != "0" and gid != "0"
    assert (workspace.workspace_dir(user["id"]) / "made-in-sandbox.txt").read_text() == "hi\n"
    status = (await client.get("/api/sandbox")).json()
    assert status == {
        "kind": "kubernetes",
        "isolated": True,
        "state": "running",
        "name": f"acf-sandbox-{user['id']}",
        "image": config.settings.sandbox_image,
    }
    await client.post("/api/sandbox/reset")
    assert (await client.get("/api/sandbox")).json()["state"] == "missing"


@on_cluster
async def test_no_capabilities_no_privilege_escalation_no_cluster_credentials(user, k8s_sandbox):
    sbx = KubernetesSandbox(user["id"])
    status = (await sbx.exec("grep -E '^(Cap(Inh|Prm|Eff|Bnd|Amb)|NoNewPrivs|Seccomp):' /proc/self/status")).stdout
    fields = dict(line.split(":\t") for line in status.splitlines())
    assert {k: v for k, v in fields.items() if k.startswith("Cap")} == dict.fromkeys(
        ["CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"], "0000000000000000"
    )
    assert fields["NoNewPrivs"] == "1" and fields["Seccomp"] == "2"  # 2: a seccomp filter is on
    res = await sbx.exec("ls /var/run/secrets/kubernetes.io/serviceaccount")
    assert res.exit_code != 0  # no ServiceAccount token to talk to the cluster with
    cgroup = "cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.limit_in_bytes"  # v2, v1
    assert (await sbx.exec(cgroup)).stdout.strip() == str(parse_bytes(config.settings.sandbox_memory))
    spec = pod(sbx)["spec"]
    assert spec["containers"][0]["resources"]["limits"] == {
        "cpu": config.settings.sandbox_cpus,
        "memory": str(parse_bytes(config.settings.sandbox_memory)),
    }
    assert spec["automountServiceAccountToken"] is False and spec["enableServiceLinks"] is False


@on_cluster
async def test_files_land_in_the_workspace_and_nowhere_else(user, k8s_sandbox):
    sbx = KubernetesSandbox(user["id"])
    outside = f"outside-{secrets.token_hex(4)}.txt"
    assert (await sbx.exec(f"echo in > /workspace/in.txt && echo out > /tmp/{outside}")).exit_code == 0
    assert (workspace.workspace_dir(user["id"]) / "in.txt").read_text() == "in\n"
    data = config.settings.data_dir
    assert not list(data.rglob(outside))  # the rest of the pod's filesystem is its own
    # Nothing of the data volume outside the user's workspace is mounted: not the files at its root, not the
    # ones next to the workspace (its sandbox-id among them), not the other users'.
    beside = [data / f"root-{outside}", workspace.user_root(user["id"]) / f"user-{outside}"]
    for path in beside:
        path.write_text("x")
    names = " -o ".join(f"-name {name}" for name in ["in.txt", "sandbox-id", *(path.name for path in beside)])
    found = await sbx.exec(f"find / -path /proc -prune -o \\( {names} \\) -print 2>/dev/null")
    assert found.stdout == "/workspace/in.txt\n"  # the workspace file, as the control
    assert "users" not in (await sbx.exec("ls / /workspace/..")).stdout.split()


@on_cluster
async def test_one_pod_per_user(client, user, k8s_sandbox):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    await send(client, chat_id, "run: echo private > secret.txt")

    await client.post("/api/auth/logout")
    other = (await client.post("/api/auth/signup", json={"email": "b@k8s.example", "password": "password123"})).json()
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    tool = (await send(client, chat_id, "run: hostname; ls /workspace; cat secret.txt")).results[0]
    assert "No such file" in tool["text"] and tool["status"] == "failed"
    pods = json.loads(kubectl("get", "pods", "-n", k8s_sandbox, "-l", "acf.sandbox=1", "-o", "json").stdout)["items"]
    assert sorted(p["metadata"]["name"] for p in pods) == sorted(
        f"acf-sandbox-{i}" for i in (user["id"], other["user"]["id"])
    )


@on_cluster
async def test_stdio_mcp_runs_inside_the_pod(client, user, k8s_sandbox):
    shutil.copy(FAKES / "echo_mcp.py", workspace.workspace_dir(user["id"]) / "echo_mcp.py")
    cfg = {"mcpServers": {"echo": {"command": "python3", "args": ["echo_mcp.py"]}}}
    await client.put("/api/mcp/config", json={"config": json.dumps(cfg)})
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    turn = await send(client, chat_id, 'tool: mcp_call {"server": "echo", "tool": "whereami", "arguments": {}}')
    assert turn.final == "Result: host=sandbox cwd=/workspace"


@on_cluster
async def test_stale_pod_is_replaced(user, k8s_sandbox):
    """If the workspace folder is recreated (data wiped, id reused), the old pod is replaced: its mount still
    points at the folder that was deleted."""
    sbx = KubernetesSandbox(user["id"])
    assert (await sbx.exec("echo one")).exit_code == 0
    shutil.rmtree(workspace.user_root(user["id"]))
    res = await sbx.exec("echo two > f.txt && cat f.txt")
    assert res.exit_code == 0 and res.stdout == "two\n", res
    assert (workspace.workspace_dir(user["id"]) / "f.txt").read_text() == "two\n"


@on_cluster
async def test_a_pod_that_cannot_start_fails_with_the_reason(user, k8s_sandbox, monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox_image", "acf-k1-no-such-image:never")
    sbx = KubernetesSandbox(user["id"])
    with pytest.raises(SandboxError, match="Could not start sandbox: .*Image"):
        await sbx.ensure()
    assert kubectl("get", "pod", "-n", k8s_sandbox, sbx.name, check=False).returncode != 0  # cleaned up


async def test_root_owned_workspace_is_refused(user, monkeypatch):
    real_stat = type(workspace.workspace_dir(user["id"])).stat

    def fake_stat(self, *a, **kw):
        st = real_stat(self, *a, **kw)
        return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink, 0, 0, *tuple(st)[6:]))

    monkeypatch.setattr(type(workspace.workspace_dir(user["id"])), "stat", fake_stat)
    with pytest.raises(SandboxError, match="don't run as root"):
        KubernetesSandbox(user["id"]).manifest("id")
