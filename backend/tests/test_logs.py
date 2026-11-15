"""JSON logs: shape, ids bound per request and run, nothing secret."""

import io
import json
import logging

import pytest

from acf import config, logs
from tests.conftest import send, use_model


@pytest.fixture
def lines(monkeypatch):
    """Log output as parsed JSON lines, with the JSON handler installed."""
    buf = io.StringIO()
    monkeypatch.setattr(config.settings, "log_format", "json")
    logs.configure("json")
    handler = next(h for h in logging.getLogger().handlers if getattr(h, "_acf", False))
    handler.setStream(buf)
    yield lambda: [json.loads(x) for x in buf.getvalue().splitlines()]
    logs.configure("text")


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def test_json_line_has_shape_and_context(lines):
    with logs.bound(request_id="r1", user_id=7):
        logging.getLogger("acf.test").info("hello %s", "world")
    (line,) = [x for x in lines() if x["logger"] == "acf.test"]
    assert line["message"] == "hello world" and line["level"] == "INFO"
    assert line["request_id"] == "r1" and line["user_id"] == 7
    assert line["ts"].endswith("+00:00")


def test_traceback_stays_on_one_line(lines):
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("acf.test").exception("failed")
    assert len(lines()) == 1
    assert "ValueError: boom" in lines()[0]["exc"]


def test_secrets_are_redacted(lines, monkeypatch):
    monkeypatch.setattr(config.settings, "llm_api_key", "server-key-123456")
    log = logging.getLogger("acf.test")
    log.warning("bad key sk-ant-abcdef123456 and server-key-123456")
    log.warning("headers Authorization: Bearer abc.def.ghi1234 access_token=zzz999")
    out = json.dumps(lines())
    for secret in ("sk-ant-abcdef123456", "server-key-123456", "abc.def.ghi1234", "zzz999"):
        assert secret not in out


def test_context_provider_adds_fields(lines):
    logs.add_context_provider(lambda: {"trace_id": "abc"})
    try:
        logging.getLogger("acf.test").info("x")
        assert lines()[-1]["trace_id"] == "abc"
    finally:
        logs._providers.clear()


def test_text_is_the_default(capsys):
    logs.configure("text")
    logging.getLogger("acf.test").info("plain")
    assert capsys.readouterr().err.rstrip().endswith("INFO acf.test: plain")


async def test_request_id_is_honoured_and_generated(client, lines):
    r = await client.get("/api/health", headers={"X-Request-Id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    r = await client.get("/api/health", headers={"X-Request-Id": "bad id with spaces"})
    assert len(r.headers["x-request-id"]) == 16
    access = [x for x in lines() if x["logger"] == "acf.access"]
    assert access[0]["request_id"] == "abc-123" and access[0]["status"] == 200


async def test_access_line_has_no_query_string(client, lines):
    await client.get("/api/health?code=secret-oauth-code")
    assert "secret-oauth-code" not in json.dumps([x for x in lines() if x["logger"].startswith("acf")])


async def test_a_turn_shares_one_run_id_with_user_and_chat(client, user, lines):
    chat_id = await new_chat(client)
    await send(client, chat_id, "private words")
    run_lines = [x for x in lines() if x["logger"] == "acf.agent"]
    assert {x["message"] for x in run_lines} >= {"run started", "run finished: end_turn"}
    assert len({x["run_id"] for x in run_lines}) == 1
    assert all(x["chat_id"] == chat_id and x["user_id"] == user["id"] for x in run_lines)
    assert "private words" not in json.dumps(lines())
    followed = [x for x in lines() if x["message"] == "following run"]
    assert followed and {x["run_id"] for x in followed} == {x["run_id"] for x in run_lines}


async def test_two_runs_do_not_share_run_ids(client, user, lines):
    a, b = await new_chat(client), await new_chat(client)
    await send(client, a, "one")
    await send(client, b, "two")
    started = [x for x in lines() if x["message"] == "run started"]
    assert len({x["run_id"] for x in started}) == 2
    assert {x["chat_id"] for x in started} == {a, b}


async def test_model_error_line_has_run_id_and_no_key(client, user, lines, fake_llm_url):
    await use_model(client, "anthropic:missing-model", base_url=fake_llm_url, api_key="sk-ant-secretkey123456")
    chat_id = await new_chat(client)
    await send(client, chat_id, "hi")
    failed = [x for x in lines() if x["message"].startswith("model call failed")]
    assert failed and failed[0]["run_id"]
    assert "sk-ant-secretkey123456" not in json.dumps(lines())
