"""OpenTelemetry: the span tree of a turn, the metrics, nothing exported by default, no content anywhere."""

import asyncio
import io
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from acf import config, logs, telemetry
from tests.acp_client import acp_connect
from tests.conftest import free_port, prompt, send, serve

BACKEND = Path(__file__).resolve().parents[1]


class Otel:
    def __init__(self) -> None:
        self.exporter = InMemorySpanExporter()
        tracer_provider = TracerProvider()
        tracer_provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.reader = InMemoryMetricReader()
        telemetry.install(tracer_provider, MeterProvider(metric_readers=[self.reader]))

    def spans(self, name: str | None = None) -> list:
        return [s for s in self.exporter.get_finished_spans() if name is None or s.name == name]

    def points(self, name: str) -> list:
        data = self.reader.get_metrics_data()
        return [
            p
            for rm in (data.resource_metrics if data else [])
            for sm in rm.scope_metrics
            for m in sm.metrics
            if m.name == name
            for p in m.data.data_points
        ]

    def value(self, name: str, **attrs) -> float:
        return sum(p.value for p in self.points(name) if dict(p.attributes) == attrs)


@pytest.fixture
def otel():
    o = Otel()
    yield o
    telemetry.reset()


def parent_of(span, spans):
    return next((s for s in spans if span.parent and s.context.span_id == span.parent.span_id), None)


def ancestors(span, spans) -> list[str]:
    out = []
    while (span := parent_of(span, spans)) is not None:
        out.append(span.name)
    return out


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


async def test_a_turn_is_one_tree(client, user, otel):
    chat_id = await new_chat(client)
    await send(client, chat_id, "run: echo hi")
    spans = otel.spans()
    (run,) = otel.spans("acf.run")
    (turn,) = otel.spans("acf.turn")
    assert parent_of(turn, spans) is run
    assert {s.trace_id for s in [s.context for s in spans if s.name.startswith("acf.")]} == {run.context.trace_id}
    llm = otel.spans("acf.llm")
    assert len(llm) == 2 and all(parent_of(s, spans) is turn for s in llm)  # the call, then the answer
    assert all(s.attributes["acf.llm.purpose"] == "turn" for s in llm)
    (tool,) = otel.spans("acf.tool")
    assert parent_of(tool, spans) is turn and tool.attributes["acf.tool.name"] == "bash"
    (exec_,) = otel.spans("acf.sandbox.exec")
    assert parent_of(exec_, spans) is tool and exec_.attributes["process.exit_code"] == 0
    (follow,) = otel.spans("acf.follow")  # the ACP connection that forwarded the run
    assert parent_of(follow, spans) is run and follow.attributes["acf.run.id"] == run.attributes["acf.run.id"]
    assert run.attributes["acf.run.outcome"] == "end_turn" and run.status.status_code is StatusCode.UNSET


async def test_runs_active_goes_up_and_back_down(client, user, otel):
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp:
        turn = asyncio.create_task(prompt(acp, chat_id, "slow: 1 waiting"))
        for _ in range(50):
            if otel.value("acf.runs.active") == 1:
                break
            await asyncio.sleep(0.05)
        assert otel.value("acf.runs.active") == 1
        assert otel.value("acf.acp.connections") == 1
        await turn
    assert otel.value("acf.runs.active") == 0
    assert otel.value("acf.acp.connections") == 0
    (duration,) = [p for p in otel.points("acf.run.duration") if p.attributes == {"outcome": "end_turn"}]
    assert duration.count == 1 and duration.sum >= 1


async def test_tokens_by_provider_and_kind(client, user, otel):
    chat_id = await new_chat(client)
    await send(client, chat_id, "hello")
    (llm,) = otel.spans("acf.llm")
    # The fake Anthropic API reports 10 output tokens per answer and a quarter of the request size as input.
    assert otel.value("acf.llm.tokens", provider="anthropic", kind="output") == 10
    assert otel.value("acf.llm.tokens", provider="anthropic", kind="input") > 100
    assert llm.attributes["gen_ai.usage.output_tokens"] == 10
    assert {tuple(sorted(p.attributes)) for p in otel.points("acf.llm.tokens")} == {("kind", "provider")}


async def test_failing_tool_marks_its_span_and_counts(client, user, otel):
    chat_id = await new_chat(client)
    await send(client, chat_id, "read: no/such/file.txt")
    (tool,) = otel.spans("acf.tool")
    assert tool.status.status_code is StatusCode.ERROR and tool.attributes["error.type"] == "tool_error"
    assert otel.value("acf.tool.calls", tool="read", outcome="error") == 1
    await send(client, chat_id, "run: echo fine")
    assert otel.value("acf.tool.calls", tool="bash", outcome="ok") == 1


async def test_sub_agent_spans_are_children_of_the_turn(client, user, otel):
    chat_id = await new_chat(client)
    args = {"description": "Look around", "prompt": "run: echo from-helper"}
    await send(client, chat_id, f"tool: agent {json.dumps(args)}")
    spans = otel.spans()
    sub_llm = [s for s in otel.spans("acf.llm") if s.attributes["acf.llm.purpose"] == "subagent"]
    assert sub_llm and all(ancestors(s, spans)[:3] == ["acf.tool", "acf.turn", "acf.run"] for s in sub_llm)
    bash = next(s for s in otel.spans("acf.tool") if s.attributes["acf.tool.name"] == "bash")
    assert ancestors(bash, spans) == ["acf.tool", "acf.turn", "acf.run"]
    assert parent_of(bash, spans).attributes["acf.tool.name"] == "agent"


async def test_no_content_or_key_in_any_attribute(client, user, otel):
    chat_id = await new_chat(client)
    await send(client, chat_id, "run: echo private-words-4815")
    await client.get("/api/chats?code=oauth-code-1623")
    exported = [
        {"name": s.name, "attributes": dict(s.attributes), "events": [dict(e.attributes) for e in s.events]}
        for s in otel.spans()
    ]
    names = ("acf.llm.tokens", "acf.tool.calls", "acf.run.duration", "acf.runs.active", "acf.acp.connections")
    exported += [dict(p.attributes) for n in names for p in otel.points(n)]
    text = json.dumps(exported, default=str)
    assert "acf.sandbox.exec" in text and "acf.llm" in text  # the dump has something to search
    for secret in ("private-words-4815", "echo", "oauth-code-1623", config.settings.llm_api_key):
        assert secret not in text


async def test_http_span_is_named_by_route_without_query(client, user, otel):
    r = await client.get("/api/chats?code=oauth-code-42", headers={"traceparent": f"00-{'ab' * 16}-{'cd' * 8}-01"})
    assert r.status_code == 200
    (server,) = [s for s in otel.spans() if s.name.startswith("GET")]
    assert server.name == "GET /api/chats" and server.attributes["http.response.status_code"] == 200
    assert format(server.context.trace_id, "032x") == "ab" * 16  # continues the caller's trace
    assert "oauth-code-42" not in json.dumps(dict(server.attributes))


async def test_a_run_started_inside_another_span_is_a_root_with_a_link(otel):
    """A run started from a tool (a background job) or a request (an app action) begins its own trace,
    linked to where it started, so chains of jobs don't grow one endless trace."""
    with telemetry.span("acf.tool") as starter:
        with telemetry.run("run-2", 1):
            pass
    with telemetry.run("run-3", 1):
        pass
    linked, alone = otel.spans("acf.run")
    assert linked.parent is None and linked.context.trace_id != starter.get_span_context().trace_id
    assert [link.context.span_id for link in linked.links] == [starter.get_span_context().span_id]
    assert alone.parent is None and not alone.links


async def test_log_lines_carry_the_trace_id(client, user, otel, monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(config.settings, "log_format", "json")
    logs.configure("json")
    handler = next(h for h in logging.getLogger().handlers if getattr(h, "_acf", False))
    handler.setStream(buf)
    try:
        chat_id = await new_chat(client)
        await send(client, chat_id, "hi")
    finally:
        logs.configure("text")
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    (run,) = otel.spans("acf.run")
    started = next(x for x in lines if x["message"] == "run started")
    assert started["trace_id"] == format(run.context.trace_id, "032x")
    assert len(started["span_id"]) == 16
    followed = next(x for x in lines if x["message"] == "following run")  # the connection forwarding the run
    assert followed["trace_id"] == started["trace_id"]


def test_off_without_an_endpoint():
    """No OTLP endpoint: setup does nothing and no exporter thread starts (so nothing can be sent)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_")}
    code = (
        "import threading; import acf.main; from acf import telemetry\n"
        "print(telemetry.setup(), telemetry.enabled(), sorted(t.name for t in threading.enumerate()))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True)
    assert out.stdout.split() == ["False", "False", "['MainThread']"], out.stdout + out.stderr


def test_global_providers_stay_unset(monkeypatch):
    """Libraries that switch on with a global provider (FastAPI's native telemetry records query strings) stay off."""
    from opentelemetry import metrics, trace

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{free_port()}")
    assert telemetry.setup()
    try:
        assert type(trace.get_tracer_provider()).__name__ == "ProxyTracerProvider"
        assert type(metrics.get_meter_provider()).__name__ == "_ProxyMeterProvider"
    finally:
        telemetry.shutdown(1)


async def test_off_adds_no_events_to_a_run(client, user):
    from acf.agent import loop as agent
    from acf.db import User, session_scope

    assert not telemetry.enabled()
    with session_scope() as db:
        me = db.get(User, user["id"])
    feed, _ = await agent.start(me, await new_chat(client), "hi")
    await feed.wait()
    assert "trace" not in {e["type"] for e in feed.events}


@pytest.fixture
def receiver():
    from tests.fakes import fake_otlp

    port = free_port()
    server = serve(fake_otlp.app, port)
    httpx.delete(f"http://127.0.0.1:{port}/_received")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


async def test_exports_over_otlp_http(client, user, receiver, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", receiver)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    assert telemetry.setup()
    try:
        chat_id = await new_chat(client)
        await send(client, chat_id, "run: echo exported")
    finally:
        await asyncio.to_thread(telemetry.shutdown, 10)
    async with httpx.AsyncClient() as c:
        got = (await c.get(f"{receiver}/_received")).json()
    assert got["requests"]["traces"] >= 1 and got["requests"]["metrics"] >= 1
    names = {s["name"] for s in got["spans"]}
    assert {"acf.run", "acf.turn", "acf.llm", "acf.tool", "acf.sandbox.exec"} <= names
    assert {s["service"] for s in got["spans"]} == {"acf"}
    (turn,) = [s for s in got["spans"] if s["name"] == "acf.turn"]
    children = {s["name"] for s in got["spans"] if s["parent_span_id"] == turn["span_id"]}
    assert {"acf.llm", "acf.tool"} <= children
    assert {p["name"] for p in got["metrics"]} >= {"acf.runs.active", "acf.tool.calls", "acf.llm.tokens"}


async def test_shutdown_is_bounded_with_the_collector_down(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"http://127.0.0.1:{free_port()}")
    assert telemetry.setup()
    with telemetry.span("acf.test"):
        pass
    t0 = time.monotonic()
    await asyncio.to_thread(telemetry.shutdown, 1.0)
    assert time.monotonic() - t0 < 2
    assert not telemetry.enabled()
