"""One isolated sandbox per user, behind a provider-agnostic port.

`Sandbox` is the port the rest of the app uses; each provider is an adapter. An adapter implements
`ensure` (start the sandbox if needed), `run` (run a shell command, return its output), `spawn` (start a
long-lived process and stream bytes to and from it, used for stdio MCP servers), `reset`, and, to be
stopped while idle, `running` and `stop`. The rest of the app calls `exec` and `process`, which record the
use, and never knows which adapter it has.

The contract every adapter keeps (tests/test_sandbox_contract.py checks it for each one):
- The user's workspace (`workspace.workspace_dir`, owned by the backend) is the working directory
  of every command and process, mounted or synced so files are the same on both sides.
- A timeout, a cancelled `exec` and `SandboxProcess.kill` stop the command and everything it started
  inside the sandbox, not only the backend's handle on it.
- Secrets stay in the backend: an adapter only receives the commands and environment it is given.
- A stopped sandbox starts again on its next use, with the workspace as it was.

Idle sandboxes are stopped (`sweeper`, in every process): each use stamps the time on the bus, and a
sandbox no process has used for ACF_SANDBOX_IDLE_MINUTES is stopped. A command, a process or an agent's
turn in flight counts as use for as long as it lasts.

Adapters:
- DockerSandbox: a long-lived container per user (`acf-sbx-<id>`) with the workspace bind-mounted at
  /workspace, resource limits, no Linux capabilities and no privilege escalation.
- KubernetesSandbox: the same as a pod per user (`acf-sandbox-<id>`), its /workspace a subPath of the
  shared data volume. deploy/kubernetes/ holds the cluster-side guardrails, in place of the Docker proxy.
- LocalSandbox: runs on the host in the workspace folder. Development/testing only; NOT isolated.
Others register with `register_sandbox()` or are named as `ACF_SANDBOX=package.module:Class`.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import os
import re
import secrets
import shutil
import signal
import time
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import anyio
import anyio.abc

from acf import bus, config, telemetry, workspace

log = logging.getLogger("acf.sandbox")
MAX_OUTPUT = 2_000_000  # the agent truncates for the model and saves the full text
WORKDIR = "/workspace"
PIDS_LIMIT = 512
STOP_GRACE = 2.0  # seconds a process gets to exit after its stdin closes, and to die after a kill
# Variables a host process inherits (as the MCP SDK's stdio client does); everything else must be passed.
_HOST_ENV = ("HOME", "LOGNAME", "PATH", "SHELL", "TERM", "USER")


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def as_text(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"[stderr]\n{self.stderr}")
        if self.timed_out:
            parts.append("[timed out]")
        parts.append(f"[exit code {self.exit_code}]")
        return "\n".join(parts)


def _clip(data: bytes) -> str:
    text = data.decode(errors="replace")
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + f"\n… ({len(text) - MAX_OUTPUT} more characters)"
    return text


_reaping: set[asyncio.Task] = set()


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """Kill the command and everything it started (it runs in its own process group)."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


async def _kill_and_reap(proc: asyncio.subprocess.Process) -> None:
    _kill_group(proc)
    with contextlib.suppress(Exception):
        await asyncio.wait_for(proc.communicate(), 10)  # collect the exit and close the pipes


def _background(coro: Coroutine[Any, Any, Any]) -> None:
    """Run cleanup without making the caller wait (a stopped run must stop at once)."""
    task = asyncio.ensure_future(coro)
    _reaping.add(task)
    task.add_done_callback(_reaping.discard)


def _kill(proc: asyncio.subprocess.Process) -> None:
    """Kill a command that was stopped, in the background so the caller's cancellation isn't delayed."""
    _background(_kill_and_reap(proc))


async def _run(args: list[str], timeout: float, cwd: str | None = None, stdin: bytes | None = None) -> ExecResult:
    start = asyncio.ensure_future(
        asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL if stdin is None else asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    )
    try:
        # Shielded: cancelling process creation makes Python 3.12 wait for the process to exit.
        proc = await asyncio.shield(start)
    except asyncio.CancelledError:
        start.add_done_callback(lambda t: t.cancelled() or t.exception() or _kill(t.result()))
        raise
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin), timeout)
        return ExecResult(proc.returncode or 0, _clip(out), _clip(err))
    except TimeoutError:
        _kill_group(proc)
        out, err = await proc.communicate()
        return ExecResult(124, _clip(out), _clip(err), timed_out=True)
    except asyncio.CancelledError:
        _kill(proc)  # stopped by the user: don't leave the command running
        raise


class SandboxError(RuntimeError):
    pass


class SandboxProcess(ABC):
    """A process running inside a sandbox: bytes in on stdin, bytes out on stdout; stderr goes to the
    backend's log. Get one with `Sandbox.process()`, which also stops it."""

    @abstractmethod
    async def write(self, data: bytes) -> None:
        """Write to stdin. Raises BrokenPipeError once the process can't read any more."""

    @abstractmethod
    async def read(self) -> bytes:
        """The next chunk of stdout; b"" once stdout has ended."""

    @abstractmethod
    async def close_stdin(self) -> None:
        """Send end-of-file. Idempotent."""

    @property
    @abstractmethod
    def returncode(self) -> int | None:
        """The exit code, or None while the process runs."""

    @abstractmethod
    async def kill(self) -> None:
        """Kill the process and everything it started, inside the sandbox. Idempotent."""

    async def aclose(self) -> None:
        """Release the backend's resources (pipes, connections) once the process has ended."""
        return  # optional: nothing to release by default


async def _exited(proc: SandboxProcess, timeout: float) -> bool:
    # Poll rather than wait(): a child that inherited the pipes makes an exited process look alive.
    with anyio.move_on_after(timeout):
        while proc.returncode is None:  # noqa: ASYNC110 - an exit code has no event to wait on
            await anyio.sleep(0.01)
    return proc.returncode is not None


SWEEP_LOCK = "sandbox-sweep"
_using: Counter[int] = Counter()  # users whose sandbox this process is using right now
_locks: dict[int, asyncio.Lock] = {}


async def _touch(user_id: int) -> None:
    if config.settings.sandbox_idle_minutes > 0:
        await bus.current().touch(user_id)


async def _touch_later(user_id: int) -> None:
    try:
        await _touch(user_id)
    except Exception:  # noqa: BLE001 - the next round of the sweeper stamps it again
        log.exception("could not record sandbox use")


@contextlib.asynccontextmanager
async def using(user_id: int) -> AsyncIterator[None]:
    """The user's sandbox is in use for the block: it is not stopped while idle until the block ends."""
    _using[user_id] += 1
    try:
        await _touch(user_id)
        yield
    finally:
        _using[user_id] -= 1
        if not _using[user_id]:
            del _using[user_id]
        _background(_touch_later(user_id))  # idle from now; in the background so a stop isn't delayed


class Sandbox(ABC):
    kind = "base"
    isolated = False  # whether commands are kept from the host and from other users (shown in Settings)

    def __init__(self, user_id: int):
        self.user_id = user_id

    @classmethod
    async def running(cls) -> list[int]:
        """The users whose sandbox runs now. Only these are stopped while idle (none by default)."""
        return []

    @contextlib.asynccontextmanager
    async def locked(self) -> AsyncIterator[None]:
        """Hold this user's sandbox: callers in this process wait on the asyncio lock, other processes on
        the bus lock (they would otherwise race to create, start or stop the same sandbox)."""
        lock = _locks.setdefault(self.user_id, asyncio.Lock())
        async with lock, bus.current().hold(f"sandbox:{self.user_id}", timeout=420):
            yield

    async def ensure(self) -> None:
        """Make sure the sandbox runs. Raise SandboxError with a sentence for the user if it can't."""
        return  # optional: a sandbox that is always there needs nothing

    @abstractmethod
    async def run(self, command: str, timeout: int | None = None) -> ExecResult:
        """Run a shell command in the workspace and return its output. Called by `exec()` after `ensure()`.
        Cancelling it kills the command."""

    @abstractmethod
    async def spawn(self, argv: list[str], env: dict[str, str]) -> SandboxProcess:
        """Start argv in the workspace with env added. Called by `process()` after `ensure()`."""

    async def status(self) -> dict:
        return {"kind": self.kind, "isolated": self.isolated, "state": "ready"}

    async def reset(self) -> None:
        """Throw the sandbox away (the workspace stays); the next use starts a fresh one."""
        return  # optional: nothing to throw away by default

    async def stop(self) -> None:
        """Stop the sandbox, keeping it (and the workspace) for `ensure()` to start again. Called with the
        sandbox `locked()`. Idempotent."""
        return  # optional: a sandbox that costs nothing while idle stays as it is

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        """Run a shell command in the workspace and return its output. Cancelling it kills the command."""
        async with using(self.user_id):
            await self.ensure()
            return await self.run(command, timeout)

    @contextlib.asynccontextmanager
    async def process(self, argv: list[str], env: dict[str, str] | None = None) -> AsyncIterator[SandboxProcess]:
        """Run argv inside the sandbox for the duration of the block, then stop it as the MCP spec asks:
        close stdin, give it STOP_GRACE seconds to exit, then kill it and everything it started."""
        async with using(self.user_id):
            await self.ensure()
            proc = await self.spawn(argv, env or {})
            try:
                yield proc
            finally:
                with anyio.CancelScope(shield=True):  # a stopped run must not leave the process behind
                    await proc.close_stdin()
                    if not await _exited(proc, STOP_GRACE):
                        await proc.kill()
                        await _exited(proc, STOP_GRACE)
                    await proc.aclose()


class _HostProcess(SandboxProcess):
    """A process the backend started on its own host (directly, or as a provider CLI like `docker exec`)."""

    def __init__(self, proc: anyio.abc.Process):
        self._proc = proc

    async def write(self, data: bytes) -> None:
        assert self._proc.stdin
        try:
            await self._proc.stdin.send(data)
        except (anyio.BrokenResourceError, anyio.ClosedResourceError, OSError) as e:
            raise BrokenPipeError(str(e) or "process stdin is closed") from e

    async def read(self) -> bytes:
        assert self._proc.stdout
        try:
            return await self._proc.stdout.receive()
        except (anyio.EndOfStream, anyio.ClosedResourceError, anyio.BrokenResourceError, OSError):
            return b""

    async def close_stdin(self) -> None:
        assert self._proc.stdin
        with contextlib.suppress(anyio.BrokenResourceError, anyio.ClosedResourceError, OSError):
            await self._proc.stdin.aclose()

    @property
    def returncode(self) -> int | None:
        return self._proc.returncode

    async def kill(self) -> None:
        # Started with start_new_session, so its process group holds everything it started.
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(self._proc.pid, signal.SIGKILL)

    async def aclose(self) -> None:
        for stream in (self._proc.stdin, self._proc.stdout):
            if stream:
                with contextlib.suppress(Exception):
                    await stream.aclose()


async def _open_host_process(argv: list[str], env: dict[str, str] | None, cwd: str | None) -> anyio.abc.Process:
    try:
        return await anyio.open_process(argv, env=env, cwd=cwd, stderr=None, start_new_session=True)
    except OSError as e:
        raise SandboxError(f"Could not start {argv[0]}: {e.strerror or e}") from e


class LocalSandbox(Sandbox):
    kind = "local"

    async def run(self, command: str, timeout: int | None = None) -> ExecResult:
        cwd = str(workspace.workspace_dir(self.user_id))
        return await _run(["sh", "-c", command], timeout or config.settings.command_timeout, cwd=cwd)

    async def spawn(self, argv: list[str], env: dict[str, str]) -> SandboxProcess:
        base = {k: os.environ[k] for k in _HOST_ENV if k in os.environ}
        cwd = str(workspace.workspace_dir(self.user_id))
        return _HostProcess(await _open_host_process(argv, base | env, cwd))


# Commands run under this wrapper: it records its pid (the session leader of the `docker exec`) so a
# stop can kill the whole session inside the container. Killing the `docker exec` client alone leaves
# the command running there.
_TRACK = 'f=$1; shift; echo $$ > "$f"; "$@"; rc=$?; rm -f "$f"; exit $rc'
# Kills every process in the recorded session. Needs only sh and /proc, so any image works.
_KILL_SESSION = """
f=$1
for i in 1 2 3 4 5 6 7 8 9 10; do [ -s "$f" ] && break; sleep 0.2; done
p=$(cat "$f" 2>/dev/null) || exit 0
rm -f "$f"
for d in /proc/[0-9]*; do
  s=$(cat "$d/stat" 2>/dev/null) || continue
  s=${s##*) }
  set -- $s
  [ "$4" = "$p" ] && kill -KILL "${d#/proc/}" 2>/dev/null
done
exit 0
"""


def _pidfile() -> str:
    return f"/tmp/acf-{secrets.token_hex(8)}.pid"


class _TrackedProcess(_HostProcess):
    """A process started through a provider CLI's exec, under `_TRACK`."""

    def __init__(self, proc: anyio.abc.Process, sandbox: _ExecSandbox, pidfile: str):
        super().__init__(proc)
        self._sandbox, self._pidfile = sandbox, pidfile

    async def kill(self) -> None:
        await self._sandbox._kill_tracked(self._pidfile)
        await super().kill()


_UNITS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}


def parse_bytes(value: str) -> int:
    """A size as Docker writes it ("512m", "1g") in bytes."""
    m = re.fullmatch(r"(\d+)([bkmg]?)b?", value.strip().lower())
    if not m:
        raise ValueError(f"Bad size: {value}")
    return int(m.group(1)) * _UNITS[m.group(2) or "b"]


def _workspace_id(user_id: int) -> str:
    """Random id for this user's workspace folder. A sandbox built for another folder (data dir wiped, user id
    reused) carries a different id and gets replaced."""
    path = workspace.user_root(user_id) / "sandbox-id"
    workspace.workspace_dir(user_id)
    if not path.exists():
        path.write_text(secrets.token_hex(8))
    return path.read_text().strip()


def _owner(user_id: int) -> tuple[int, int]:
    """The uid and gid sandboxes run as: the workspace's owner, the app's own (non-root) user. Never root: root
    in a container is root on the host unless user namespaces remap it."""
    owner = workspace.workspace_dir(user_id).stat()
    if owner.st_uid == 0 or owner.st_gid == 0:
        raise SandboxError(
            "Sandboxes don't run as root. Run AI Chatbot Framework as a normal user, or make that user "
            "own the data folder."
        )
    return owner.st_uid, owner.st_gid


class _ExecSandbox(Sandbox):
    """A sandbox the backend reaches through a provider CLI's exec (`docker exec`, `kubectl exec`)."""

    isolated = True

    @abstractmethod
    def _exec_args(self, argv: list[str], env: dict[str, str], interactive: bool) -> list[str]:
        """The CLI command that runs argv in the sandbox's workspace with env added; stdin attached if
        interactive."""

    def _output(self, res: ExecResult) -> ExecResult:
        return res  # what the CLI adds to a command's output, taken out again

    async def _kill_tracked(self, pidfile: str) -> None:
        await _run(self._exec_args(["sh", "-c", _KILL_SESSION, "sh", pidfile], {}, False), 30)

    async def run(self, command: str, timeout: int | None = None) -> ExecResult:
        t = timeout or config.settings.command_timeout
        pidfile = _pidfile()
        # The backend enforces the deadline and kills the whole session; `timeout` inside the sandbox is a
        # backstop for when the backend itself goes away.
        argv = ["sh", "-c", _TRACK, "sh", pidfile, "timeout", "-s", "KILL", str(t + 30), "sh", "-c", command]
        try:
            res = self._output(await _run(self._exec_args(argv, {}, False), t))
        except asyncio.CancelledError:
            _background(self._kill_tracked(pidfile))  # stopped by the user
            raise
        if res.timed_out:
            await self._kill_tracked(pidfile)
        elif res.exit_code == 137:
            res.timed_out = True
        return res

    async def spawn(self, argv: list[str], env: dict[str, str]) -> SandboxProcess:
        pidfile = _pidfile()
        args = self._exec_args(["sh", "-c", _TRACK, "sh", pidfile, *argv], env, True)
        # The CLI gets the backend's environment (DOCKER_HOST, KUBECONFIG, …); the sandbox gets only env.
        return _TrackedProcess(await _open_host_process(args, None, None), self, pidfile)


class DockerSandbox(_ExecSandbox):
    kind = "docker"

    @property
    def name(self) -> str:
        return f"{config.settings.sandbox_prefix}-{self.user_id}"

    async def _inspect(self) -> tuple[str, str]:
        res = await _run(
            [
                "docker",
                "container",
                "inspect",
                "-f",
                '{{.State.Status}} {{index .Config.Labels "acf.workspace"}}',
                self.name,
            ],
            30,
        )
        if res.exit_code != 0:
            return "missing", ""
        state, _, ws = res.stdout.strip().partition(" ")
        return state, ws

    async def _state(self) -> str:
        return (await self._inspect())[0]

    async def _ensure_network(self) -> None:
        """Create the sandbox network if needed: a bridge with inter-container traffic off."""
        s = config.settings
        net = s.sandbox_network
        if net == "host" or net.startswith("container:"):
            raise SandboxError(f"ACF_SANDBOX_NETWORK={net} would share a network with the host or a container")
        if net in ("bridge", "none"):
            return
        if (await _run(["docker", "network", "inspect", net], 30)).exit_code == 0:
            return
        res = await _run(
            [
                "docker",
                "network",
                "create",
                "--driver",
                "bridge",
                "--label",
                "acf.sandbox=1",
                "-o",
                "com.docker.network.bridge.enable_icc=false",
                "-o",
                f"com.docker.network.bridge.name={s.sandbox_bridge}",
                net,
            ],
            60,
        )
        if res.exit_code != 0 and (await _run(["docker", "network", "inspect", net], 30)).exit_code != 0:
            raise SandboxError(f"Could not create the sandbox network: {res.stderr.strip() or res.stdout.strip()}")

    async def ensure(self) -> None:
        if not shutil.which("docker"):
            raise SandboxError("Docker CLI not found. Install Docker or set ACF_SANDBOX=local for development.")
        async with self.locked():  # one container per user
            state, ws_id = await self._inspect()
            expected = _workspace_id(self.user_id)
            if state != "missing" and ws_id != expected:
                await _run(["docker", "rm", "-f", self.name], 60)
                state = "missing"
            if state == "running":
                return
            started = time.monotonic()
            if state != "missing":
                res = await _run(["docker", "start", self.name], 60)
                if res.exit_code == 0:
                    telemetry.sandbox_started(time.monotonic() - started, "start")
                    return
                await _run(["docker", "rm", "-f", self.name], 60)
            s = config.settings
            uid, gid = _owner(self.user_id)
            await self._ensure_network()
            runtime = ["--runtime", s.sandbox_runtime] if s.sandbox_runtime else []
            args = [
                "docker",
                "run",
                "-d",
                "--name",
                self.name,
                "--label",
                "acf.sandbox=1",
                "--label",
                f"acf.user={self.user_id}",
                "--label",
                f"acf.workspace={expected}",
                "--hostname",
                "sandbox",
                "--user",
                f"{uid}:{gid}",
                "--memory",
                s.sandbox_memory,
                "--cpus",
                s.sandbox_cpus,
                "--pids-limit",
                str(PIDS_LIMIT),
                "--network",
                s.sandbox_network,
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                *runtime,
                "-v",
                f"{workspace.host_workspace_dir(self.user_id)}:{WORKDIR}",
                "-w",
                WORKDIR,
                "-e",
                "HOME=/workspace/.home",
                s.sandbox_image,
                "sleep",
                "infinity",
            ]
            res = await _run(args, 300)
            if res.exit_code != 0:
                raise SandboxError(f"Could not start sandbox: {res.stderr.strip() or res.stdout.strip()}")
            await _run(["docker", "exec", self.name, "mkdir", "-p", "/workspace/.home"], 30)
            telemetry.sandbox_started(time.monotonic() - started, "create")

    def _exec_args(self, argv: list[str], env: dict[str, str], interactive: bool) -> list[str]:
        args = ["docker", "exec", *(["-i"] if interactive else []), "-w", WORKDIR]
        for k, v in env.items():
            args += ["-e", f"{k}={v}"]
        return [*args, self.name, *argv]

    async def status(self) -> dict:
        state = await self._state() if shutil.which("docker") else "unavailable"
        return {
            "kind": self.kind,
            "isolated": self.isolated,
            "state": state,
            "name": self.name,
            "image": config.settings.sandbox_image,
        }

    async def reset(self) -> None:
        await _run(["docker", "rm", "-f", self.name], 60)

    @classmethod
    async def running(cls) -> list[int]:
        if not shutil.which("docker"):
            return []
        prefix = f"{config.settings.sandbox_prefix}-"
        # The Docker proxy lets the app list containers only with exactly these filters.
        filters = ["--filter", "label=acf.sandbox=1", "--filter", f"name=^{prefix}"]
        res = await _run(["docker", "ps", *filters, "--format", "{{.Names}}"], 30)
        if res.exit_code != 0:
            raise SandboxError(f"Could not list sandboxes: {res.stderr.strip() or res.stdout.strip()}")
        ids = [name.removeprefix(prefix) for name in res.stdout.split() if name.startswith(prefix)]
        return [int(i) for i in ids if i.isdigit()]

    async def stop(self) -> None:
        # No grace period: `sleep infinity` as PID 1 ignores SIGTERM and passes it on to no one.
        res = await _run(["docker", "stop", "-t", "0", self.name], 60)
        if res.exit_code != 0 and "No such container" not in res.stderr:
            raise SandboxError(f"Could not stop {self.name}: {res.stderr.strip() or res.stdout.strip()}")


POD_PREFIX = "acf-sandbox-"  # deploy/kubernetes/admission-policy.yaml admits only this + a user id
POD_READY_TIMEOUT = 300.0
# Container states a pod doesn't leave without being created again.
_STUCK = {
    "CreateContainerConfigError",
    "CreateContainerError",
    "ErrImageNeverPull",
    "ImagePullBackOff",
    "InvalidImageName",
    "RunContainerError",
}
_EXITED = re.compile(r"^command terminated with exit code \d+\n?\Z", re.MULTILINE)
PodState = Literal["missing", "starting", "ready", "failed", "terminating"]


@dataclass(frozen=True)
class Pod:
    """What the Kubernetes adapter needs to know about a sandbox pod, read from `kubectl get -o json`."""

    state: PodState
    workspace: str = ""  # the acf.workspace label: which workspace folder it was made for
    reason: str = ""  # why it isn't ready yet, or why it failed

    @classmethod
    def parse(cls, pod: dict | None) -> Pod:
        if not pod:
            return cls("missing")
        meta, status = pod.get("metadata") or {}, pod.get("status") or {}
        ws = (meta.get("labels") or {}).get("acf.workspace", "")
        if meta.get("deletionTimestamp"):
            return cls("terminating", ws)
        if status.get("phase") in ("Succeeded", "Failed"):
            return cls("failed", ws, status.get("message") or status.get("reason") or "the sandbox stopped")
        for c in status.get("containerStatuses") or []:
            waiting = (c.get("state") or {}).get("waiting") or {}
            if waiting.get("reason") in _STUCK:
                return cls("failed", ws, f"{waiting['reason']}: {waiting.get('message', '')}".strip(": "))
        conditions = {c.get("type"): c for c in status.get("conditions") or []}
        if (conditions.get("Ready") or {}).get("status") == "True":
            return cls("ready", ws)
        waiting_on = next((c for c in conditions.values() if c.get("status") == "False" and c.get("message")), {})
        return cls("starting", ws, waiting_on.get("message", ""))


class KubernetesSandbox(_ExecSandbox):
    """A pod per user in ACF_K8S_NAMESPACE. Its /workspace is the user's folder on the data volume (the
    ReadWriteMany claim ACF_K8S_DATA_CLAIM, mounted at ACF_DATA_DIR in the app's pods). Stopping deletes the pod;
    the files stay on the volume. kubectl uses the app's ServiceAccount in a cluster, or KUBECONFIG."""

    kind = "kubernetes"

    @property
    def name(self) -> str:
        return f"{POD_PREFIX}{self.user_id}"

    @staticmethod
    def _kubectl(*args: str) -> list[str]:
        return ["kubectl", "--namespace", config.settings.k8s_namespace, *args]

    async def _get(self) -> Pod:
        res = await _run(self._kubectl("get", "pod", self.name, "--ignore-not-found", "-o", "json"), 30)
        if res.exit_code != 0:
            raise SandboxError(f"Could not reach Kubernetes: {res.stderr.strip() or res.stdout.strip()}")
        return Pod.parse(json.loads(res.stdout) if res.stdout.strip() else None)

    async def _delete(self) -> None:
        res = await _run(self._kubectl("delete", "pod", self.name, "--ignore-not-found", "--wait", "--timeout=60s"), 90)
        if res.exit_code != 0:
            raise SandboxError(f"Could not stop {self.name}: {res.stderr.strip() or res.stdout.strip()}")

    def manifest(self, workspace_id: str) -> dict:
        s = config.settings
        uid, gid = _owner(self.user_id)
        sub_path = workspace.workspace_dir(self.user_id).relative_to(s.data_dir).as_posix()
        spec: dict[str, Any] = {
            "automountServiceAccountToken": False,
            "enableServiceLinks": False,
            "hostname": "sandbox",
            "restartPolicy": "Never",
            "terminationGracePeriodSeconds": 0,  # `sleep infinity` as PID 1 ignores SIGTERM
            "securityContext": {
                "runAsUser": uid,
                "runAsGroup": gid,
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "sandbox",
                    "image": s.sandbox_image,
                    "command": ["sleep", "infinity"],
                    "workingDir": WORKDIR,
                    "env": [{"name": "HOME", "value": "/workspace/.home"}],
                    "resources": {"limits": {"memory": str(parse_bytes(s.sandbox_memory)), "cpu": s.sandbox_cpus}},
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                        "privileged": False,
                        "runAsNonRoot": True,
                    },
                    "volumeMounts": [{"name": "workspace", "mountPath": WORKDIR, "subPath": sub_path}],
                }
            ],
            "volumes": [{"name": "workspace", "persistentVolumeClaim": {"claimName": s.k8s_data_claim}}],
        }
        if s.sandbox_runtime:
            spec["runtimeClassName"] = s.sandbox_runtime
        labels = {"acf.sandbox": "1", "acf.user": str(self.user_id), "acf.workspace": workspace_id}
        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.name, "namespace": s.k8s_namespace, "labels": labels},
            "spec": spec,
        }

    async def _wait_ready(self) -> None:
        deadline = time.monotonic() + POD_READY_TIMEOUT
        while (pod := await self._get()).state != "ready":
            if pod.state == "failed" or time.monotonic() > deadline:
                await self._delete()
                raise SandboxError(f"Could not start sandbox: {pod.reason or 'it did not become ready in time'}")
            await asyncio.sleep(0.5)

    async def ensure(self) -> None:
        if not shutil.which("kubectl"):
            raise SandboxError("kubectl not found. Install it in the app's image, or choose another ACF_SANDBOX.")
        async with self.locked():  # one pod per user
            pod = await self._get()
            expected = _workspace_id(self.user_id)
            if pod.state == "ready" and pod.workspace == expected:
                return
            started = time.monotonic()
            if pod.state != "starting" or pod.workspace != expected:  # a start in progress is waited for
                if pod.state != "missing":
                    await self._delete()
                manifest = self.manifest(expected)
                (workspace.workspace_dir(self.user_id) / ".home").mkdir(exist_ok=True)
                res = await _run(self._kubectl("apply", "-f", "-"), 60, stdin=json.dumps(manifest).encode())
                if res.exit_code != 0:
                    raise SandboxError(f"Could not start sandbox: {res.stderr.strip() or res.stdout.strip()}")
            await self._wait_ready()
            telemetry.sandbox_started(time.monotonic() - started, "create")

    def _exec_args(self, argv: list[str], env: dict[str, str], interactive: bool) -> list[str]:
        # kubectl exec has no -e: `env` adds the variables (the pod's own, like HOME, stay).
        added = ["env", *(f"{k}={v}" for k, v in env.items())] if env else []
        flags = ["-i"] if interactive else []
        return self._kubectl("exec", *flags, self.name, "-c", "sandbox", "--", *added, *argv)

    def _output(self, res: ExecResult) -> ExecResult:
        res.stderr = _EXITED.sub("", res.stderr)  # kubectl's own line about a non-zero exit
        return res

    async def status(self) -> dict:
        try:
            state = (await self._get()).state if shutil.which("kubectl") else "unavailable"
        except SandboxError:
            state = "unavailable"
        return {
            "kind": self.kind,
            "isolated": self.isolated,
            "state": "running" if state == "ready" else state,
            "name": self.name,
            "image": config.settings.sandbox_image,
        }

    async def reset(self) -> None:
        await self._delete()

    @classmethod
    async def running(cls) -> list[int]:
        if not shutil.which("kubectl"):
            return []
        res = await _run(cls._kubectl("get", "pods", "-l", "acf.sandbox=1", "-o", "json"), 30)
        if res.exit_code != 0:
            raise SandboxError(f"Could not list sandboxes: {res.stderr.strip() or res.stdout.strip()}")
        pods = [p["metadata"] for p in json.loads(res.stdout)["items"]]
        live = [m["name"] for m in pods if "deletionTimestamp" not in m]  # a stopping pod no longer counts
        ids = [name[len(POD_PREFIX) :] for name in live if name.startswith(POD_PREFIX)]
        return sorted(int(i) for i in ids if i.isdigit())

    async def stop(self) -> None:
        await self._delete()


def _sweep_period() -> float:
    """How often each process stamps its sandboxes in use and tries to sweep: well within the idle time."""
    return min(60.0, max(1.0, config.settings.sandbox_idle_minutes * 15))


async def _stop_if_idle(sbx: Sandbox, idle: float) -> bool:
    async with sbx.locked():  # a use that started meanwhile has stamped it, or waits for this
        now = time.time()
        if now - (await bus.current().last_used([sbx.user_id])).get(sbx.user_id, now) < idle:
            return False
        await sbx.stop()
        return True


async def sweep() -> list[int]:
    """One round: stamp the sandboxes this process is using, then, unless another process is sweeping,
    stop every sandbox no one has used for ACF_SANDBOX_IDLE_MINUTES. Returns the users stopped.
    Safe to run again after a crash: it starts from what runs now."""
    b = bus.current()
    for user_id in list(_using):
        await b.touch(user_id)
    idle = config.settings.sandbox_idle_minutes * 60
    if idle <= 0 or not await b.lock(SWEEP_LOCK):
        return []
    try:
        adapter = sandbox_class()
        users = await adapter.running()
        last = await b.last_used(users)
        stopped = []
        for user_id in users:
            if user_id not in last:  # started before anyone stamped it (a restart, an older version)
                await b.touch(user_id)
            elif time.time() - last[user_id] >= idle and user_id not in _using:
                try:
                    if await _stop_if_idle(adapter(user_id), idle):
                        stopped.append(user_id)
                except Exception:  # noqa: BLE001 - one broken sandbox must not keep the others running
                    log.exception("could not stop the sandbox of user %s", user_id)
        return stopped
    finally:
        await b.unlock(SWEEP_LOCK)


async def sweeper() -> None:
    """Every app process runs this, so each keeps its own sandboxes in use stamped."""
    while config.settings.sandbox_idle_minutes > 0:
        try:
            if stopped := await sweep():
                log.info("stopped idle sandboxes of users %s", stopped)
        except Exception:  # noqa: BLE001
            log.exception("sandbox sweep failed")
        await asyncio.sleep(_sweep_period())


_ADAPTERS: dict[str, type[Sandbox]] = {"docker": DockerSandbox, "kubernetes": KubernetesSandbox, "local": LocalSandbox}


def _checked(adapter: type[Sandbox], name: str) -> type[Sandbox]:
    """Refuse an adapter written before adapters implemented `run`: without one it can't be created, and
    with both its `exec` would skip `using()`, so the sandbox could be stopped as idle mid-command."""
    if adapter.exec is not Sandbox.exec:
        raise SandboxError(
            f"ACF_SANDBOX={name}: {adapter.__name__} overrides `exec`. Adapters implement `run` now: rename "
            "`exec` to `run`. `Sandbox.exec` wraps it to keep the sandbox in use while a command runs."
        )
    return adapter


def register_sandbox(kind: str, adapter: type[Sandbox]) -> None:
    """Make an adapter available as ACF_SANDBOX=<kind>."""
    _ADAPTERS[kind] = _checked(adapter, kind)


def sandbox_class(name: str | None = None) -> type[Sandbox]:
    """The adapter ACF_SANDBOX names: a registered kind, or `package.module:Class`."""
    name = (name or config.settings.sandbox).strip()
    if name in _ADAPTERS:
        return _ADAPTERS[name]
    module, _, attr = name.partition(":")
    if attr:
        try:
            adapter = getattr(importlib.import_module(module), attr)
        except (ImportError, AttributeError) as e:
            raise SandboxError(f"ACF_SANDBOX={name}: could not load the adapter ({e})") from e
        if isinstance(adapter, type) and issubclass(adapter, Sandbox):
            return _checked(adapter, name)
        raise SandboxError(f"ACF_SANDBOX={name} is not a Sandbox subclass")
    raise SandboxError(f"Unknown ACF_SANDBOX={name!r}. Use one of {', '.join(sorted(_ADAPTERS))} or module:Class.")


def get_sandbox(user_id: int) -> Sandbox:
    return sandbox_class()(user_id)


def workspace_path(user_id: int) -> Path:
    return workspace.workspace_dir(user_id)
