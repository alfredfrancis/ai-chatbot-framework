"""OpenTelemetry traces and metrics, exported over OTLP/HTTP (protobuf) to any collector.

Off unless `OTEL_EXPORTER_OTLP_ENDPOINT` (or `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` / `..._METRICS_ENDPOINT`) is
set. Off, every helper here returns at once: no provider is made, no span is made, nothing goes over the network.
On, the standard OTEL_* variables configure the rest (headers, timeout, sampler, resource attributes, metric
export interval); `OTEL_SERVICE_NAME` defaults to "acf".

Spans: one SERVER span per HTTP request (named by route; never the query string), and per run:
  acf.run                  one agent run; follower processes join its trace (see `traceparent`)
    acf.turn               one user turn
      acf.llm              one model call (also compaction, sub-agents, reviews and titles)
      acf.tool             one tool call; a sub-agent's calls nest under its `agent` call
        acf.sandbox.exec   one command in the user's sandbox
    acf.follow             a client connection forwarding the run's events (in whichever process serves it)
Metrics: acf.runs.active, acf.run.duration{outcome}, acf.tool.calls{tool,outcome}, acf.sandbox.start.duration
{action}, acf.llm.tokens{provider,kind}, acf.acp.connections.

No attribute holds message text, prompts, tool arguments or output, commands, file paths or keys, and no metric
has a per-user label. JSON log lines inside a span carry its trace_id and span_id.

The providers are ACF's own, never the global ones: libraries that switch on when a global provider exists stay
off. FastAPI's native telemetry would record URL query strings (OAuth codes, file paths) and WebSocket frames;
the FastAPI, SQLAlchemy and Redis instrumentations are left out for the same reasons and for the root spans the
bus's polling would make. The SERVER span here records the route template only.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, Span, SpanKind, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from acf import logs

log = logging.getLogger("acf.telemetry")

TRACES_ENDPOINTS = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
METRICS_ENDPOINTS = ("OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
SERVICE_NAME = "acf"

_propagator = TraceContextTextMapPropagator()


@dataclass
class _Telemetry:
    tracer: trace.Tracer
    providers: list[Any]  # SDK providers to flush on shutdown
    runs_active: metrics.UpDownCounter
    run_duration: metrics.Histogram
    tool_calls: metrics.Counter
    sandbox_start: metrics.Histogram
    llm_tokens: metrics.Counter
    acp_connections: metrics.UpDownCounter


_t: _Telemetry | None = None


def _wanted(names: tuple[str, ...], exporter_var: str) -> bool:
    return any(os.environ.get(n) for n in names) and os.environ.get(exporter_var, "otlp").strip().lower() != "none"


def setup() -> bool:
    """Start exporting if an OTLP endpoint is configured. Returns whether telemetry is on. Idempotent."""
    if _t is not None:
        return True
    if os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true":
        return False
    want_traces = _wanted(TRACES_ENDPOINTS, "OTEL_TRACES_EXPORTER")
    want_metrics = _wanted(METRICS_ENDPOINTS, "OTEL_METRICS_EXPORTER")
    if not (want_traces or want_metrics):
        return False

    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create()  # OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES
    if str(resource.attributes.get("service.name", "")).startswith("unknown_service"):
        resource = resource.merge(Resource({"service.name": SERVICE_NAME}))
    tracer_provider = meter_provider = None
    if want_traces:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        tracer_provider = TracerProvider(resource=resource, shutdown_on_exit=False)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    if want_metrics:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

        reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        meter_provider = MeterProvider(metric_readers=[reader], resource=resource, shutdown_on_exit=False)
    install(tracer_provider, meter_provider)
    log.info("exporting%s%s over OTLP", " traces" if want_traces else "", " metrics" if want_metrics else "")
    return True


def install(tracer_provider: Any | None, meter_provider: Any | None) -> None:
    """Use these SDK providers (None: that signal stays off). `setup` calls it; tests pass in-memory ones."""
    global _t
    tracer = tracer_provider.get_tracer("acf") if tracer_provider else trace.NoOpTracer()
    meter = meter_provider.get_meter("acf") if meter_provider else metrics.NoOpMeter("acf")
    _t = _Telemetry(
        tracer=tracer,
        providers=[p for p in (tracer_provider, meter_provider) if p],
        runs_active=meter.create_up_down_counter("acf.runs.active", "{run}", "Agent runs working in this process"),
        run_duration=meter.create_histogram("acf.run.duration", "s", "How long agent runs take, by outcome"),
        tool_calls=meter.create_counter("acf.tool.calls", "{call}", "Tool calls, by tool and outcome"),
        sandbox_start=meter.create_histogram("acf.sandbox.start.duration", "s", "Time to start a user's sandbox"),
        llm_tokens=meter.create_counter("acf.llm.tokens", "{token}", "Model tokens, by provider and kind"),
        acp_connections=meter.create_up_down_counter("acf.acp.connections", "{connection}", "Open ACP connections"),
    )
    logs.add_context_provider(_trace_fields)


def reset() -> None:
    """Turn telemetry off again (tests)."""
    global _t
    _t = None


def enabled() -> bool:
    return _t is not None


def shutdown(timeout: float = 5.0) -> None:
    """Export what is buffered, then stop the exporters. Never takes much longer than `timeout` seconds, even
    with the collector down: the flush runs in a daemon thread that is abandoned after the deadline."""
    global _t
    if _t is None:
        return
    providers, _t = _t.providers, None
    deadline = time.monotonic() + timeout

    def flush() -> None:
        for p in providers:
            left = max(int((deadline - time.monotonic()) * 1000), 0)
            with contextlib.suppress(Exception):
                p.force_flush(left)
            with contextlib.suppress(Exception):
                p.shutdown()

    worker = threading.Thread(target=flush, name="otel-shutdown", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        log.warning("telemetry did not flush within %ss; dropping what is left", timeout)


def _trace_fields() -> dict[str, Any]:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return {}
    return {"trace_id": format(ctx.trace_id, "032x"), "span_id": format(ctx.span_id, "016x")}


# ------------------------------------------------------------------ spans


def _context(traceparent: str | None) -> Context:
    return _propagator.extract({"traceparent": traceparent} if traceparent else {})


def fail(span: Span, error_type: str) -> None:
    """Mark a span failed. `error_type` is a class of error (an exception's name), never a message."""
    span.set_status(StatusCode.ERROR)
    span.set_attribute("error.type", error_type)


@contextlib.contextmanager
def span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    parent: Context | None = None,
    links: list[Link] | None = None,
) -> Iterator[Span]:
    """A span that is current for the block. An exception marks it failed with its type only (messages can quote
    content); a cancel (the user stopped, or steering restarted a model call) is not a failure."""
    if _t is None:
        yield trace.INVALID_SPAN
        return
    with _t.tracer.start_as_current_span(
        name,
        context=parent,
        kind=kind,
        attributes=attributes,
        links=links,
        record_exception=False,
        set_status_on_exception=False,
    ) as sp:
        try:
            yield sp
        except asyncio.CancelledError:
            sp.set_attribute("acf.cancelled", True)
            raise
        except Exception as e:
            fail(sp, type(e).__name__)
            raise


def traceparent() -> str | None:
    """The current span as a W3C traceparent, for a process that continues the trace (None when off)."""
    if _t is None:
        return None
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    return carrier.get("traceparent")


def start_follow(run_id: str, chat_id: int, parent: str | None) -> Span:
    """`acf.follow`: a connection forwarding a run's events, in the run's trace when `parent` (its traceparent)
    is known. The caller ends it."""
    if _t is None:
        return trace.INVALID_SPAN
    attrs = {"acf.run.id": run_id, "acf.chat.id": chat_id}
    return _t.tracer.start_span("acf.follow", _context(parent), attributes=attrs)


def current(span: Span):
    """Make a span started with `start_follow` current for a block (its log lines carry its trace id)."""
    return trace.use_span(span, end_on_exit=False) if _t is not None else contextlib.nullcontext()


@contextlib.contextmanager
def server_span(scope: dict[str, Any]) -> Iterator[Span]:
    """A SERVER span for an HTTP request, continuing an incoming traceparent. WebSockets get none: an ACP
    connection lives for hours; its runs have their own spans."""
    if _t is None or scope["type"] != "http":
        yield trace.INVALID_SPAN
        return
    given = dict(scope["headers"]).get(b"traceparent", b"").decode("latin-1")
    method = scope["method"]
    with span(method, {"http.request.method": method}, kind=SpanKind.SERVER, parent=_context(given)) as sp:
        yield sp


def end_request(span: Span, scope: dict[str, Any], status: int) -> None:
    """Name the server span by its route template (/api/chats/{chat_id}), never the raw path or query."""
    if not span.is_recording():
        return
    route = getattr(scope.get("route"), "path", None)
    if route:
        span.update_name(f"{scope['method']} {route}")
        span.set_attribute("http.route", route)
    span.set_attribute("http.response.status_code", status)
    if status >= 500:
        fail(span, str(status))


@dataclass
class RunRecord:
    traceparent: str | None
    outcome: str = "end_turn"  # the run's stop reason, or "error"


@contextlib.contextmanager
def run(run_id: str, chat_id: int) -> Iterator[RunRecord]:
    """`acf.run` and the run metrics. Set `outcome` on the record before the block ends."""
    if _t is None:
        yield RunRecord(None)
        return
    t = _t
    started = time.monotonic()
    t.runs_active.add(1)
    # A trace of its own: a run outlives the request or the tool call that started it. A link keeps the way back.
    starter = trace.get_current_span().get_span_context()
    links = [Link(starter)] if starter.is_valid else None
    with span("acf.run", {"acf.run.id": run_id, "acf.chat.id": chat_id}, parent=Context(), links=links) as sp:
        record = RunRecord(traceparent())
        try:
            yield record
        finally:
            sp.set_attribute("acf.run.outcome", record.outcome)
            if record.outcome == "error":
                fail(sp, "run_failed")
            t.runs_active.add(-1)
            t.run_duration.record(time.monotonic() - started, {"outcome": record.outcome})


@dataclass
class ToolRecord:
    span: Span
    error: bool = False  # the call failed without raising (an error result for the model)


@contextlib.contextmanager
def tool(name: str) -> Iterator[ToolRecord]:
    """`acf.tool` and `acf.tool.calls{tool,outcome}`: ok, error or cancelled."""
    if _t is None:
        yield ToolRecord(trace.INVALID_SPAN)
        return
    t = _t
    outcome = "cancelled"
    try:
        with span("acf.tool", {"acf.tool.name": name}) as sp:
            record = ToolRecord(sp)
            yield record
            if record.error:
                fail(sp, "tool_error")
            outcome = "error" if record.error else "ok"
    except Exception:
        outcome = "error"
        raise
    finally:
        t.tool_calls.add(1, {"tool": name, "outcome": outcome})


def llm_usage(span: Span, provider: str, usage: dict[str, Any] | None) -> None:
    """Token counts of one answer (LangChain's usage_metadata) on its span and in `acf.llm.tokens`.
    cache_read and cache_creation are parts of input, counted again under their own kind."""
    if _t is None or not usage:
        return
    details = usage.get("input_token_details") or {}
    counts = {
        "input": usage.get("input_tokens"),
        "output": usage.get("output_tokens"),
        "cache_read": details.get("cache_read"),
        "cache_creation": details.get("cache_creation"),
    }
    for kind, n in counts.items():
        if n:
            _t.llm_tokens.add(int(n), {"provider": provider, "kind": kind})
    span.set_attribute("gen_ai.usage.input_tokens", int(counts["input"] or 0))
    span.set_attribute("gen_ai.usage.output_tokens", int(counts["output"] or 0))


def sandbox_started(seconds: float, action: str) -> None:
    """A sandbox was started: `action` is "create" (a new container) or "start" (a stopped one)."""
    if _t is not None:
        _t.sandbox_start.record(seconds, {"action": action})


@contextlib.contextmanager
def acp_connection() -> Iterator[None]:
    if _t is None:
        yield
        return
    t = _t
    t.acp_connections.add(1)
    try:
        yield
    finally:
        t.acp_connections.add(-1)
