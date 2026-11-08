"""The server's model API key never leaves the server's own provider and address."""

from acf import config
from acf.db import User
from acf.llm import NO_KEY, LLMConfig
from tests.conftest import send
from tests.fakes import fake_llm


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def keys_seen() -> list[str]:
    out = []
    for r in fake_llm.REQUESTS:
        h = r["headers"]
        out.append(h.get("x-api-key") or h.get("authorization", "").removeprefix("Bearer "))
    return out


async def test_server_key_used_for_the_servers_own_model(client, user):
    fake_llm.REQUESTS.clear()
    turn = await send(client, await new_chat(client), "hello")
    assert turn.final == "Echo: hello"
    assert keys_seen() == ["test-key"]


async def test_server_key_is_not_sent_to_another_provider(client, user, fake_llm_url):
    # The server's own address, written differently: still the server's key.
    r = await client.put("/api/settings", json={"provider": "anthropic", "base_url": f"{fake_llm_url}/"})
    assert r.status_code == 200
    fake_llm.REQUESTS.clear()
    await send(client, await new_chat(client), "hello")
    assert keys_seen() == ["test-key"]

    await client.put("/api/settings", json={"provider": "openai", "model": "m", "base_url": f"{fake_llm_url}/v1"})
    fake_llm.REQUESTS.clear()
    await send(client, await new_chat(client), "hello")
    assert keys_seen() == [NO_KEY]


async def test_server_key_is_not_sent_to_another_address_of_the_same_provider(client, user, fake_llm_url):
    other = fake_llm_url.replace("127.0.0.1", "localhost")
    await client.put("/api/settings", json={"provider": "anthropic", "base_url": other})
    fake_llm.REQUESTS.clear()
    turn = await send(client, await new_chat(client), "hello")
    assert turn.final == "Echo: hello"
    assert keys_seen() == [NO_KEY]


async def test_users_own_key_goes_to_their_server(client, user, fake_llm_url):
    await client.put(
        "/api/settings", json={"provider": "openai", "model": "m", "base_url": f"{fake_llm_url}/v1", "api_key": "mine"}
    )
    fake_llm.REQUESTS.clear()
    await send(client, await new_chat(client), "hello")
    assert keys_seen() == ["mine"]


def test_env_keys_are_not_picked_up_for_another_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "server-env-key")
    cfg = LLMConfig.for_user(User(llm_provider="openai", llm_model="m", llm_base_url="", llm_api_key=""))
    assert cfg.api_key == NO_KEY and cfg.base_url == ""


async def test_only_allowed_providers_can_be_chosen(client, user):
    r = await client.put("/api/settings", json={"provider": "bedrock_converse", "model": "x"})
    assert r.status_code == 400 and "doesn't offer 'bedrock_converse'" in r.json()["detail"]
    assert "anthropic" in r.json()["detail"]
    settings = (await client.get("/api/settings")).json()
    assert "openai" in settings["providers"] and "bedrock_converse" not in settings["providers"]


async def test_disallowed_provider_saved_earlier_is_refused_at_run_time(client, user):
    from acf import db

    with db.session_scope() as s:
        s.get(User, user["id"]).llm_provider = "bedrock_converse"
        s.get(User, user["id"]).llm_model = "x"
    turn = await send(client, await new_chat(client), "hi")
    assert "not available on this server" in turn.error


async def test_any_provider_when_the_operator_allows_it(client, user, monkeypatch):
    monkeypatch.setattr(config.settings, "llm_providers", "*")
    r = await client.put("/api/settings", json={"provider": "bedrock_converse", "model": "x"})
    assert r.status_code == 200


async def test_settings_fields_are_bounded(client, user):
    r = await client.put("/api/settings", json={"model": "m" * 201})
    assert r.status_code == 422
    r = await client.put("/api/settings", json={"base_url": "file:///etc/passwd"})
    assert r.status_code == 400


def test_empty_provider_list_means_the_default(monkeypatch):
    monkeypatch.setenv("ACF_LLM_PROVIDERS", "")  # docker compose passes unset variables as empty
    s = config.Settings()
    assert s.provider_allowed("openai") and not s.provider_allowed("bedrock_converse")
