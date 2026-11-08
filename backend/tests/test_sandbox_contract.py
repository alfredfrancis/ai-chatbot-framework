"""The contract every sandbox adapter keeps (see acf/sandbox.py). Each test runs once per adapter;
a new adapter is added to ADAPTERS and must pass all of them. Docker runs need a daemon."""

import asyncio
import os
import subprocess
import time

import pytest

from acf import config, sandbox, workspace
from acf.sandbox import DockerSandbox, LocalSandbox, Sandbox, SandboxError, SandboxProcess
from tests.conftest import docker_available

IMAGE = os.environ.get("ACF_TEST_SANDBOX_IMAGE", "python:3.12-alpine")

ADAPTERS = [
    pytest.param(LocalSandbox, id="local"),
    pytest.param(
        DockerSandbox,
        id="docker",
        marks=[pytest.mark.docker, pytest.mark.skipif(not docker_available(), reason="Docker not available")],
    ),
]


@pytest.fixture(params=ADAPTERS)
def sbx(request, user, monkeypatch):
    adapter: type[Sandbox] = request.param
    monkeypatch.setattr(sandbox, "STOP_GRACE", 0.5)
    if adapter is DockerSandbox:
        monkeypatch.setattr(config.settings, "sandbox_image", IMAGE)
    yield adapter(user["id"])
    if adapter is DockerSandbox:
        subprocess.run(["docker", "rm", "-f", f"{config.settings.sandbox_prefix}-{user['id']}"], capture_output=True)


async def _read_all(proc: SandboxProcess) -> bytes:
    out = b""
    while chunk := await proc.read():
        out += chunk
    return out


async def _gone(sbx: Sandbox, marker: str, wait: float) -> bool:
    """Whether a command that would create `marker` after a delay was stopped before it could."""
    await asyncio.sleep(wait)
    return not (workspace.workspace_dir(sbx.user_id) / marker).exists()


async def test_exec_returns_output_and_exit_code(sbx):
    res = await sbx.exec("echo out; echo err >&2; exit 3")
    assert (res.exit_code, res.stdout, res.stderr, res.timed_out) == (3, "out\n", "err\n", False)


async def test_exec_runs_in_the_workspace(sbx):
    assert (await sbx.exec("echo hi > from-exec.txt")).exit_code == 0
    assert workspace.read_file(sbx.user_id, "from-exec.txt") == "hi\n"
    workspace.write_file(sbx.user_id, "from-backend.txt", "yo")
    assert (await sbx.exec("cat from-backend.txt")).stdout == "yo"


async def test_exec_timeout_kills_the_command(sbx):
    await sbx.ensure()
    started = time.monotonic()
    res = await sbx.exec("sleep 3; touch late-timeout", timeout=1)
    assert res.timed_out and time.monotonic() - started < 3
    assert await _gone(sbx, "late-timeout", 3)


async def test_cancelled_exec_kills_the_command_inside_the_sandbox(sbx):
    await sbx.ensure()
    task = asyncio.create_task(sbx.exec("sleep 2 & sleep 2; touch late-cancel"))
    await asyncio.sleep(0.8)
    started = time.monotonic()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert time.monotonic() - started < 1  # the caller doesn't wait for the kill
    assert await _gone(sbx, "late-cancel", 3)


async def test_process_streams_stdin_to_stdout(sbx):
    async with sbx.process(["cat"]) as proc:
        await proc.write(b"line one\n")
        await proc.write(b"line two\n")
        await proc.close_stdin()
        assert await _read_all(proc) == b"line one\nline two\n"
    assert proc.returncode == 0


async def test_process_gets_env_and_runs_in_the_workspace(sbx):
    async with sbx.process(["sh", "-c", 'printf %s "$ACF_T" > from-process.txt; printf done'], {"ACF_T": "x y"}) as p:
        assert await _read_all(p) == b"done"
    assert workspace.read_file(sbx.user_id, "from-process.txt") == "x y"


async def test_process_that_ignores_eof_is_killed_on_exit(sbx):
    # It ignores stdin closing and SIGTERM; leaving the block must still stop it and its children.
    script = 'trap "" TERM; (sleep 3; touch late-child) & sleep 3; touch late-parent'
    async with sbx.process(["sh", "-c", script]) as proc:
        await proc.write(b"ignored\n")
    assert proc.returncode is not None
    assert await _gone(sbx, "late-child", 3) and await _gone(sbx, "late-parent", 0)


async def test_killed_process_ends_its_stdout(sbx):
    async with sbx.process(["sh", "-c", "echo ready; sleep 30"]) as proc:
        assert (await proc.read()).startswith(b"ready")
        await proc.kill()
        assert await asyncio.wait_for(_read_all(proc), 10) == b""
    assert proc.returncode is not None


async def test_write_to_an_ended_process_raises_broken_pipe(sbx):
    async with sbx.process(["true"]) as proc:
        assert await asyncio.wait_for(_read_all(proc), 10) == b""
        with pytest.raises(BrokenPipeError):
            for _ in range(100):  # the first writes may still land in the pipe buffer
                await proc.write(b"x" * 65536)
                await asyncio.sleep(0.01)


# Choosing an adapter -----------------------------------------------------------------------------------


class _Custom(LocalSandbox):
    kind = "custom"


def test_adapters_are_chosen_by_kind_or_import_path(monkeypatch):
    assert sandbox.sandbox_class("local") is LocalSandbox and sandbox.sandbox_class("docker") is DockerSandbox
    assert sandbox.sandbox_class(f"{__name__}:_Custom") is _Custom
    monkeypatch.setattr(sandbox, "_ADAPTERS", dict(sandbox._ADAPTERS))
    sandbox.register_sandbox("custom", _Custom)
    monkeypatch.setattr(config.settings, "sandbox", "custom")
    assert isinstance(sandbox.get_sandbox(1), _Custom)


@pytest.mark.parametrize("name", ["nope", "acf.nope:Thing", "acf.config:Settings"])
def test_unknown_adapters_fail_with_a_clear_error(name):
    with pytest.raises(SandboxError, match="ACF_SANDBOX"):
        sandbox.sandbox_class(name)
