"""Several app processes behind one address: any of them serves any chat (run state lives in Redis).

Real `uvicorn` processes share the database, the data folder and a Redis; clients talk ACP to whichever
one they like, as they would behind a load balancer."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from websockets.asyncio.client import connect

from acf import workspace
from acf.db import Chat, Message, Task, session_scope, utcnow
from tests.acp_client import Acp, joined
from tests.conftest import free_port

BACKEND = Path(__file__).parents[1]
TTL = 1.5  # seconds before a dead process's chats are free


class Replica:
    def __init__(self, env: dict[str, str], name: str):
        self.name, self.port = name, free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.log = Path(env["ACF_DATA_DIR"]) / f"replica-{name}-{self.port}.log"
        with self.log.open("w") as out:
            self.proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "acf.main:app", "--port", str(self.port), "--log-level", "warning"],
                cwd=BACKEND,
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT,
            )

    def output(self) -> str:
        return self.log.read_text()

    def wait_ready(self) -> None:
        for _ in range(200):
            with contextlib.suppress(httpx.HTTPError):
                if httpx.get(f"{self.url}/api/health", timeout=1).status_code == 200:
                    return
            if self.proc.poll() is not None:
                raise RuntimeError(f"replica {self.name} exited")
            time.sleep(0.1)
        raise RuntimeError(f"replica {self.name} did not start")

    def stop(self, sig: int = signal.SIGTERM, wait: float = 30) -> None:
        if self.proc.poll() is None:
            self.proc.send_signal(sig)
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.proc.wait(wait)
        if self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()


@pytest.fixture(scope="module")
def cluster_env(redis_url, acf_env):
    return {
        **os.environ,
        "ACF_REDIS_URL": redis_url,
        "ACF_REDIS_PREFIX": f"acf-cluster-{uuid.uuid4().hex[:8]}",
        "ACF_BUS_TTL": str(TTL),
        "ACF_SCHEDULER": "true",
        "ACF_SCHEDULER_INTERVAL": "0.3",
        "ACF_SHUTDOWN_GRACE": "15",
        "ACF_FRONTEND_DIST": "/nonexistent",
        "PYTHONPATH": str(BACKEND),
    }


@pytest.fixture(scope="module")
def cluster(cluster_env):
    replicas = [Replica(cluster_env, "a"), Replica(cluster_env, "b")]
    try:
        for r in replicas:
            r.wait_ready()
        yield replicas
    finally:
        for r in replicas:
            r.stop()
        for r in replicas:  # a clean shutdown, and no errors along the way
            assert "Traceback" not in r.output(), r.output()


@pytest.fixture
def spare(cluster_env):
    """A third process, for tests that kill one."""
    r = Replica(cluster_env, "spare")
    try:
        r.wait_ready()
        yield r
    finally:
        r.stop(signal.SIGKILL)


class Ws:
    def __init__(self, ws):
        self.ws = ws

    async def send_text(self, text: str) -> None:
        await self.ws.send(text)

    async def receive_text(self) -> str | None:
        try:
            return await self.ws.recv()
        except Exception:  # noqa: BLE001 - closed
            return None


@contextlib.asynccontextmanager
async def acp_to(replica: Replica, cookie: str):
    async with connect(f"ws://127.0.0.1:{replica.port}/api/acp", additional_headers={"cookie": cookie}) as ws:
        conn = Acp(Ws(ws))
        try:
            yield conn
        finally:
            conn.close()


@pytest.fixture
async def account(cluster):
    """A signed-in user: (cookie, user id), made through replica a."""
    email = f"cluster-{uuid.uuid4().hex[:8]}@example.com"
    async with httpx.AsyncClient(base_url=cluster[0].url) as c:
        r = await c.post("/api/auth/signup", json={"email": email, "password": "correct horse", "name": "Ana"})
        assert r.status_code == 200, r.text
        return f"acf_session={c.cookies['acf_session']}", r.json()["user"]["id"]


def text_prompt(sid: str, text: str) -> dict:
    return {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}


def agent_texts(acp: Acp, sid: str) -> list[str]:
    return list(joined([u for u in acp.updates(sid) if u["sessionUpdate"] == "agent_message_chunk"]).values())


def turn_end(sid: str):
    return lambda n: n.get("method") == "_acf/turn_end" and n["params"]["sessionId"] == sid


def stored(chat_id: int, role: str = "assistant") -> list[str]:
    with session_scope() as db:
        return [m.content for m in db.query(Message).filter_by(chat_id=chat_id, role=role).order_by(Message.id)]


async def test_a_run_on_one_process_streams_to_a_client_on_another(cluster, account):
    a, b = cluster
    cookie, _ = account
    async with acp_to(a, cookie) as on_a, acp_to(b, cookie) as on_b:
        sid = (await on_a.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        sent = asyncio.create_task(on_a.request("session/prompt", text_prompt(sid, "typing: one two three four five")))
        await asyncio.sleep(0.6)
        loaded = await on_b.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        assert loaded["_meta"]["acf"]["running"] is True
        async with httpx.AsyncClient(base_url=b.url, headers={"cookie": cookie}) as http:
            assert (await http.get(f"/api/chats/{sid}")).json()["running"] is True
        assert (await sent)["stopReason"] == "end_turn"
        end = await on_b.wait_for(turn_end(sid))
        assert "error" not in end["params"]
        # B saw the answer stream in, word by word, as one message.
        assert agent_texts(on_b, sid)[-1] == "Echo: one two three four five"
        assert len([u for u in on_b.updates(sid) if u["sessionUpdate"] == "agent_message_chunk"]) > 1
        async with httpx.AsyncClient(base_url=b.url, headers={"cookie": cookie}) as http:
            assert (await http.get(f"/api/chats/{sid}")).json()["running"] is False


async def test_steer_and_stop_from_another_process(cluster, account):
    a, b = cluster
    cookie, _ = account
    async with acp_to(a, cookie) as on_a, acp_to(b, cookie) as on_b:
        sid = (await on_a.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        first = asyncio.create_task(on_a.request("session/prompt", text_prompt(sid, "slow: 4 first")))
        await asyncio.sleep(0.8)
        # The model is still thinking on A: a message sent through B restarts it with the new message.
        t0 = time.monotonic()
        second = await on_b.request("session/prompt", text_prompt(sid, "steered through b"))
        assert second["stopReason"] == "end_turn" and (await first)["stopReason"] == "end_turn"
        assert time.monotonic() - t0 < 3.5  # it didn't wait out the slow call
        assert stored(int(sid)) == ["Echo: steered through b"]
        assert stored(int(sid), "user") == ["slow: 4 first", "steered through b"]

        long = asyncio.create_task(on_a.request("session/prompt", text_prompt(sid, "slow: 30 never")))
        await asyncio.sleep(0.8)
        t0 = time.monotonic()
        await on_b.notify("session/cancel", {"sessionId": sid})
        assert (await asyncio.wait_for(long, 10))["stopReason"] == "cancelled"
        assert time.monotonic() - t0 < 5


async def test_a_background_command_wakes_the_agent_for_clients_anywhere(cluster, account):
    a, b = cluster
    cookie, user_id = account
    async with acp_to(a, cookie) as on_a, acp_to(b, cookie) as on_b:
        sid = (await on_a.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        await on_b.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        # The command finishes only once the first turn has ended, so its note starts a new run.
        wait = "while [ ! -f go ]; do sleep 0.1; done; echo cluster-bg"
        cmd = json.dumps({"command": wait, "background": True})
        await on_a.request("session/prompt", text_prompt(sid, f"tool: bash {cmd}"))
        (workspace.workspace_dir(user_id) / "go").write_text("")
        await on_b.wait_for(lambda n: n.get("method") == "_acf/turn_start" and n["params"]["sessionId"] == sid, 15)
        await on_b.wait_for(turn_end(sid), 15)
        assert any("cluster-bg" in t for t in agent_texts(on_b, sid))
        assert any(m.startswith("Background done") for m in stored(int(sid)))


async def test_a_due_task_runs_once_across_processes(cluster, account):
    cookie, user_id = account
    with session_scope() as db:
        task = Task(user_id=user_id, name="Once", prompt="hello from the schedule", schedule="0 0 1 1 *")
        task.next_run_at = utcnow() - timedelta(seconds=1)
        db.add(task)
        db.flush()
        task_id = task.id
    for _ in range(100):
        with session_scope() as db:
            if db.get(Task, task_id).last_status == "ok":
                break
        await asyncio.sleep(0.1)
    await asyncio.sleep(1.5)  # several more ticks of both schedulers
    with session_scope() as db:
        chats = db.query(Chat).filter_by(task_id=task_id).all()
        assert db.get(Task, task_id).last_status == "ok"
    assert len(chats) == 1
    assert stored(chats[0].id) == ["Echo: hello from the schedule"]


async def test_scaling_in_lets_running_agents_finish(cluster, account, spare):
    _, b = cluster
    cookie, _ = account
    async with acp_to(spare, cookie) as on_spare, acp_to(b, cookie) as on_b:
        sid = (await on_spare.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        sent = asyncio.create_task(on_spare.request("session/prompt", text_prompt(sid, "slow: 2 finished anyway")))
        await asyncio.sleep(0.5)
        await on_b.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        spare.proc.send_signal(signal.SIGTERM)  # its client is cut off; the agent keeps going
        end = await on_b.wait_for(turn_end(sid), 20)
        assert "error" not in end["params"]
        sent.cancel()  # its connection was closed by the shutdown
    # uvicorn re-raises the signal once it has shut down cleanly
    assert await asyncio.to_thread(spare.proc.wait, 20) in (0, -signal.SIGTERM)
    assert "Traceback" not in spare.output() and "shutdown failed" not in spare.output()
    assert stored(int(sid)) == ["Echo: finished anyway"]


async def test_a_process_that_dies_frees_its_chats(cluster, account, spare):
    _, b = cluster
    cookie, _ = account
    async with acp_to(spare, cookie) as on_spare, acp_to(b, cookie) as on_b:
        sid = (await on_spare.request("session/new", {"cwd": "/", "mcpServers": []}))["sessionId"]
        cmd = json.dumps({"command": "sleep 30", "background": True})
        await on_spare.request("session/prompt", text_prompt(sid, f"tool: bash {cmd}"))
        asyncio.create_task(on_spare.request("session/prompt", text_prompt(sid, "slow: 30 lost")))
        await asyncio.sleep(0.8)
        await on_b.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        spare.proc.send_signal(signal.SIGKILL)
        end = await on_b.wait_for(turn_end(sid), TTL + 10)
        assert "stopped before the agent finished" in end["params"]["error"]
        # The chat is free again: the next message runs on B, with the lost work closed off in the history.
        reply = await on_b.request("session/prompt", text_prompt(sid, "back again"))
        assert reply["stopReason"] == "end_turn"
        assert stored(int(sid))[-1] == "Echo: back again"
        notes = stored(int(sid), "user")
        assert any("ended when the server restarted" in n for n in notes)
