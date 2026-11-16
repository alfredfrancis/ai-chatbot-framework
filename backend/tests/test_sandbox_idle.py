"""Idle sandboxes are stopped and start again on their next use (`sandbox.sweep`). A recording adapter stands
in for Docker here; tests/test_docker_proxy.py runs the sweep against real containers, and the last test here
against real Kubernetes pods."""

from __future__ import annotations

import asyncio
import time

import pytest

from acf import bus, config, sandbox
from acf.sandbox import KubernetesSandbox, LocalSandbox
from tests.conftest import kubectl, kubernetes_available, plain_pod

IDLE = 0.4  # seconds


class Recording(LocalSandbox):
    """Runs commands on the host and keeps a list of the sandboxes that are up, like a provider would."""

    kind = "recording"
    up: set[int] = set()
    stops: list[int] = []
    broken: set[int] = set()

    async def ensure(self) -> None:
        Recording.up.add(self.user_id)

    @classmethod
    async def running(cls) -> list[int]:
        return sorted(cls.up)

    async def stop(self) -> None:
        if self.user_id in Recording.broken:
            raise RuntimeError("provider unavailable")
        Recording.stops.append(self.user_id)
        Recording.up.discard(self.user_id)


@pytest.fixture(autouse=True)
def recording(monkeypatch):
    sandbox.register_sandbox("recording", Recording)
    monkeypatch.setattr(config.settings, "sandbox", "recording")
    monkeypatch.setattr(config.settings, "sandbox_idle_minutes", IDLE / 60)
    Recording.up, Recording.stops, Recording.broken = set(), [], set()
    bus.use(bus.LocalBus())
    yield
    bus.use(None)


def sbx(user_id: int) -> Recording:
    return Recording(user_id)


async def test_an_idle_sandbox_is_stopped_and_starts_again_on_next_use():
    assert (await sbx(9001).exec("echo kept > kept.txt")).exit_code == 0
    await sbx(9002).exec("true")
    await asyncio.sleep(IDLE)
    await sbx(9002).exec("true")  # used again: its idle time starts over
    assert await sandbox.sweep() == [9001]
    assert await Recording.running() == [9002]
    assert (await sbx(9001).exec("cat kept.txt")).stdout == "kept\n"
    assert await Recording.running() == [9001, 9002]


async def test_nothing_in_use_is_stopped():
    """A command that runs past the idle time, a stdio MCP server, an agent's turn between commands."""
    command = asyncio.create_task(sbx(9011).exec(f"sleep {IDLE * 3}"))
    async with sbx(9012).process(["cat"]), sandbox.using(9013):
        await sbx(9013).ensure()
        await asyncio.sleep(IDLE * 2)
        assert await sandbox.sweep() == []
        assert not command.done()
    assert (await command).exit_code == 0
    await asyncio.sleep(IDLE)
    assert sorted(await sandbox.sweep()) == [9011, 9012, 9013]


async def test_a_use_in_flight_is_stamped_every_round_for_the_other_processes():
    async with sandbox.using(9021):
        started = time.time()
        await asyncio.sleep(IDLE)
        await sandbox.sweep()
        assert (await bus.current().last_used([9021]))[9021] >= started + IDLE


async def test_a_sandbox_no_one_was_seen_using_gets_the_whole_idle_time():
    """E.g. started before a restart, or by an older version: its idle time starts at the first sweep."""
    Recording.up.add(9031)
    assert await sandbox.sweep() == []
    await asyncio.sleep(IDLE)
    assert await sandbox.sweep() == [9031]


async def test_only_one_process_sweeps_at_a_time():
    await sbx(9041).exec("true")
    await asyncio.sleep(IDLE)
    assert await bus.current().lock(sandbox.SWEEP_LOCK)  # another process is sweeping
    assert await sandbox.sweep() == []
    await bus.current().unlock(sandbox.SWEEP_LOCK)
    assert await sandbox.sweep() == [9041]
    assert await sandbox.sweep() == []
    assert Recording.stops == [9041]  # one stop per sandbox


async def test_a_failed_stop_leaves_the_others_and_the_next_round_finishes():
    for user_id in (9051, 9052):
        await sbx(user_id).exec("true")
    await asyncio.sleep(IDLE)
    Recording.broken = {9051}
    assert await sandbox.sweep() == [9052]
    Recording.broken = set()
    assert await sandbox.sweep() == [9051]


async def test_idle_minutes_0_never_stops_a_sandbox(monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox_idle_minutes", 0)
    await sbx(9061).exec("true")
    Recording.up.add(9062)
    await asyncio.sleep(IDLE)
    assert await sandbox.sweep() == [] and await sandbox.sweep() == []
    await asyncio.wait_for(sandbox.sweeper(), 1)  # the sweeper doesn't run at all
    assert await Recording.running() == [9061, 9062] and Recording.stops == []


async def test_the_local_sandbox_is_never_stopped(monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox", "local")
    await LocalSandbox(9071).exec("echo hi > here.txt")
    await asyncio.sleep(IDLE)
    assert await sandbox.sweep() == []
    assert (await LocalSandbox(9071).exec("cat here.txt")).stdout == "hi\n"


def test_idle_minutes_must_not_be_negative(monkeypatch):
    monkeypatch.setenv("ACF_SANDBOX_IDLE_MINUTES", "-1")
    with pytest.raises(ValueError, match="ACF_SANDBOX_IDLE_MINUTES"):
        config.Settings()


@pytest.mark.kubernetes
@pytest.mark.skipif(not kubernetes_available(), reason="no Kubernetes cluster")
async def test_idle_kubernetes_sandboxes_are_deleted_and_come_back_with_their_files(k8s_sandbox, monkeypatch):
    monkeypatch.setattr(config.settings, "sandbox_idle_minutes", 1 / 60)
    idle, busy = KubernetesSandbox(9101), KubernetesSandbox(9102)
    # A pod with the sandbox label but not a sandbox's name is never listed, so never stopped.
    other = "acf-not-a-sandbox"
    kubectl("apply", "-f", "-", stdin=plain_pod(other, k8s_sandbox, {"acf.sandbox": "1"}))
    try:
        assert (await idle.exec("echo kept > kept.txt")).exit_code == 0
        async with busy.process(["cat"]):
            await asyncio.sleep(1)
            assert await sandbox.sweep() == [9101]
            assert await KubernetesSandbox.running() == [9102]
        assert kubectl("get", "pod", "-n", k8s_sandbox, idle.name, check=False).returncode != 0  # deleted
        assert kubectl("get", "pod", "-n", k8s_sandbox, other, check=False).returncode == 0
        assert (await idle.exec("cat kept.txt")).stdout == "kept\n"
        assert await KubernetesSandbox.running() == [9101, 9102]
    finally:
        kubectl("delete", "pod", "-n", k8s_sandbox, other, "--wait", check=False)
