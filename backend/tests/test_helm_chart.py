"""The Helm chart deploy/helm/acf, rendered with `helm template`: what every install gets whatever its values.
Skipped without helm. The chart installed on a cluster: deploy/helm/acf/ci/smoke.py."""

import shutil
import string
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.conftest import GUARDRAILS

pytestmark = pytest.mark.skipif(not shutil.which("helm"), reason="helm not installed")

CHART = Path(__file__).resolve().parents[2] / "deploy" / "helm" / "acf"
NAMESPACE = "acf-test"
SECRET_KEY = "a-secret-key-for-tests-only-0123456789"
LLM_KEY = "sk-llm-key-for-tests"
DB_URL = "postgresql://acf:db-password-for-tests@db:5432/acf"
REDIS_URL = "redis://:redis-password-for-tests@redis:6379/0"
# Inline values: the chart writes them into its own Secret.
INLINE = {
    "secretKey": SECRET_KEY,
    "llm.apiKey": LLM_KEY,
    "database.url": DB_URL,
    "publicUrl": "https://acf.example.com",
}
PROD = CHART / "ci" / "prod-values.yaml"
SECRET_VARS = {"ACF_SECRET_KEY", "ACF_LLM_API_KEY", "ACF_DB_URL", "ACF_REDIS_URL", "ACF_ADMIN_PASSWORD"}


def render(values: dict[str, object] | None = None, files: tuple[Path, ...] = ()) -> subprocess.CompletedProcess:
    args = ["helm", "template", "acf", str(CHART), "--namespace", NAMESPACE]
    for f in files:
        args += ["-f", str(f)]
    for k, v in (values or {}).items():
        text = str(v).lower() if isinstance(v, bool) else str(v)
        args += ["--set-string" if isinstance(v, str) else "--set", f"{k}={text}"]
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def docs(values: dict[str, object] | None = None, files: tuple[Path, ...] = ()) -> list[dict]:
    res = render(values, files)
    assert res.returncode == 0, res.stderr
    return [d for d in yaml.safe_load_all(res.stdout) if d]


def refused(values: dict[str, object], files: tuple[Path, ...] = ()) -> str:
    res = render(values, files)
    assert res.returncode != 0, "rendered"
    return res.stderr


def one(rendered: list[dict], kind: str, name: str | None = None) -> dict:
    [doc] = [d for d in rendered if d["kind"] == kind and (name is None or d["metadata"]["name"] == name)]
    return doc


def pod_specs(rendered: list[dict]) -> dict[str, dict]:
    return {
        f"{d['kind']}/{d['metadata']['name']}": d["spec"]["template"]["spec"]
        for d in rendered
        if d["kind"] in ("Deployment", "Job")
    }


def env(spec: dict) -> dict[str, dict]:
    return {e["name"]: e for e in spec["containers"][0]["env"]}


CONFIGS = {"inline": ({**INLINE, "redis.url": REDIS_URL, "replicas": 2}, ()), "prod": ({}, (PROD,))}


@pytest.mark.parametrize("values,files", CONFIGS.values(), ids=CONFIGS.keys())
def test_every_pod_meets_pod_security_restricted(values, files):
    for where, spec in pod_specs(docs(values, files)).items():
        pod = spec["securityContext"]
        assert pod["runAsNonRoot"] is True and pod["runAsUser"] == 10001, where
        assert pod["seccompProfile"] == {"type": "RuntimeDefault"}, where
        assert not any(spec.get(k) for k in ("hostNetwork", "hostPID", "hostIPC")), where
        assert all(set(v) <= {"name", "persistentVolumeClaim", "emptyDir"} for v in spec["volumes"]), where
        for c in spec["containers"] + spec.get("initContainers", []):
            sc = c["securityContext"]
            assert sc["allowPrivilegeEscalation"] is False and sc["capabilities"] == {"drop": ["ALL"]}, where
            assert sc["runAsNonRoot"] is True and sc.get("privileged") is not True, where
            assert sc["readOnlyRootFilesystem"] is True, where
            assert "ports" not in c or all("hostPort" not in p for p in c["ports"]), where


@pytest.mark.parametrize("values,files", CONFIGS.values(), ids=CONFIGS.keys())
def test_pods_get_secrets_only_as_secret_references(values, files):
    """The app's ServiceAccount can read every pod spec in its namespace."""
    rendered = docs(values, files)
    for where, spec in pod_specs(rendered).items():
        for name, var in env(spec).items():
            if name in SECRET_VARS:
                assert set(var) == {"name", "valueFrom"} and "secretKeyRef" in var["valueFrom"], (where, var)
        assert "envFrom" not in spec["containers"][0], where
    workloads = yaml.safe_dump([d for d in rendered if d["kind"] != "Secret"])
    for secret in (SECRET_KEY, LLM_KEY, DB_URL, REDIS_URL, "db-password-for-tests", "redis-password-for-tests"):
        assert secret not in workloads


def test_inline_secrets_go_into_a_hook_secret_made_before_the_migrate_job():
    rendered = docs({**INLINE, "redis.url": REDIS_URL})
    secret, job = one(rendered, "Secret"), one(rendered, "Job")
    assert secret["stringData"] == {
        "ACF_SECRET_KEY": SECRET_KEY,
        "ACF_LLM_API_KEY": LLM_KEY,
        "ACF_DB_URL": DB_URL,
        "ACF_REDIS_URL": REDIS_URL,
    }
    for doc in (secret, job):
        assert doc["metadata"]["annotations"]["helm.sh/hook"] == "pre-install,pre-upgrade"
    weight = lambda d: int(d["metadata"]["annotations"]["helm.sh/hook-weight"])  # noqa: E731
    assert weight(secret) < weight(job)
    refs = {
        n: v["valueFrom"]["secretKeyRef"]["name"]
        for n, v in env(one(rendered, "Deployment")["spec"]["template"]["spec"]).items()
        if "valueFrom" in v
    }
    assert refs == dict.fromkeys(
        ("ACF_SECRET_KEY", "ACF_DB_URL", "ACF_REDIS_URL", "ACF_LLM_API_KEY"), secret["metadata"]["name"]
    )


def test_with_secrets_managed_elsewhere_the_chart_makes_none():
    rendered = docs(files=(PROD,))
    assert not [d for d in rendered if d["kind"] == "Secret"]
    app = env(one(rendered, "Deployment")["spec"]["template"]["spec"])
    assert app["ACF_DB_URL"]["valueFrom"]["secretKeyRef"] == {"name": "acf-db-app", "key": "uri"}
    assert app["ACF_SECRET_KEY"]["valueFrom"]["secretKeyRef"] == {"name": "acf-secrets", "key": "ACF_SECRET_KEY"}
    assert app["ACF_LLM_API_KEY"]["valueFrom"]["secretKeyRef"]["optional"] is True


def test_the_migrate_job_runs_before_installs_and_upgrades_with_the_apps_key():
    job = one(docs(INLINE), "Job")
    assert job["metadata"]["annotations"]["helm.sh/hook"] == "pre-install,pre-upgrade"
    spec = job["spec"]["template"]["spec"]
    assert spec["containers"][0]["command"] == ["acf-migrate"]
    assert spec["restartPolicy"] == "Never" and spec["automountServiceAccountToken"] is False
    assert {"ACF_SECRET_KEY", "ACF_DB_URL"} <= set(env(spec))


def test_the_app_runs_sandboxes_on_kubernetes_and_never_migrates():
    rendered = docs(INLINE)
    app = env(one(rendered, "Deployment")["spec"]["template"]["spec"])
    values = {n: v.get("value") for n, v in app.items()}
    assert values["ACF_MIGRATE_ON_START"] == "false"
    assert values["ACF_SANDBOX"] == "kubernetes"
    assert values["ACF_K8S_NAMESPACE"] == NAMESPACE
    assert values["ACF_K8S_DATA_CLAIM"] == one(rendered, "PersistentVolumeClaim")["metadata"]["name"]
    assert values["ACF_DATA_DIR"] == "/data" and values["ACF_COOKIE_SECURE"] == "true"
    claim = one(rendered, "PersistentVolumeClaim")
    assert claim["spec"]["accessModes"] == ["ReadWriteMany"]


@pytest.mark.parametrize("pre_stop,grace,margin", [(10, 20, 10), (3, 120, 5)])
def test_the_grace_period_covers_the_prestop_sleep_and_the_shutdown_grace(pre_stop, grace, margin):
    values = {
        **INLINE,
        "shutdown.preStopSleepSeconds": pre_stop,
        "shutdown.graceSeconds": grace,
        "shutdown.marginSeconds": margin,
    }
    spec = one(docs(values), "Deployment")["spec"]["template"]["spec"]
    container = spec["containers"][0]
    assert container["lifecycle"]["preStop"]["exec"]["command"] == ["sleep", str(pre_stop)]
    assert env(spec)["ACF_SHUTDOWN_GRACE"]["value"] == str(grace)
    assert spec["terminationGracePeriodSeconds"] == pre_stop + grace + margin


def test_probes_and_the_service():
    rendered = docs(INLINE)
    container = one(rendered, "Deployment")["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/api/health"
    assert container["readinessProbe"]["httpGet"]["path"] == "/api/health/ready"
    assert one(rendered, "Service")["spec"]["ports"][0]["targetPort"] == "http"


@pytest.mark.parametrize(
    "values",
    [{"replicas": 2}, {"autoscaling.enabled": True, "autoscaling.maxReplicas": 3}],
    ids=["replicas", "autoscaling"],
)
def test_more_than_one_replica_needs_redis(values):
    assert "More than one app replica needs Redis" in refused({**INLINE, **values})
    assert docs({**INLINE, **values, "redis.url": REDIS_URL})
    assert docs({**INLINE, **values, "redis.existingSecret.name": "acf-redis"})


@pytest.mark.parametrize(
    "values,message",
    [
        ({"secretKey": ""}, "Set secretKey"),
        ({"secretKey": "too-short"}, "Set secretKey"),
        ({"database.url": ""}, "Set database.url"),
        ({"publicUrl": ""}, "Set publicUrl"),
        ({"existingSecret": "acf-secrets"}, "leave secretKey and llm.apiKey empty"),
        ({"env.ACF_SANDBOX": "local"}, "the chart sets ACF_SANDBOX itself"),
        ({"env.ACF_DB_URL": DB_URL}, "the chart sets ACF_DB_URL itself"),
        ({"otel.ACF_X": "1"}, "doesn't start with OTEL_"),
        ({"sandbox.image": 'x" || true || "'}, "sandbox.image must be an image reference"),
    ],
)
def test_values_that_dont_work_are_refused(values, message):
    assert message in refused({**INLINE, **values})


def test_otel_settings_reach_the_app():
    app = env(one(docs(files=(PROD,)), "Deployment")["spec"]["template"]["spec"])
    assert app["OTEL_EXPORTER_OTLP_ENDPOINT"]["value"] == "http://otel-collector.observability:4318"


def test_the_guardrails_are_deploy_kubernetes_filled_in():
    """No copy to drift: the chart renders deploy/kubernetes/*.yaml themselves (guardrails/ links to them), the
    same as `envsubst` would."""
    rendered = docs({**INLINE, "sandbox.image": "registry.example/acf-sandbox:1", "sandbox.runtimeClass": "gvisor"})
    deployment = one(rendered, "Deployment")["spec"]["template"]["spec"]
    fill = {
        "NAMESPACE": NAMESPACE,
        "SERVICE_ACCOUNT": deployment["serviceAccountName"],
        "IMAGE": "registry.example/acf-sandbox:1",
        "DATA_CLAIM": deployment["volumes"][0]["persistentVolumeClaim"]["claimName"],
        "RUNTIME_CLASS": "gvisor",
    }
    for f in ("rbac", "admission-policy", "network-policy"):
        assert (CHART / "guardrails" / f"{f}.yaml").resolve() == (GUARDRAILS / f"{f}.yaml").resolve()
        expected = [
            d for d in yaml.safe_load_all(string.Template((GUARDRAILS / f"{f}.yaml").read_text()).substitute(fill)) if d
        ]
        for doc in expected:
            name = doc["metadata"]["name"]
            assert one(rendered, doc["kind"], name) == doc, f"{f}.yaml: {doc['kind']} {name}"
    assert env(deployment)["ACF_SANDBOX_IMAGE"]["value"] == fill["IMAGE"]
    assert env(deployment)["ACF_SANDBOX_RUNTIME"]["value"] == "gvisor"
