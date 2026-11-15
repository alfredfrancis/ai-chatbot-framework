"""The Redis bus: two instances in one process stand in for two app processes."""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import pytest
import redis

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
        assert await a.claim(1, "run-a")
        assert not await b.claim(1, "run-b")
        assert await b.owner(1) == "run-a"
        await b.release(1, "run-a")  # only the holder releases
        assert await a.owner(1) == "run-a"
        await a.release(1, "run-a")
        assert await b.claim(1, "run-b") and await a.owner(1) == "run-b"


async def test_a_held_lease_outlives_its_ttl_while_refreshed(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert await a.claim(2, "run-a")
        await asyncio.sleep(1.5)  # 2.5 TTLs: the heartbeat keeps it
        assert await b.owner(2) == "run-a" and not await b.claim(2, "run-b")


async def test_a_dead_process_frees_its_chats_locks_and_jobs(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert await a.claim(3, "run-a") and await a.lock("task:9")
        await a.add_job(3, "bg-1")
        assert await b.jobs(3) == {"bg-1"} and not await b.lock("task:9")
        crash(a)
        await asyncio.sleep(1.0)
        assert await b.owner(3) is None and await b.claim(3, "run-b")
        assert await b.lock("task:9")
        assert await b.jobs(3) == set()


async def test_a_lease_released_while_the_heartbeat_takes_it_back_stays_free(redis_url, monkeypatch):
    """The lease expired while this process was cut off; the heartbeat takes it back, and the run ends
    while that SET is on its way. No one holds the lease, so no one may find it taken."""
    async with two_buses(redis_url, ttl=3) as (a, b):
        assert await a.claim(5, "run-a")
        await a.r.delete(a.k("lease", 5))
        real_set = a.r.set

        async def run_ends_meanwhile(key, value, **kw):
            if key == a.k("lease", 5):
                await a.release(5, "run-a")
            return await real_set(key, value, **kw)

        monkeypatch.setattr(a.r, "set", run_ends_meanwhile)
        await asyncio.sleep(1.5)  # one beat
        assert await b.owner(5) is None
        assert await b.claim(5, "run-b")


async def test_the_heartbeat_outlives_a_redis_error(redis_url, monkeypatch):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert await a.claim(6, "run-a")
        await a.r.delete(a.k("lease", 6))  # expired while cut off: the next beat takes it back
        real_set, failures = a.r.set, [redis.ConnectionError("Redis went away")]

        async def flaky(key, value, **kw):
            if failures:
                raise failures.pop()
            return await real_set(key, value, **kw)

        monkeypatch.setattr(a.r, "set", flaky)
        await asyncio.sleep(1.0)  # five beats: the first fails
        assert not failures
        assert await b.owner(6) == "run-a"
        await asyncio.sleep(1.0)  # still refreshed, past its TTL
        assert await b.owner(6) == "run-a"


async def test_sandbox_use_is_shared(redis_url):
    async with two_buses(redis_url) as (a, b):
        assert await b.last_used([1, 2]) == {}
        await a.touch(1)
        first = (await b.last_used([1, 2]))[1]
        await asyncio.sleep(0.01)
        await b.touch(1)
        assert set(await a.last_used([1, 2])) == {1} and (await a.last_used([1]))[1] > first


@pytest.mark.parametrize("kind", ["local", "redis"])
async def test_a_lock_has_one_holder_within_a_process_too(kind, request):
    """A second lock() in the same process fails: else one unlock would free the lock for both holders."""
    async with contextlib.AsyncExitStack() as stack:
        if kind == "local":
            b = bus.LocalBus()
        else:
            b, _ = await stack.enter_async_context(two_buses(request.getfixturevalue("redis_url")))
        assert await b.lock("task:1") and await b.locked(["task:1", "task:2"]) == {"task:1"}
        assert not await b.lock("task:1")
        await b.unlock("task:1")
        assert await b.locked(["task:1"]) == set()
        assert await b.lock("task:1")


async def test_inbox_is_shared_and_read_once(redis_url):
    async with two_buses(redis_url) as (a, b):
        await a.push(4, {"kind": "text", "text": "one"})
        await b.push(4, {"kind": "text", "text": "two"})
        assert await a.pending(4)
        assert [i["text"] for i in await b.take(4)] == ["one", "two"]
        assert await a.take(4) == [] and not await a.pending(4)


async def test_feed_replays_then_streams_to_another_process(redis_url):
    async with two_buses(redis_url) as (a, b):
        assert await a.claim(5, "r5")
        local = a.feed(5, "r5", local=True)
        a.publish(local, {"type": "delta", "text": "hel"})
        await asyncio.sleep(0.2)
        remote = b.feed(5, "r5")  # joins late: gets the replay, then live events
        q = remote.listen()
        a.publish(local, {"type": "delta", "text": "lo"})
        await a.release(5, "r5")
        a.publish(local, {"type": "done", "stop_reason": "end_turn", "error": None, "ok": True})
        got = [await asyncio.wait_for(q.get(), 5) for _ in range(3)]
        assert [e.get("text") for e in got[:2]] == ["hel", "lo"]
        assert got[2]["type"] == "done" and got[2]["ok"]
        assert b.feed(5, "r5") is remote  # one tail per run per process


async def test_feed_of_a_run_whose_process_died_ends_with_an_error(redis_url):
    async with two_buses(redis_url, ttl=0.6) as (a, b):
        assert await a.claim(6, "r6")
        a.publish(a.feed(6, "r6", local=True), {"type": "delta", "text": "partial"})
        await asyncio.sleep(0.2)
        crash(a)
        done = await asyncio.wait_for(b.feed(6, "r6").wait(), 15)
        assert done["error"] == bus.LOST and not done["ok"]


async def test_signals_reach_every_process(redis_url):
    seen: list[str] = []
    bus.handle("test-ping", lambda m: seen.append(m["from"]))
    async with two_buses(redis_url) as (a, b):
        await a.signal({"op": "test-ping", "from": "a"})
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


async def test_a_slow_redis_holds_up_the_caller_not_the_event_loop(redis_url):
    async with two_buses(redis_url) as (a, _):
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.01)
                ticks += 1

        ticker = asyncio.create_task(tick())
        try:
            with redis.Redis.from_url(redis_url) as admin:
                admin.client_pause(400, all=False)  # writes wait 0.4 s; reads and this client go on
            started = asyncio.get_running_loop().time()
            await a.push(7, {"kind": "text", "text": "hi"})
            waited = asyncio.get_running_loop().time() - started
        finally:
            ticker.cancel()
        assert waited > 0.3  # the push did wait for Redis
        assert ticks > waited / 0.01 / 2  # and the loop ran other work all the while


async def test_calls_work_again_once_redis_drops_its_connections(redis_url):
    async with two_buses(redis_url) as (a, _):
        await a.push(8, {"kind": "text", "text": "before"})
        with redis.Redis.from_url(redis_url) as admin:  # what a Redis restart does to every pooled connection
            admin.client_kill_filter(_type="normal", skipme=True)
        await asyncio.sleep(0.2)
        await a.push(8, {"kind": "text", "text": "after"})
        assert [i["text"] for i in await a.take(8)] == ["before", "after"]


@pytest.mark.parametrize("kind", ["local", "redis"])
async def test_a_sighting_keeps_its_first_time_until_forgotten(kind, request):
    async with contextlib.AsyncExitStack() as stack:
        if kind == "local":
            a = b = bus.LocalBus()
        else:
            a, b = await stack.enter_async_context(two_buses(request.getfixturevalue("redis_url")))
        first = await a.seen("free:task:1", ttl=60)
        await asyncio.sleep(0.01)
        assert await b.seen("free:task:1", ttl=60) == first
        await b.forget(["free:task:1", "free:task:2"])
        assert await a.seen("free:task:1", ttl=60) > first
