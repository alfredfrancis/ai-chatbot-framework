# Kubernetes guardrails for sandboxes

With `ACF_SANDBOX=kubernetes`, the app creates one pod per user and runs the agent's commands in it with
`kubectl exec`. On Docker, the [Docker proxy](../README.md) stops a taken-over app from using Docker to get
root on the host. On Kubernetes, the cluster itself stops it, with these manifests. Apply them in the
namespace the sandboxes run in (`ACF_K8S_NAMESPACE`).

| File | What it stops |
|---|---|
| `namespace.yaml` | Any pod in the namespace that breaks the Pod Security `restricted` profile: root, capabilities, privilege escalation, no seccomp, host namespaces, hostPath volumes |
| `rbac.yaml` | The app's ServiceAccount doing anything but create, get, list, watch and delete pods and exec into them, in this namespace. No update or patch, attach, port-forward, ephemeral containers, Secrets or ConfigMaps |
| `admission-policy.yaml` | The ServiceAccount creating any pod that isn't a sandbox (named `acf-sandbox-<user id>`, the sandbox image, the data claim as its only volume with `subPath: users/<that id>/workspace`, non-root user and group, no capabilities, limits set, the RuntimeClass, no token), or deleting or exec-ing into other pods |
| `network-policy.yaml` | Connections to sandbox pods, and connections from them to anything but cluster DNS and public addresses (no pods, Services, nodes, API server, private or link-local ranges, cloud metadata, IPv6) |

They are plain manifests with five placeholders, for a chart to template or for `envsubst`:

| Placeholder | Example | Meaning |
|---|---|---|
| `NAMESPACE` | `acf` | Where the app's ServiceAccount and the sandbox pods are (`ACF_K8S_NAMESPACE`) |
| `SERVICE_ACCOUNT` | `acf` | The app's ServiceAccount |
| `IMAGE` | `ghcr.io/you/acf-sandbox:2.0.0` | The sandbox image (`ACF_SANDBOX_IMAGE`) |
| `DATA_CLAIM` | `acf-data` | The ReadWriteMany claim holding `ACF_DATA_DIR` (`ACF_K8S_DATA_CLAIM`) |
| `RUNTIME_CLASS` | `gvisor`, or empty | The sandboxes' RuntimeClass (`ACF_SANDBOX_RUNTIME`); empty means the default runtime |

```sh
export NAMESPACE=acf SERVICE_ACCOUNT=acf IMAGE=acf-sandbox:latest DATA_CLAIM=acf-data RUNTIME_CLASS=
cat deploy/kubernetes/*.yaml | envsubst '$NAMESPACE $SERVICE_ACCOUNT $IMAGE $DATA_CLAIM $RUNTIME_CLASS' \
  | kubectl apply -f -
```

The two ValidatingAdmissionPolicies and their bindings are cluster-scoped and named after the namespace
(`acf-sandbox-pods-<namespace>`, `acf-sandbox-access-<namespace>`). They need Kubernetes 1.30 or later. The
NetworkPolicies need a network plugin that enforces them (Calico, Cilium, k3s's built-in kube-router; not
plain flannel).

`backend/tests/test_kubernetes_policy.py` checks all of this against a real cluster, as the ServiceAccount.

## What they don't cover

- **Reads.** The ServiceAccount can get and list every pod in the namespace (admission never sees reads, and
  RBAC can't match pod names by pattern). Sandbox pods carry no secrets, but other pods' specs in the same
  namespace are readable: keep other workloads, such as a database, out of it.
- **Exec by name.** An exec request names its pod but doesn't carry it, so the policy allows exec into any
  pod named `acf-sandbox-<digits>`. The ServiceAccount can create such pods only as sandboxes, so don't give
  other pods in the namespace such names.
- **Process limits.** Kubernetes has no per-pod process limit in the pod spec (Docker sandboxes get 512).
  Set the kubelet's `podPidsLimit` on the nodes that run sandboxes.
- **Limits' size.** The policy requires CPU and memory limits but doesn't cap them.
- **Public addresses.** A node or API server on a public address is reachable from sandboxes, though they
  have no ServiceAccount token. If yours are public, add their addresses to the egress `except` list.
- **gVisor.** `RUNTIME_CLASS` is checked by the policy, but no gVisor RuntimeClass has been tested here.
