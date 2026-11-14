"""Model settings: the operator's models, each user's model list, keys per provider, and a chat's model,
effort and token window."""

import json

import pytest

from acf import config, models
from tests.acp_client import RpcError, acp_connect
from tests.conftest import prompt, use_model


def by_key(settings: dict) -> dict[str, dict]:
    return {m["key"]: m for m in settings["models"]}


async def new_session(acp) -> tuple[str, list[dict]]:
    r = await acp.request("session/new", {"cwd": "/", "mcpServers": []})
    return r["sessionId"], r["configOptions"]


def option(options: list[dict], oid: str) -> dict | None:
    return next((o for o in options if o["id"] == oid), None)


async def set_option(acp, sid: str, oid: str, value: str) -> list[dict]:
    r = await acp.request("session/set_config_option", {"sessionId": sid, "configId": oid, "value": value})
    return r["configOptions"]


async def test_the_list_holds_the_servers_models_with_ready_ones_on(client, user):
    s = (await client.get("/api/settings")).json()
    listed = by_key(s)
    opus, gpt = listed["anthropic:claude-opus-5-5"], listed["openai:gpt-5"]
    assert opus["enabled"] and opus["has_key"]  # the server's provider has a key
    assert opus["efforts"] == ["low", "medium", "high", "max"] and opus["effort"] == "medium"
    assert not gpt["enabled"] and not gpt["has_key"]  # no key for OpenAI yet
    assert s["defaults"]["model"] == "anthropic:claude-opus-5-5" and s["model"] == ""

    await client.put("/api/settings/providers/openai", json={"api_key": "sk-mine"})
    listed = by_key((await client.get("/api/settings")).json())
    assert listed["openai:gpt-5"]["enabled"] and listed["openai:gpt-5"]["has_key"]


async def test_the_picker_offers_only_models_that_are_on(client, user):
    await client.patch("/api/settings/models", json={"key": "anthropic:claude-haiku-5-5", "enabled": False})
    picker = option((await client.get("/api/models")).json()["configOptions"], "model")
    values = [o["value"] for o in picker["options"]]
    assert picker["currentValue"] == "anthropic:claude-opus-5-5"
    assert "anthropic:claude-sonnet-5-5" in values and "anthropic:claude-haiku-5-5" not in values
    assert "openai:gpt-5" not in values
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        with pytest.raises(RpcError, match="Unknown model"):
            await set_option(acp, sid, "model", "anthropic:claude-haiku-5-5")


async def test_efforts_are_named_in_plain_words(client, user):
    effort = option((await client.get("/api/models")).json()["configOptions"], "effort")
    assert [(o["value"], o["name"]) for o in effort["options"]] == [
        ("low", "Quick"),
        ("medium", "Balanced"),
        ("high", "Thorough"),
        ("max", "Deepest"),
    ]


async def test_the_default_model_cannot_be_turned_off(client, user):
    r = await client.patch("/api/settings/models", json={"key": "anthropic:claude-opus-5-5", "enabled": False})
    assert r.status_code == 400 and "default model" in r.json()["detail"]


async def test_each_chat_runs_on_its_own_model_and_effort(client, user):
    async with acp_connect(client) as acp:
        sid, options = await new_session(acp)
        assert option(options, "effort")["currentValue"] == "medium"
        assert (await prompt(acp, sid, "show effort")).final == "Effort: medium"

        options = await set_option(acp, sid, "model", "anthropic:claude-sonnet-5-5")
        assert option(options, "model")["currentValue"] == "anthropic:claude-sonnet-5-5"
        options = await set_option(acp, sid, "effort", "high")
        assert option(options, "effort")["currentValue"] == "high"
        assert (await prompt(acp, sid, "show model")).final == "Model: claude-sonnet-5-5"
        assert (await prompt(acp, sid, "show effort")).final == "Effort: high"
        with pytest.raises(RpcError, match="Unknown effort"):
            await set_option(acp, sid, "effort", "turbo")

        other, _ = await new_session(acp)  # a new chat starts on the user's default
        assert (await prompt(acp, other, "show model")).final == "Model: claude-opus-5-5"

    async with acp_connect(client) as acp:  # the choice is kept with the chat
        r = await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        assert option(r["configOptions"], "model")["currentValue"] == "anthropic:claude-sonnet-5-5"
        assert option(r["configOptions"], "effort")["currentValue"] == "high"


async def test_default_model_and_effort(client, user):
    r = await client.put("/api/settings", json={"model": "anthropic:claude-haiku-5-5", "effort": "low"})
    assert r.json()["model"] == "anthropic:claude-haiku-5-5" and r.json()["effort"] == "low"
    async with acp_connect(client) as acp:
        sid, options = await new_session(acp)
        assert option(options, "model")["currentValue"] == "anthropic:claude-haiku-5-5"
        assert (await prompt(acp, sid, "show model")).final == "Model: claude-haiku-5-5"
        assert (await prompt(acp, sid, "show effort")).final == "Effort: low"


async def test_effort_goes_to_openai_as_reasoning_effort(client, user, fake_llm_url):
    await use_model(client, "openai:gpt-5", base_url=f"{fake_llm_url}/v1", api_key="k")
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        await set_option(acp, sid, "effort", "minimal")
        assert (await prompt(acp, sid, "show effort")).final == "Effort: minimal"
        options = await set_option(acp, sid, "model", "openai:gpt-4.1-mini")  # no effort setting
        assert option(options, "effort") is None
        assert (await prompt(acp, sid, "show effort")).final == "Effort: none"


async def test_models_of_ones_own(client, user, fake_llm_url):
    await client.put("/api/settings/providers/openai", json={"base_url": f"{fake_llm_url}/v1", "api_key": "k"})
    r = await client.post("/api/settings/models", json={"provider": "openai", "id": "llama3.1:8b"})
    added = by_key(r.json())["openai:llama3.1:8b"]
    assert added["custom"] and added["enabled"] and added["efforts"] == []
    assert (
        await client.post("/api/settings/models", json={"provider": "openai", "id": "two words"})
    ).status_code == 400
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        await set_option(acp, sid, "model", "openai:llama3.1:8b")
        assert (await prompt(acp, sid, "show model")).final == "Model: llama3.1:8b"

    r = await client.delete("/api/settings/models", params={"key": "openai:llama3.1:8b"})
    assert "openai:llama3.1:8b" not in by_key(r.json())
    # models from the server's list can only be turned off
    r = await client.delete("/api/settings/models", params={"key": "openai:gpt-5"})
    assert r.status_code == 404


async def test_operator_can_limit_users_to_the_list(client, user, monkeypatch):
    await client.post("/api/settings/models", json={"provider": "anthropic", "id": "claude-made-up"})
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        await set_option(acp, sid, "model", "anthropic:claude-made-up")
        monkeypatch.setattr(config.settings, "custom_models", False)
        r = await client.post("/api/settings/models", json={"provider": "anthropic", "id": "claude-other"})
        assert r.status_code == 400 and "only offers the models in the list" in r.json()["detail"]
        assert "anthropic:claude-made-up" not in by_key((await client.get("/api/settings")).json())
        turn = await prompt(acp, sid, "hello")  # chosen before the operator closed the list
        assert "not available on this server" in turn.error


async def test_models_file_replaces_the_list(client, user, monkeypatch, tmp_path):
    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            [
                {
                    "provider": "anthropic",
                    "id": "claude-opus-5-5",
                    "name": "Opus",
                    "efforts": ["low", "high"],
                    "effort": "high",
                    "context_window": 300_000,
                    "max_context_window": 600_000,
                },
                {"provider": "bedrock_converse", "id": "x"},  # provider not offered: left out
            ]
        )
    )
    monkeypatch.setattr(config.settings, "models_file", str(path))
    listed = by_key((await client.get("/api/settings")).json())
    assert list(listed) == ["anthropic:claude-opus-5-5"]
    assert listed["anthropic:claude-opus-5-5"]["window"] == 300_000
    async with acp_connect(client) as acp:
        sid, options = await new_session(acp)
        assert [o["value"] for o in option(options, "effort")["options"]] == ["low", "high"]
        turn = await prompt(acp, sid, "show effort")
        assert turn.final == "Effort: high"
        sizes = [u["size"] for u in turn.updates if u["sessionUpdate"] == "usage_update"]
        assert sizes == [300_000]

    path.write_text(json.dumps([{"provider": "anthropic", "id": "m", "efforts": ["low"], "effort": "max"}]))
    with pytest.raises(ValueError, match="not one of its efforts"):
        models.catalogue()


async def test_token_window(client, user):
    key = "anthropic:claude-opus-5-5"
    r = await client.patch("/api/settings/models", json={"key": key, "context_window": 50_000})
    assert by_key(r.json())[key]["window"] == 50_000
    assert (await client.patch("/api/settings/models", json={"key": key, "context_window": 10})).status_code == 400
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        turn = await prompt(acp, sid, "hello")
    assert [u["size"] for u in turn.updates if u["sessionUpdate"] == "usage_update"] == [50_000]


async def test_token_window_is_capped_by_the_operator(client, user, monkeypatch, tmp_path):
    path = tmp_path / "models.json"
    path.write_text(json.dumps([{"provider": "anthropic", "id": "claude-opus-5-5", "max_context_window": 200_000}]))
    monkeypatch.setattr(config.settings, "models_file", str(path))
    r = await client.patch("/api/settings/models", json={"key": "anthropic:claude-opus-5-5", "context_window": 300_000})
    assert r.status_code == 400 and "at most 200,000" in r.json()["detail"]


async def test_a_small_token_window_compacts_sooner(client, user):
    # ACF_COMPACT_TOKENS (120,000) is far off; a 1,000-token window compacts at 800.
    await client.patch("/api/settings/models", json={"key": "anthropic:claude-opus-5-5", "context_window": 1000})
    async with acp_connect(client) as acp:
        sid, _ = await new_session(acp)
        notices = []
        for i in range(3):
            notices += (await prompt(acp, sid, f"message number {i} " + "padding " * 200)).notices
        turn = await prompt(acp, sid, "show messages")
    assert any("Summarised" in n for n in notices + turn.notices)
    assert "SUMMARY of" in turn.final and "message number 0" in turn.final
