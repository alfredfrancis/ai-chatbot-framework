"""What app processes share while chats run: who runs which chat, run events, steering, stop and locks.

The database holds everything that lasts (chats, messages, tasks). The bus holds what lives only while
work is in flight, so any process can serve any request:

- **Leases**: one run per chat across all processes. A run holds `claim(chat, run)` until it ends.
- **Inbox**: messages for a chat's run (`push` / `take`). Whoever sends a message pushes it, then tries to
  claim the chat; a run releases the chat and then checks the inbox again. Either way someone reads it.
- **Feeds**: a run's events, replayed to late subscribers and streamed live, from any process.
- **Signals**: steer (wake a thinking model), stop, and chat events; delivered to every process.
- **Locks** and **jobs**: short-lived names held by this process (a scheduled task's run, a review,
  creating a sandbox, background commands).

Adapters: `LocalBus` (in memory; one process, the default) and `RedisBus` (ACF_REDIS_URL; any number
of processes). Held leases, locks and jobs expire `bus_ttl` seconds after their process stops
refreshing them, so a crashed process frees its chats on its own.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

from acf import config

log = logging.getLogger("acf.bus")
FEED_KEEP = 300  # seconds a finished run's events stay readable (late subscribers, slow tails)
LOST = "The server running this chat stopped before the agent finished. Send your message again to continue."

# Signal handlers by op, shared by every bus instance (tests swap the bus; handlers stay registered).
_handlers: dict[str, Callable[[dict[str, Any]], None]] = {}


def handle(op: str, fn: Callable[[dict[str, Any]], None]) -> None:
    _handlers[op] = fn


def _dispatch(msg: dict[str, Any]) -> None:
    fn = _handlers.get(msg.get("op", ""))
    if fn is None:
        return
    try:
        fn(msg)
    except Exception:  # noqa: BLE001 - one bad handler must not stop the listener
        log.exception("bus signal %s failed", msg.get("op"))


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class Feed:
    """A run's events as this process sees them: everything so far, then live ones."""

    def __init__(self, chat_id: int, run_id: str):
        self.chat_id, self.run_id = chat_id, run_id
        self.events: list[dict[str, Any]] = []
        self._listeners: list[asyncio.Queue] = []

    def add(self, event: dict[str, Any]) -> None:
        if self.done:
            return
        self.events.append(event)
        for q in self._listeners:
            q.put_nowait(event)

    def listen(self) -> asyncio.Queue:
        """Register a listener now: it gets every event so far, then live ones."""
        q: asyncio.Queue = asyncio.Queue()
        for e in self.events:
            q.put_nowait(e)
        self._listeners.append(q)
        return q

    def unlisten(self, q: asyncio.Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    @property
    def result(self) -> dict[str, Any] | None:
        """The run's `done` event (stop_reason, error, ok, final_text) once it has ended."""
        return self.events[-1] if self.events and self.events[-1]["type"] == "done" else None

    @property
    def done(self) -> bool:
        return self.result is not None

    async def wait(self) -> dict[str, Any]:
        q = self.listen()
        try:
            while True:
                e = await q.get()
                if e["type"] == "done":
                    return e
        finally:
            self.unlisten(q)


class LocalBus:
    """Everything in this process. Correct for one process only."""

    kind = "local"

    def __init__(self) -> None:
        self.replica = new_id()
        self._leases: dict[int, str] = {}
        self._inbox: dict[int, list[dict[str, Any]]] = {}
        self._feeds: dict[str, Feed] = {}
        self._locks: set[str] = set()
        self._jobs: dict[str, int] = {}

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    # -- leases: one run per chat
    def claim(self, chat_id: int, run_id: str) -> bool:
        if chat_id in self._leases:
            return self._leases[chat_id] == run_id
        self._leases[chat_id] = run_id
        return True

    def owner(self, chat_id: int) -> str | None:
        return self._leases.get(chat_id)

    def release(self, chat_id: int, run_id: str) -> None:
        if self._leases.get(chat_id) == run_id:
            del self._leases[chat_id]

    # -- inbox
    def push(self, chat_id: int, item: dict[str, Any]) -> None:
        self._inbox.setdefault(chat_id, []).append(item)

    def take(self, chat_id: int) -> list[dict[str, Any]]:
        return self._inbox.pop(chat_id, [])

    def pending(self, chat_id: int) -> bool:
        return bool(self._inbox.get(chat_id))

    # -- feeds
    def feed(self, chat_id: int, run_id: str, *, local: bool = False) -> Feed:
        """The run's feed. `local`: this process runs it (its events come from `publish`)."""
        feed = self._feeds.get(run_id)
        if feed is None:
            feed = self._feeds[run_id] = Feed(chat_id, run_id)
            if not local:
                self._follow(feed)
        return feed

    def _follow(self, feed: Feed) -> None:
        """Fill a feed for a run another process runs. In one process there is none: it is lost."""
        if not feed.done:
            self._finish(feed, {"type": "done", "stop_reason": "end_turn", "ok": False, "error": LOST})

    def publish(self, feed: Feed, event: dict[str, Any]) -> None:
        feed.add(event)
        if event["type"] == "done":
            self._forget_later(feed.run_id)

    def _finish(self, feed: Feed, event: dict[str, Any]) -> None:
        feed.add(event)
        self._forget_later(feed.run_id)

    def _forget_later(self, run_id: str) -> None:
        with contextlib.suppress(RuntimeError):  # no running loop (sync tests): keep it
            asyncio.get_running_loop().call_later(FEED_KEEP, self._feeds.pop, run_id, None)

    # -- signals (every process, this one included)
    def signal(self, msg: dict[str, Any]) -> None:
        _dispatch(msg)

    # -- locks
    def lock(self, name: str) -> bool:
        if name in self._locks:
            return False
        self._locks.add(name)
        return True

    def unlock(self, name: str) -> None:
        self._locks.discard(name)

    @contextlib.asynccontextmanager
    async def hold(self, name: str, timeout: float = 600):
        """Wait for a lock, hold it for the block."""
        deadline = time.monotonic() + timeout
        while not self.lock(name):
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for {name}")
            await asyncio.sleep(0.1)
        try:
            yield
        finally:
            self.unlock(name)

    # -- background jobs
    def add_job(self, chat_id: int, job_id: str) -> None:
        self._jobs[job_id] = chat_id

    def drop_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

    def jobs(self, chat_id: int) -> set[str]:
        """Running background commands of the chat, in any process."""
        return {j for j, c in self._jobs.items() if c == chat_id}


# Compare-and-set helpers: only the holder may refresh or drop a key.
_REFRESH = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('pexpire', KEYS[1], ARGV[2]) end return 0"
_RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) end return 0"


class RedisBus(LocalBus):
    """Shared through Redis, so app processes can be added and removed at any time.

    Small calls (claim, push, take, signal) use a synchronous client, like the database: one quick
    round trip. Events are written by one background publisher in order (batched, so streamed text
    doesn't cost a round trip per word) and read by one tail per run per process.
    """

    kind = "redis"

    def __init__(self, url: str, prefix: str = "acf", ttl: float = 30) -> None:
        super().__init__()
        import redis
        import redis.asyncio as aredis

        self.prefix, self.ttl_ms = prefix, int(ttl * 1000)
        self.r = redis.Redis.from_url(url, decode_responses=True)
        self.ar = aredis.Redis.from_url(url, decode_responses=True)
        self._refresh = self.r.register_script(_REFRESH)
        self._release = self.r.register_script(_RELEASE)
        self._held: dict[str, str] = {}  # key -> value, refreshed while this process lives
        self._out: deque[tuple[str, dict[str, Any]]] = deque()
        self._wake = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        self._ready = asyncio.Event()

    def k(self, *parts: Any) -> str:
        return ":".join([self.prefix, *map(str, parts)])

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def start(self) -> None:
        self.r.ping()
        self._spawn(self._listen())
        self._spawn(self._publisher())
        self._spawn(self._heartbeat())
        await asyncio.wait_for(self._ready.wait(), 10)

    async def close(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        with contextlib.suppress(Exception):
            await self._flush()  # the last events (a stopped run's `done`)
        pipe = self.r.pipeline()
        for key, value in self._held.items():
            self._release(keys=[key], args=[value], client=pipe)
        pipe.execute()
        self._held.clear()
        await self.ar.aclose()
        self.r.close()

    # -- held keys
    def _take_key(self, key: str, value: str) -> bool:
        if self._held.get(key) == value:
            return True
        if self.r.set(key, value, nx=True, px=self.ttl_ms):
            self._held[key] = value
            return True
        return False

    def _drop_key(self, key: str) -> None:
        value = self._held.pop(key, None)
        if value is not None:
            self._release(keys=[key], args=[value])

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self.ttl_ms / 3000)
            held = list(self._held.items())
            if not held:
                continue
            try:
                pipe = self.r.pipeline()
                for key, value in held:
                    self._refresh(keys=[key], args=[value, self.ttl_ms], client=pipe)
                results = await asyncio.to_thread(pipe.execute)
            except Exception:  # noqa: BLE001 - Redis away for a moment: try again next beat
                log.exception("bus heartbeat failed")
                continue
            for (key, value), ok in zip(held, results, strict=True):
                if ok or self._held.get(key) != value:
                    continue
                # Expired while this process was cut off. Take it back if no one else has; otherwise
                # another process may run this chat now, so stop here rather than run it twice.
                if not self.r.set(key, value, nx=True, px=self.ttl_ms):
                    log.error("lost %s to another process", key)
                    self._held.pop(key, None)
                    if key.startswith(self.k("lease")):
                        _dispatch({"op": "lost", "chat_id": int(key.rsplit(":", 1)[1])})

    # -- leases
    def claim(self, chat_id: int, run_id: str) -> bool:
        return self._take_key(self.k("lease", chat_id), run_id)

    def owner(self, chat_id: int) -> str | None:
        return self.r.get(self.k("lease", chat_id))

    def release(self, chat_id: int, run_id: str) -> None:
        key = self.k("lease", chat_id)
        if self._held.get(key) == run_id:
            self._drop_key(key)

    # -- inbox
    def push(self, chat_id: int, item: dict[str, Any]) -> None:
        key = self.k("inbox", chat_id)
        self.r.pipeline().rpush(key, json.dumps(item)).expire(key, 86400).execute()

    def take(self, chat_id: int) -> list[dict[str, Any]]:
        key = self.k("inbox", chat_id)
        items, _ = self.r.pipeline(transaction=True).lrange(key, 0, -1).delete(key).execute()
        return [json.loads(i) for i in items]

    def pending(self, chat_id: int) -> bool:
        return bool(self.r.llen(self.k("inbox", chat_id)))

    # -- feeds
    def publish(self, feed: Feed, event: dict[str, Any]) -> None:
        super().publish(feed, event)
        self._out.append((feed.run_id, event))
        self._wake.set()

    async def _publisher(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            try:
                await self._flush()
            except Exception:  # noqa: BLE001
                log.exception("could not publish run events")
                await asyncio.sleep(0.5)
                self._wake.set()

    async def _flush(self) -> None:
        if not self._out:
            return
        batch = list(self._out)
        self._out.clear()
        pipe = self.ar.pipeline(transaction=False)
        for run_id, event in batch:
            key = self.k("events", run_id)
            pipe.xadd(key, {"e": json.dumps(event)})
            # A day while running (a process that dies mid-run leaves no `done`), a while once done.
            pipe.expire(key, FEED_KEEP if event["type"] == "done" else 86400)
        try:
            await pipe.execute()
        except BaseException:
            self._out.extendleft(reversed(batch))  # keep the order for the next try
            raise

    def _follow(self, feed: Feed) -> None:
        self._spawn(self._tail(feed))

    async def _tail(self, feed: Feed) -> None:
        """Copy a run's events from Redis into the feed until it is done (or its process is gone)."""
        key, last, quiet = self.k("events", feed.run_id), "0", 0
        try:
            while not feed.done:
                res = await self.ar.xread({key: last}, block=1000, count=1000)
                if res:
                    quiet = 0
                    for entry_id, fields in res[0][1]:
                        last = entry_id
                        feed.add(json.loads(fields["e"]))
                    continue
                # Nothing for a second. A run publishes `done` right after it releases the chat, so give
                # it a few seconds; after that, a chat no longer held by this run means its process died.
                if await self.ar.get(self.k("lease", feed.chat_id)) == feed.run_id:
                    quiet = 0
                else:
                    quiet += 1
                    if quiet >= 3:
                        feed.add({"type": "done", "stop_reason": "end_turn", "ok": False, "error": LOST})
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("could not follow run %s", feed.run_id)
            if not feed.done:
                feed.add({"type": "done", "stop_reason": "end_turn", "ok": False, "error": LOST})
        finally:
            self._forget_later(feed.run_id)

    # -- signals
    def signal(self, msg: dict[str, Any]) -> None:
        self.r.publish(self.k("signals"), json.dumps(msg))

    async def _listen(self) -> None:
        while True:
            try:
                async with self.ar.pubsub() as ps:
                    await ps.subscribe(self.k("signals"))
                    self._ready.set()
                    async for m in ps.listen():
                        if m.get("type") == "message":
                            _dispatch(json.loads(m["data"]))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("bus listener failed; reconnecting")
                await asyncio.sleep(1)

    # -- locks
    def lock(self, name: str) -> bool:
        return self._take_key(self.k("lock", name), self.replica)

    def unlock(self, name: str) -> None:
        self._drop_key(self.k("lock", name))

    # -- background jobs
    def add_job(self, chat_id: int, job_id: str) -> None:
        self._take_key(self.k("job", job_id), str(chat_id))
        self.r.sadd(self.k("jobs", chat_id), job_id)

    def drop_job(self, job_id: str) -> None:
        key = self.k("job", job_id)
        chat = self._held.get(key)
        self._drop_key(key)
        if chat is not None:
            self.r.srem(self.k("jobs", chat), job_id)

    def jobs(self, chat_id: int) -> set[str]:
        ids = sorted(self.r.smembers(self.k("jobs", chat_id)))
        if not ids:
            return set()
        pipe = self.r.pipeline()
        for j in ids:
            pipe.exists(self.k("job", j))
        live = {j for j, ok in zip(ids, pipe.execute(), strict=True) if ok}
        if gone := set(ids) - live:  # their process died: forget them
            self.r.srem(self.k("jobs", chat_id), *gone)
        return live


_bus: LocalBus | None = None


def current() -> LocalBus:
    """This process's bus (made from the settings on first use)."""
    global _bus
    if _bus is None:
        s = config.settings
        _bus = RedisBus(s.redis_url, s.redis_prefix, s.bus_ttl) if s.redis_url else LocalBus()
    return _bus


def use(bus: LocalBus | None) -> None:
    """Swap the bus (tests); None makes a new one from the settings on next use."""
    global _bus
    _bus = bus
