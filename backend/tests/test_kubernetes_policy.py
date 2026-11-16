"""The cluster-side guardrails of deploy/kubernetes/, in place of the Docker proxy, against a real cluster: what
the app's ServiceAccount may and may not do with pods, and where a sandbox pod can connect. Requests go through
`kubectl --as` that ServiceAccount. Skipped without a cluster (ACF_TEST_K8S_NAMESPACE)."""

import copy
import json

import pytest

from acf import workspace
from acf.sandbox import KubernetesSandbox
from tests.conftest import K8S_APP, guardrails, kubectl, kubernetes_available, plain_pod, wait_for_admission_policy

pytestmark = [pytest.mark.kubernetes, pytest.mark.skipif(not kubernetes_available(), reason="no Kubernetes cluster")]

USER = 4242


def as_app(namespace: str, *args: str, stdin: dict | None = None):
    return kubectl("--as", f"system:serviceaccount:{namespace}:{K8S_APP}", *args, stdin=stdin, check=False)


def sandbox_pod(namespace: str) -> dict:
    """The pod KubernetesSandbox creates for USER, in namespace."""
    pod = KubernetesSandbox(USER).manifest("policy-test")
    pod["metadata"]["namespace"] = namespace
    return pod


@pytest.fixture(scope="module")
def policy_only(k8s_cluster):
    """A namespace with the app's RBAC and admission policy but no Pod Security labels, to show the policy refuses
    on its own what Pod Security refuses too."""
    namespace = f"{k8s_cluster[0]}-vap"
    rendered = guardrails(namespace, ("rbac", "admission-policy"))
    kubectl("delete", "namespace", namespace, "--ignore-not-found", "--wait")
    kubectl("create", "namespace", namespace)
    kubectl("apply", "-f", "-", stdin=rendered)
    wait_for_admission_policy(namespace)
    yield namespace
    kubectl("delete", "-f", "-", "--ignore-not-found", "--wait", stdin=rendered, check=False)
    kubectl("delete", "namespace", namespace, "--wait", check=False)


def _c(pod: dict) -> dict:
    return pod["spec"]["containers"][0]


def _rename(pod: dict, name: str, user: str) -> None:
    pod["metadata"]["name"] = name
    pod["metadata"]["labels"]["acf.user"] = user


def _privileged(pod: dict) -> None:
    _c(pod)["securityContext"].update(privileged=True, allowPrivilegeEscalation=True)


def _host_path(pod: dict) -> None:
    pod["spec"]["volumes"] = [{"name": "workspace", "hostPath": {"path": "/"}}]


MOUNT = "mounts users/<its user id>/workspace"
VOLUME = "the data claim is a sandbox pod's only volume"
# Each unsafe change, and the admission policy's reason for refusing it.
UNSAFE = {
    "another user's subPath": (lambda p: _c(p)["volumeMounts"][0].update(subPath="users/1/workspace"), MOUNT),
    "name and subPath of different users": (lambda p: _rename(p, "acf-sandbox-1", "1"), MOUNT),
    "not a sandbox's name": (lambda p: _rename(p, "acf-sandbox-x", "x"), "named acf-sandbox-<user id>"),
    "no sandbox label": (lambda p: p["metadata"]["labels"].pop("acf.sandbox"), "labelled acf.sandbox=1"),
    "privileged": (_privileged, "not privileged"),
    "hostPath volume": (_host_path, VOLUME),
    "a second volume": (lambda p: p["spec"]["volumes"].append({"name": "scratch", "emptyDir": {}}), VOLUME),
    "the whole claim": (lambda p: _c(p)["volumeMounts"][0].pop("subPath"), MOUNT),
    "foreign image": (lambda p: _c(p).update(image="alpine:3.20"), "of the sandbox image"),
    "no limits": (lambda p: _c(p).pop("resources"), "CPU and memory limits"),
    "host network": (lambda p: p["spec"].update(hostNetwork=True), "no host namespace"),
    "host PID": (lambda p: p["spec"].update(hostPID=True), "no host namespace"),
    "an added capability": (
        lambda p: _c(p)["securityContext"]["capabilities"].update(add=["SYS_ADMIN"]),
        "drop every capability",
    ),
    "root": (lambda p: p["spec"]["securityContext"].update(runAsUser=0, runAsNonRoot=False), "non-root user"),
    "root group": (lambda p: p["spec"]["securityContext"].update(runAsGroup=0), "non-root user and group"),
    "a ServiceAccount token": (lambda p: p["spec"].update(automountServiceAccountToken=True), VOLUME),
    "another runtime": (lambda p: p["spec"].update(runtimeClassName="crun"), "the cluster's default runtime"),
    "an init container": (
        lambda p: p["spec"].update(initContainers=[copy.deepcopy(_c(p)) | {"name": "init"}]),
        "one container",
    ),
    "a chosen node": (lambda p: p["spec"].update(nodeName="any-node"), "placed by the scheduler"),
}


def test_a_sandbox_pod_is_admitted(k8s_sandbox, policy_only):
    for namespace in (k8s_sandbox, policy_only):
        res = as_app(namespace, "create", "--dry-run=server", "-f", "-", stdin=sandbox_pod(namespace))
        assert res.returncode == 0, res.stderr


@pytest.mark.parametrize("change,reason", UNSAFE.values(), ids=UNSAFE.keys())
def test_unsafe_pods_are_refused(k8s_sandbox, policy_only, change, reason):
    for namespace in (k8s_sandbox, policy_only):
        pod = sandbox_pod(namespace)
        change(pod)
        res = as_app(namespace, "create", "--dry-run=server", "-f", "-", stdin=pod)
        assert res.returncode != 0, namespace
        if namespace == policy_only:  # without Pod Security, the admission policy refuses it on its own
            assert f"ValidatingAdmissionPolicy 'acf-sandbox-pods-{namespace}'" in res.stderr, res.stderr
            assert reason in res.stderr, res.stderr


def test_the_app_works_in_its_namespace_only(k8s_sandbox, policy_only):
    for namespace in (policy_only, "default"):
        res = as_app(k8s_sandbox, "create", "--dry-run=server", "-f", "-", stdin=sandbox_pod(namespace))
        assert res.returncode != 0 and "forbidden" in res.stderr, res.stderr
        assert as_app(k8s_sandbox, "get", "pods", "-n", namespace).returncode != 0
    for resource in ("secrets", "configmaps", "serviceaccounts", "networkpolicies", "roles"):
        assert as_app(k8s_sandbox, "get", resource, "-n", k8s_sandbox).returncode != 0, resource
    # Nor the admission policy itself.
    change = json.dumps([{"op": "replace", "path": "/spec/variables/0/expression", "value": '"alpine:3.20"'}])
    res = as_app(
        k8s_sandbox,
        "patch",
        "validatingadmissionpolicy",
        f"acf-sandbox-pods-{k8s_sandbox}",
        "--type=json",
        "-p",
        change,
    )
    assert res.returncode != 0 and "forbidden" in res.stderr


def test_the_app_deletes_and_execs_into_sandbox_pods_only(k8s_sandbox):
    ns = k8s_sandbox
    others = [plain_pod("acf-database", ns), plain_pod("acf-sandbox-999", ns)]  # the second has no sandbox label
    for pod in others:
        kubectl("apply", "-f", "-", stdin=pod)
    try:
        sandbox = sandbox_pod(ns)
        assert as_app(ns, "create", "-f", "-", stdin=sandbox).returncode == 0
        kubectl("wait", "-n", ns, "--for=condition=Ready", "pod", *[p["metadata"]["name"] for p in [sandbox, *others]])
        # An exec request names a pod but doesn't carry it, so execs are allowed by name.
        res = as_app(ns, "-n", ns, "exec", "acf-database", "--", "id")
        assert res.returncode != 0 and "acf-sandbox-access-" in res.stderr, res.stderr
        for pod in others:
            name = pod["metadata"]["name"]
            res = as_app(ns, "-n", ns, "delete", "pod", name, "--dry-run=server")
            assert res.returncode != 0 and "acf-sandbox-access-" in res.stderr, res.stderr
            res = as_app(ns, "-n", ns, "label", "pod", name, "acf.sandbox=1")
            assert res.returncode != 0 and "forbidden" in res.stderr, res.stderr  # no patch or update at all
        name = sandbox["metadata"]["name"]
        res = as_app(ns, "-n", ns, "exec", name, "--", "id", "-u")
        assert res.returncode == 0 and res.stdout.strip() not in ("", "0"), res.stderr
        for sub in (["attach", name], ["port-forward", name, "18080:80"]):
            res = as_app(ns, "-n", ns, *sub)
            assert res.returncode != 0 and "forbidden" in res.stderr, res.stderr
        assert as_app(ns, "-n", ns, "delete", "pod", name, "--wait").returncode == 0
    finally:
        kubectl("delete", "pods", "-n", ns, "acf-database", "acf-sandbox-999", "--ignore-not-found", check=False)
        kubectl("delete", "pod", "-n", ns, sandbox_pod(ns)["metadata"]["name"], "--ignore-not-found", check=False)


PROBE = """
import socket, sys
for target in sys.argv[1:]:
    host, port = target.rsplit(":", 1)
    try:
        socket.create_connection((host, int(port)), timeout=3).close()
        print(target, "open")
    except OSError:
        print(target, "blocked")
"""


def _probe(result: str) -> dict[str, str]:
    return dict(line.split() for line in result.strip().splitlines())


async def test_sandbox_network_is_dns_and_public_addresses_only(k8s_sandbox):
    ns = k8s_sandbox
    api = kubectl("get", "svc", "kubernetes", "-n", "default", "-o", "jsonpath={.spec.clusterIP}").stdout
    node = kubectl("get", "nodes", "-o", "jsonpath={.items[0].status.addresses[0].address}").stdout
    dns = ["get", "pods", "-n", "kube-system", "-l", "k8s-app=kube-dns", "-o", "jsonpath={.items[0].status.podIP}"]
    dns_pod = kubectl(*dns).stdout
    private = [f"{api}:443", f"{node}:6443", f"{node}:10250", f"{dns_pod}:9153", "169.254.169.254:80"]
    public = "1.1.1.1:443"
    sbx = KubernetesSandbox(USER)
    kubectl("apply", "-f", "-", stdin=plain_pod("acf-control", ns))
    try:
        kubectl("wait", "-n", ns, "--for=condition=Ready", "pod/acf-control")
        from_control = ["exec", "-n", ns, "acf-control", "--", "python3", "-c", PROBE]
        control = _probe(kubectl(*from_control, *private, public).stdout)
        # The control pod has no sandbox label: what it reaches, only the policies keep a sandbox from.
        assert all(control[t] == "open" for t in private if not t.startswith("169.254.")), control

        (workspace.workspace_dir(USER) / "probe.py").write_text(PROBE)
        seen = _probe((await sbx.exec(f"python3 probe.py {' '.join(private)} {public}")).stdout)
        assert {t: seen[t] for t in private} == dict.fromkeys(private, "blocked")
        if control[public] == "open":  # this cluster can reach the internet: so can a sandbox
            assert seen[public] == "open"
        lookup = "import socket; print(socket.gethostbyname('kubernetes.default.svc.cluster.local'))"
        assert (await sbx.exec(f'python3 -c "{lookup}"')).stdout.strip() == api  # DNS works

        # Nothing connects to a sandbox, not even a pod in its namespace.
        assert (await sbx.exec("nohup python3 -m http.server 8000 >/dev/null 2>&1 & sleep 1")).exit_code == 0
        assert _probe((await sbx.exec("python3 probe.py 127.0.0.1:8000")).stdout) == {"127.0.0.1:8000": "open"}
        ip = kubectl("get", "pod", "-n", ns, sbx.name, "-o", "jsonpath={.status.podIP}").stdout
        inbound = kubectl(*from_control, f"{ip}:8000").stdout
        assert _probe(inbound) == {f"{ip}:8000": "blocked"}
    finally:
        kubectl("delete", "pod", "-n", ns, "acf-control", "--ignore-not-found", check=False)
