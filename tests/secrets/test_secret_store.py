from __future__ import annotations

import pytest

from agent0.core.types import Capability
from agent0.models.base import ModelProfile
from agent0.models.chat import MissingKeyError, api_key
from agent0.models.registry import ModelRegistry, resolve_secret, set_secret_resolver
from agent0.secrets import InMemorySecretStore, SecretsDisabled, allowed_secret_names, generate_key

ENV = "TEST_SECRET_STORE_KEY"
VALUE = "gsk_abcdefghijklmnop1234"


def profile() -> ModelProfile:
    return ModelProfile(name="p", provider="groq", model="m", capability=Capability.CHAT, key_env=ENV)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    yield
    set_secret_resolver(None)


async def test_round_trip_and_ciphertext_is_opaque():
    store = InMemorySecretStore(generate_key())
    await store.set(ENV, VALUE, "me")
    assert await store.get(ENV) == VALUE
    row = store._data[ENV]
    assert VALUE.encode() not in row["ciphertext"]
    listed = await store.list()
    assert listed[0]["name"] == ENV and listed[0]["last4"] == "1234" and listed[0]["configured"] is True
    assert VALUE not in str(listed)


async def test_reload_decrypts_and_wrong_key_is_skipped():
    key = generate_key()
    store = InMemorySecretStore(key)
    await store.set(ENV, VALUE, "me")
    fresh = InMemorySecretStore(key)
    fresh._data = store._data
    await fresh.load()
    assert fresh.resolve(ENV) == VALUE
    other = InMemorySecretStore(generate_key())
    other._data = store._data
    await other.load()
    assert other.resolve(ENV) is None


async def test_refuses_without_master_key():
    for key in (None, "", "not-a-fernet-key"):
        store = InMemorySecretStore(key)
        assert store.enabled is False
        with pytest.raises(SecretsDisabled):
            await store.set(ENV, VALUE, "me")


async def test_delete():
    store = InMemorySecretStore(generate_key())
    await store.set(ENV, VALUE, "me")
    assert await store.delete(ENV) is True
    assert await store.delete(ENV) is False
    assert store.resolve(ENV) is None


def test_short_values_have_no_last4():
    store = InMemorySecretStore(generate_key())
    import asyncio

    asyncio.run(store.set(ENV, "short", "me"))
    assert asyncio.run(store.list())[0]["last4"] == ""


async def test_resolver_order_env_first(monkeypatch):
    store = InMemorySecretStore(generate_key())
    await store.set(ENV, "from-store-value-xx", "me")
    set_secret_resolver(store.resolve)
    p = profile()
    assert api_key(p) == "from-store-value-xx"
    assert ModelRegistry([p]).available() == [p]
    monkeypatch.setenv(ENV, "from-env")
    assert api_key(p) == "from-env"
    assert resolve_secret(ENV) == "from-env"


def test_no_resolver_keeps_env_only_behaviour(monkeypatch):
    p = profile()
    with pytest.raises(MissingKeyError):
        api_key(p)
    assert ModelRegistry([p]).available() == []
    monkeypatch.setenv(ENV, "k")
    assert api_key(p) == "k"


def test_allowed_names_include_telegram():
    assert allowed_secret_names([profile()]) == ["AGENT0_TELEGRAM_BOT_TOKEN", ENV]
