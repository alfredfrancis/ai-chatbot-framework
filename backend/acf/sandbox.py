"""One isolated sandbox per user, behind a provider-agnostic port.

`Sandbox` is the port the rest of the app uses; each provider is an adapter. An adapter implements
four things: `ensure` (start the sandbox if needed), `exec` (run a shell command, return its output),
`spawn` (start a long-lived process and stream bytes to and from it, used for stdio MCP servers) and
`reset`. The rest of the app never knows which adapter it has.

The contract every adapter keeps (tests/test_sandbox_contract.py checks it for each one):
- The user's workspace (`workspace.workspace_dir`, owned by the backend) is the working directory
  of every command and process, mounted or synced so files are the same on both sides.
- A timeout, a cancelled `exec` and `SandboxProcess.kill` stop the command and everything it started
  inside the sandbox, not only the backend's handle on it.
- Secrets stay in the backend: an adapter only receives the commands and environment it is given.

Adapters:
- DockerSandbox: a long-lived container per user (`acf-sbx-<id>`) with the workspace bind-mounted at
  /workspace, resource limits, no Linux capabilities and no privilege escalation.
- LocalSandbox: runs on the host in the workspace folder. Development/testing only; NOT isolated.
Others register with `register_sandbox()` or are named as `ACF_SANDBOX=package.module:Class`.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import os
import secrets
import shutil
import signal
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import anyio.abc

from acf import bus, config, workspace

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


async def _run(args: list[str], timeout: float, cwd: str | None = None) -> ExecResult:
    start = asyncio.ensure_future(
        asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
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
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
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


class Sandbox(ABC):
    kind = "base"

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def ensure(self) -> None:
        """Make sure the sandbox runs. Raise SandboxError with a sentence for the user if it can't."""
        return  # optional: a sandbox that is always there needs nothing

    @abstractmethod
    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        """Run a shell command in the workspace and return its output. Cancelling it kills the command."""

    @abstractmethod
    async def spawn(self, argv: list[str], env: dict[str, str]) -> SandboxProcess:
        """Start argv in the workspace with env added. Called by `process()` after `ensure()`."""

    async def status(self) -> dict:
        return {"kind": self.kind, "state": "ready"}

    async def reset(self) -> None:
        """Throw the sandbox away (the workspace stays); the next use starts a fresh one."""
        return  # optional: nothing to throw away by default

    @contextlib.asynccontextmanager
    async def process(self, argv: list[str], env: dict[str, str] | None = None) -> AsyncIterator[SandboxProcess]:
        """Run argv inside the sandbox for the duration of the block, then stop it as the MCP spec asks:
        close stdin, give it STOP_GRACE seconds to exit, then kill it and everything it started."""
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

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        cwd = str(workspace.workspace_dir(self.user_id))
        return await _run(["sh", "-c", command], timeout or config.settings.command_timeout, cwd=cwd)

    async def spawn(self, argv: list[str], env: dict[str, str]) -> SandboxProcess:
        base = {k: os.environ[k] for k in _HOST_ENV if k in os.environ}
        cwd = str(workspace.workspace_dir(self.user_id))
        return _HostProcess(await _open_host_process(argv, base | env, cwd))


_locks: dict[int, asyncio.Lock] = {}

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


class _DockerProcess(_HostProcess):
    def __init__(self, proc: anyio.abc.Process, sandbox: DockerSandbox, pidfile: str):
        super().__init__(proc)
        self._sandbox, self._pidfile = sandbox, pidfile

    async def kill(self) -> None:
        await self._sandbox._kill_tracked(self._pidfile)
        await super().kill()


class DockerSandbox(Sandbox):
    kind = "docker"

    @property
    def name(self) -> str:
        return f"{config.settings.sandbox_prefix}-{self.user_id}"

    def _workspace_id(self) -> str:
        """Random id for this user's workspace folder. A container built for another folder
        (data dir wiped, user id reused) carries a different id and gets replaced."""
        path = workspace.user_root(self.user_id) / "sandbox-id"
        workspace.workspace_dir(self.user_id)
        if not path.exists():
            path.write_text(secrets.token_hex(8))
        return path.read_text().strip()

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
        lock = _locks.setdefault(self.user_id, asyncio.Lock())
        # One container per user: callers in this process wait on the asyncio lock, other processes on
        # the bus lock (they would otherwise race to create, replace or start the same container).
        async with lock, bus.current().hold(f"sandbox:{self.user_id}", timeout=420):
            state, ws_id = await self._inspect()
            expected = self._workspace_id()
            if state != "missing" and ws_id != expected:
                await _run(["docker", "rm", "-f", self.name], 60)
                state = "missing"
            if state == "running":
                return
            if state != "missing":
                res = await _run(["docker", "start", self.name], 60)
                if res.exit_code == 0:
                    return
                await _run(["docker", "rm", "-f", self.name], 60)
            s = config.settings
            # Run as the workspace's owner: the app's own (non-root) user. Never as root: root in a
            # container is root on the host unless the daemon remaps user namespaces.
            owner = workspace.workspace_dir(self.user_id).stat()
            if owner.st_uid == 0 or owner.st_gid == 0:
                raise SandboxError(
                    "Sandboxes don't run as root. Run AI Chatbot Framework as a normal user, or make that user "
                    "own the data folder."
                )
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
                f"{owner.st_uid}:{owner.st_gid}",
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

    async def _kill_tracked(self, pidfile: str) -> None:
        await _run(["docker", "exec", self.name, "sh", "-c", _KILL_SESSION, "sh", pidfile], 30)

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        await self.ensure()
        t = timeout or config.settings.command_timeout
        pidfile = _pidfile()
        # The backend enforces the deadline and kills the whole session; `timeout` inside the container is
        # a backstop for when the backend itself goes away.
        argv = ["timeout", "-s", "KILL", str(t + 30), "sh", "-c", command]
        try:
            res = await _run(["docker", "exec", "-w", WORKDIR, self.name, "sh", "-c", _TRACK, "sh", pidfile, *argv], t)
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
        args = ["docker", "exec", "-i", "-w", WORKDIR]
        for k, v in env.items():
            args += ["-e", f"{k}={v}"]
        args += [self.name, "sh", "-c", _TRACK, "sh", pidfile, *argv]
        # The docker client gets the backend's environment (DOCKER_HOST, …); the container gets only env.
        return _DockerProcess(await _open_host_process(args, None, None), self, pidfile)

    async def status(self) -> dict:
        state = await self._state() if shutil.which("docker") else "unavailable"
        return {"kind": self.kind, "state": state, "name": self.name, "image": config.settings.sandbox_image}

    async def reset(self) -> None:
        await _run(["docker", "rm", "-f", self.name], 60)


_ADAPTERS: dict[str, type[Sandbox]] = {"docker": DockerSandbox, "local": LocalSandbox}


def register_sandbox(kind: str, adapter: type[Sandbox]) -> None:
    """Make an adapter available as ACF_SANDBOX=<kind>."""
    _ADAPTERS[kind] = adapter


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
            return adapter
        raise SandboxError(f"ACF_SANDBOX={name} is not a Sandbox subclass")
    raise SandboxError(f"Unknown ACF_SANDBOX={name!r}. Use one of {', '.join(sorted(_ADAPTERS))} or module:Class.")


def get_sandbox(user_id: int) -> Sandbox:
    return sandbox_class()(user_id)


def workspace_path(user_id: int) -> Path:
    return workspace.workspace_dir(user_id)
