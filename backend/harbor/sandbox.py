"""One isolated sandbox per user.

DockerSandbox: a long-lived container per user (`harbor-sbx-<id>`) with the user's workspace mounted at
/workspace, resource limits, no Linux capabilities and no privilege escalation. Shell commands and
local (stdio) MCP servers both run inside it via `docker exec`.

LocalSandbox: runs commands directly on the host in the workspace folder. Development/testing only;
it is NOT isolated.
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path

from harbor import config, workspace

MAX_OUTPUT = 20_000
WORKDIR = "/workspace"


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


async def _run(args: list[str], timeout: float, cwd: str | None = None) -> ExecResult:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
        return ExecResult(proc.returncode or 0, _clip(out), _clip(err))
    except TimeoutError:
        proc.kill()
        out, err = await proc.communicate()
        return ExecResult(124, _clip(out), _clip(err), timed_out=True)


class SandboxError(RuntimeError):
    pass


class Sandbox:
    kind = "base"

    def __init__(self, user_id: int):
        self.user_id = user_id

    async def ensure(self) -> None: ...

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        raise NotImplementedError

    def stdio_command(
        self, command: str, args: list[str], env: dict[str, str]
    ) -> tuple[str, list[str], str | None]:
        """Return (command, args, cwd) that launches an MCP stdio server inside the sandbox."""
        raise NotImplementedError

    async def status(self) -> dict:
        return {"kind": self.kind, "state": "ready"}

    async def reset(self) -> None: ...


class LocalSandbox(Sandbox):
    kind = "local"

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        cwd = str(workspace.workspace_dir(self.user_id))
        return await _run(["sh", "-c", command], timeout or config.settings.command_timeout, cwd=cwd)

    def stdio_command(self, command, args, env):
        return command, args, str(workspace.workspace_dir(self.user_id))


_locks: dict[int, asyncio.Lock] = {}


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
                "inspect",
                "-f",
                '{{.State.Status}} {{index .Config.Labels "harbor.workspace"}}',
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

    async def ensure(self) -> None:
        if not shutil.which("docker"):
            raise SandboxError(
                "Docker CLI not found. Install Docker or set HARBOR_SANDBOX=local for development."
            )
        lock = _locks.setdefault(self.user_id, asyncio.Lock())
        async with lock:
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
            workspace.workspace_dir(self.user_id)  # make sure it exists
            args = [
                "docker",
                "run",
                "-d",
                "--name",
                self.name,
                "--label",
                "harbor.sandbox=1",
                "--label",
                f"harbor.user={self.user_id}",
                "--label",
                f"harbor.workspace={expected}",
                "--hostname",
                "sandbox",
                "--memory",
                s.sandbox_memory,
                "--cpus",
                s.sandbox_cpus,
                "--pids-limit",
                "512",
                "--network",
                s.sandbox_network,
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
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

    async def exec(self, command: str, timeout: int | None = None) -> ExecResult:
        await self.ensure()
        t = timeout or config.settings.command_timeout
        # `timeout` inside the container makes sure the process dies there too.
        res = await _run(
            [
                "docker",
                "exec",
                "-w",
                WORKDIR,
                self.name,
                "timeout",
                "-s",
                "KILL",
                str(t),
                "sh",
                "-c",
                command,
            ],
            t + 15,
        )
        if res.exit_code == 137 and not res.timed_out:
            res.timed_out = True
        return res

    def stdio_command(self, command, args, env):
        docker_args = ["exec", "-i", "-w", WORKDIR]
        for k, v in env.items():
            docker_args += ["-e", f"{k}={v}"]
        return "docker", [*docker_args, self.name, command, *args], None

    async def status(self) -> dict:
        state = await self._state() if shutil.which("docker") else "unavailable"
        return {"kind": self.kind, "state": state, "name": self.name, "image": config.settings.sandbox_image}

    async def reset(self) -> None:
        await _run(["docker", "rm", "-f", self.name], 60)


def get_sandbox(user_id: int) -> Sandbox:
    if config.settings.sandbox == "local":
        return LocalSandbox(user_id)
    return DockerSandbox(user_id)


def workspace_path(user_id: int) -> Path:
    return workspace.workspace_dir(user_id)
