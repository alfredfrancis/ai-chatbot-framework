"""Sandbox command execution: stopping a command must not wait for it, and must kill it."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from acf import workspace
from acf.sandbox import LocalSandbox


@pytest.mark.parametrize("delay", [0, 0.5], ids=["while-starting", "while-running"])
async def test_cancelled_command_stops_at_once_and_is_killed(user, delay):
    sbx = LocalSandbox(user["id"])
    marker = workspace.workspace_dir(user["id"]) / f"finished-{delay}"
    task = asyncio.create_task(sbx.exec(f"sleep 1.5; touch {marker.name}"))
    await asyncio.sleep(delay)
    started = time.monotonic()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert time.monotonic() - started < 1  # Python 3.12 used to wait for the process to exit
    await asyncio.sleep(2)
    assert not marker.exists()  # the command was killed, not left running


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # a killed child may linger as a zombie until its new parent reaps it
    stat = Path(f"/proc/{pid}/stat")
    return not (stat.exists() and stat.read_text().split(") ")[1].startswith("Z"))


async def test_stop_kills_child_processes_too(user):
    sbx = LocalSandbox(user["id"])
    pidfile = workspace.workspace_dir(user["id"]) / "child.pid"
    task = asyncio.create_task(sbx.exec(f"sleep 30 & echo $! > {pidfile.name}; wait"))
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        await asyncio.sleep(0.05)
    pid = int(pidfile.read_text())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.5)
    assert not _alive(pid)


async def test_timeout_does_not_wait_for_child_processes(user):
    started = time.monotonic()
    res = await LocalSandbox(user["id"]).exec("sleep 30 & wait", timeout=1)
    assert res.timed_out and time.monotonic() - started < 5
