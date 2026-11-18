from types import SimpleNamespace

import psycopg_pool
import pytest

import agent0.config
import agent0.secrets.store
from agent0.cli import _load_stored_secrets
from agent0.models.registry import resolve_secret, set_secret_resolver


class FakePool:
    def __init__(self, *a, fail: bool = False, **kw):
        self.fail = fail
        self.closed = False

    async def open(self, **kw):
        if self.fail:
            raise TimeoutError

    async def close(self):
        self.closed = True


class FakeStore:
    def __init__(self, pool, key):
        pass

    async def load(self):
        pass

    def resolve(self, name):
        return {"GROQ_API_KEY": "from-store"}.get(name)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(agent0.secrets.store, "PgSecretStore", FakeStore)
    yield
    set_secret_resolver(None)


def _settings(monkeypatch, key):
    s = SimpleNamespace(secret_key=key, database_url="postgresql://x")
    monkeypatch.setattr(agent0.config, "get_settings", lambda: s)


async def test_loads_dashboard_secrets(monkeypatch):
    _settings(monkeypatch, "k")
    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", FakePool)
    await _load_stored_secrets()
    assert resolve_secret("GROQ_API_KEY") == "from-store"


async def test_db_down_falls_back_to_env(monkeypatch):
    _settings(monkeypatch, "k")
    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", lambda *a, **kw: FakePool(fail=True))
    await _load_stored_secrets()
    assert resolve_secret("GROQ_API_KEY") is None


async def test_no_master_key_skips_db(monkeypatch):
    _settings(monkeypatch, None)

    def boom(*a, **kw):
        raise AssertionError("should not connect")

    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", boom)
    await _load_stored_secrets()
