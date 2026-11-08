"""The Redis bus: two instances in one process stand in for two app processes."""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import pytest

from acf import bus


@contextlib.asynccontextmanager
async def two_buses(redis_url: str, ttl: float = 1.0):
    prefix = f"acf-test-{uuid.uuid4().hex[:8]}"
    a, b = bus.RedisBus(redis_url, prefix, ttl), bus.RedisBus(redis_url, prefix, ttl)
    await a.start()
    await b.start()
    try:
        yield a, b
    finally:
        for x in (a, b):
            with contextlib.suppress(Exception):
                await x.close()


def crash(x: bus.RedisBus) -> None:
    """Stop refreshing without releasing anything, like a process that was killed."""
    for task in list(x._tasks):
        task.cancel()
    x._held.clear()


async def test_one_run_per_chat_across_processes(redis_url):
    async with two_buses(redis_url) as (a, b):
        assert a.claim(1, "run-a")
        assert not b.claim(1, "run-b")
        assert b.owner(1) == "run-a"
        b.release(1, "run-a")  # only the holder releases
        assert a.owner(1) == "run-a"
        a.release(1, "run-a")
        assert b.claim(1, "run-b") and a.owner(1) == "run-b"


async def test_a_held_lease_outlives_its_ttl_while_refreshed(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert a.claim(2, "run-a")
        await asyncio.sleep(1.5)  # 2.5 TTLs: the heartbeat keeps it
        assert b.owner(2) == "run-a" and not b.claim(2, "run-b")


async def test_a_dead_process_frees_its_chats_locks_and_jobs(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert a.claim(3, "run-a") and a.lock("task:9")
        a.add_job(3, "bg-1")
        assert b.jobs(3) == {"bg-1"} and not b.lock("task:9")
        crash(a)
        await asyncio.sleep(1.0)
        assert b.owner(3) is None and b.claim(3, "run-b")
        assert b.lock("task:9")
        assert b.jobs(3) == set()


async def test_inbox_is_shared_and_read_once(redis_url):
    async with two_buses(redis_url) as (a, b):
        a.push(4, {"kind": "text", "text": "one"})
        b.push(4, {"kind": "text", "text": "two"})
        assert a.pending(4)
        assert [i["text"] for i in b.take(4)] == ["one", "two"]
        assert a.take(4) == [] and not a.pending(4)


async def test_feed_replays_then_streams_to_another_process(redis_url):
    async with two_buses(redis_url) as (a, b):
        assert a.claim(5, "r5")
        local = a.feed(5, "r5", local=True)
        a.publish(local, {"type": "delta", "text": "hel"})
        await asyncio.sleep(0.2)
        remote = b.feed(5, "r5")  # joins late: gets the replay, then live events
        q = remote.listen()
        a.publish(local, {"type": "delta", "text": "lo"})
        a.release(5, "r5")
        a.publish(local, {"type": "done", "stop_reason": "end_turn", "error": None, "ok": True})
        got = [await asyncio.wait_for(q.get(), 5) for _ in range(3)]
        assert [e.get("text") for e in got[:2]] == ["hel", "lo"]
        assert got[2]["type"] == "done" and got[2]["ok"]
        assert b.feed(5, "r5") is remote  # one tail per run per process


async def test_feed_of_a_run_whose_process_died_ends_with_an_error(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert a.claim(6, "r6")
        a.publish(a.feed(6, "r6", local=True), {"type": "delta", "text": "partial"})
        await asyncio.sleep(0.2)
        crash(a)
        done = await asyncio.wait_for(b.feed(6, "r6").wait(), 15)
        assert done["error"] == bus.LOST and not done["ok"]


async def test_signals_reach_every_process(redis_url):
    seen: list[str] = []
    bus.handle("test-ping", lambda m: seen.append(m["from"]))
    async with two_buses(redis_url) as (a, b):
        a.signal({"op": "test-ping", "from": "a"})
        for _ in range(50):
            if len(seen) == 2:
                break
            await asyncio.sleep(0.05)
        assert seen == ["a", "a"]  # both processes (a included) heard it


async def test_hold_waits_for_another_process(redis_url):
    async with two_buses(redis_url) as (a, b):
        order: list[str] = []

        async def first():
            async with a.hold("sandbox:1"):
                order.append("a in")
                await asyncio.sleep(0.4)
                order.append("a out")

        async def second():
            await asyncio.sleep(0.1)
            async with b.hold("sandbox:1"):
                order.append("b in")

        await asyncio.gather(first(), second())
        assert order == ["a in", "a out", "b in"]
        with pytest.raises(TimeoutError):
            async with a.hold("sandbox:2"):
                async with b.hold("sandbox:2", timeout=0.3):
                    pass
