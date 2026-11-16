"""Logging: text (default) or one JSON object per line (`ACF_LOG_FORMAT=json`), with ids bound per request and run.

Context fields (request_id, user_id, chat_id, run_id, task_id) live in a contextvar, so every line logged while
serving a request or working on a run carries them, whichever module logs it. Child asyncio tasks inherit them.
Everything that adds a field to a record goes through `ContextFilter`: `bind` and `annotate` set values, and
`add_context_provider` registers a function that returns more fields at log time (e.g. trace_id and span_id).
The app never logs message bodies or tool output; the JSON formatter also redacts key-like tokens.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import re
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar("acf_log_ctx", default=None)
_providers: list[Callable[[], dict[str, Any]]] = []

_SECRET = re.compile(r"(?i)\b(?:sk-[\w-]{8,}|acp_[\w-]{8,}|bearer\s+[\w.~+/=-]{8,})")
_HEADER = re.compile(
    r"(?i)\b(authorization|x-api-key|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]secret)"
    r"(['\"]?\s*[:=]\s*['\"]?)(?:bearer\s+)?[^\s,'\"}&]+"
)


def bind(**fields: Any) -> contextvars.Token:
    """Add fields for the rest of the current task and the tasks it starts. Other tasks are unaffected."""
    return _ctx.set({**(_ctx.get() or {}), **{k: v for k, v in fields.items() if v is not None}})


def annotate(**fields: Any) -> None:
    """Add fields to the context dict already in force, so everything sharing it (a whole request, even code run
    in a thread pool) sees them. Use `bind` when starting a task of its own."""
    if (ctx := _ctx.get()) is None:
        ctx = {}
        _ctx.set(ctx)
    ctx.update({k: v for k, v in fields.items() if v is not None})


@contextlib.contextmanager
def bound(**fields: Any) -> Iterator[None]:
    token = bind(**fields)
    try:
        yield
    finally:
        _ctx.reset(token)


def reset(token: contextvars.Token) -> None:
    _ctx.reset(token)


def fresh() -> None:
    """Start an empty context (a new request or connection must not inherit another's fields)."""
    _ctx.set({})


def current() -> dict[str, Any]:
    return dict(_ctx.get() or {})


def add_context_provider(fn: Callable[[], dict[str, Any]]) -> None:
    """Register a function whose fields are added to every record when it is logged. Idempotent."""
    if fn not in _providers:
        _providers.append(fn)


class ContextFilter(logging.Filter):
    """The one place that puts context fields on a record (`record.acf_ctx`)."""

    def filter(self, record: logging.LogRecord) -> bool:
        fields = dict(_ctx.get() or {})
        for provider in _providers:
            try:
                fields.update({k: v for k, v in provider().items() if v is not None})
            except Exception:  # noqa: BLE001 - a broken provider must not stop logging
                pass
        record.acf_ctx = fields
        return True


def redact(text: str) -> str:
    from acf import config

    key = config.settings.llm_api_key
    if key and len(key) >= 8:
        text = text.replace(key, "[redacted]")
    text = _HEADER.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text)
    return _SECRET.sub("[redacted]", text)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        out.update({k: v for k in ("status", "duration_ms") if (v := getattr(record, k, None)) is not None})
        out.update(getattr(record, "acf_ctx", None) or {})
        if record.exc_info:
            out["exc"] = redact(self.formatException(record.exc_info))
        if record.stack_info:
            out["stack"] = redact(self.formatStack(record.stack_info))
        return json.dumps(out, default=str, ensure_ascii=False)


_UVICORN = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configure(fmt: str | None = None) -> None:
    """Install the root handler. Safe to call again (tests, reloads): it replaces its own handler."""
    from acf import config

    fmt = (fmt or config.settings.log_format).lower()
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, "_acf", False)]:
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler._acf = True  # type: ignore[attr-defined]
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(TEXT_FORMAT))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    if fmt == "json":
        # One format on stderr: uvicorn's own handlers would print text, and its access log has query strings
        # (OAuth codes). RequestContext logs an access line without them.
        for name in _UVICORN:
            lg = logging.getLogger(name)
            lg.handlers.clear()
            lg.propagate = name != "uvicorn.access"
        logging.getLogger("uvicorn.access").disabled = True
