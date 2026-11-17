from __future__ import annotations

import logging

from conftest import KEY_ENV

from agent0.api.errors import ApiError, RateLimiter
from agent0.models.registry import resolve_secret
from agent0.secrets import InMemorySecretStore

BASE = "/api/v1/secrets"
PLAINTEXT = "gsk_SUPERSECRET_plaintext_value_9876"


def test_list_masked_and_allowed_names(client):
    items = client.get(BASE).json()["items"]
    assert [i["name"] for i in items] == ["AGENT0_TELEGRAM_BOT_TOKEN", KEY_ENV]
    assert all(i["configured"] is False and i["source"] is None for i in items)


def test_secret_never_echoed(env, caplog):
    caplog.set_level(logging.DEBUG)
    bodies = []

    def track(r):
        bodies.append(r.text + str(dict(r.headers)))
        return r

    put = track(env.client.put(f"{BASE}/{KEY_ENV}", json={"value": PLAINTEXT}))
    assert put.status_code == 200
    assert put.json() == {
        "name": KEY_ENV,
        "last4": PLAINTEXT[-4:],
        "configured": True,
        "source": "store",
        "updated_at": put.json()["updated_at"],
    }
    track(env.client.get(BASE))
    track(env.client.get("/api/v1/model-profiles"))
    track(env.client.get("/api/v1/extensions"))
    track(env.client.put(f"{BASE}/NOT_ALLOWED", json={"value": PLAINTEXT}))
    track(env.client.put(f"{BASE}/{KEY_ENV}", json={"value": PLAINTEXT * 200}))
    track(env.client.put(f"{BASE}/{KEY_ENV}", json={"value": PLAINTEXT + "\nx"}))
    track(env.client.put(f"{BASE}/{KEY_ENV}", json={"wrong": PLAINTEXT}))
    test = track(env.client.post(f"{BASE}/{KEY_ENV}/test"))
    assert test.json() == {"ok": True, "message": "ok ***"}
    track(env.client.delete(f"{BASE}/{KEY_ENV}"))
    assert all(PLAINTEXT not in b for b in bodies)
    assert PLAINTEXT not in caplog.text
    assert not any(PLAINTEXT in str(e) for e in env.repos.events.rows)
    assert resolve_secret(KEY_ENV) is None


def test_store_flow_and_resolver(env):
    assert resolve_secret(KEY_ENV) is None
    env.client.put(f"{BASE}/{KEY_ENV}", json={"value": PLAINTEXT})
    assert resolve_secret(KEY_ENV) == PLAINTEXT
    prof = env.client.get("/api/v1/model-profiles").json()["items"][0]
    assert prof["key_configured"] is True
    assert env.registry.available()
    listed = {i["name"]: i for i in env.client.get(BASE).json()["items"]}
    assert listed[KEY_ENV]["source"] == "store"
    assert env.client.delete(f"{BASE}/{KEY_ENV}").json()["configured"] is False
    assert resolve_secret(KEY_ENV) is None
    assert env.client.delete(f"{BASE}/{KEY_ENV}").status_code == 404


def test_env_keys_are_read_only(env, monkeypatch):
    monkeypatch.setenv(KEY_ENV, PLAINTEXT)
    item = {i["name"]: i for i in env.client.get(BASE).json()["items"]}[KEY_ENV]
    assert item["source"] == "env" and item["configured"] is True and item["last4"] is None
    for r in (
        env.client.put(f"{BASE}/{KEY_ENV}", json={"value": "other-value-1234"}),
        env.client.delete(f"{BASE}/{KEY_ENV}"),
    ):
        assert r.status_code == 409 and r.json()["error"]["code"] == "env_managed"
        assert PLAINTEXT not in r.text
    assert env.client.post(f"{BASE}/{KEY_ENV}/test").json()["ok"] is True
    assert env.tested[-1] == (KEY_ENV, "groq")


def test_rejects_unknown_names_and_disabled_store(env):
    r = env.client.put(f"{BASE}/SOME_OTHER_KEY", json={"value": "abcdefghijkl"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_secret"
    env.deps.secrets = InMemorySecretStore(None)
    r = env.client.put(f"{BASE}/{KEY_ENV}", json={"value": "abcdefghijkl"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "secrets_disabled"


def test_test_endpoint_unconfigured_and_failing_tester(env):
    assert env.client.post(f"{BASE}/{KEY_ENV}/test").status_code == 409

    async def boom(name, value, provider):
        raise RuntimeError(f"leaked {value}")

    env.deps.secret_tester = boom
    env.client.put(f"{BASE}/{KEY_ENV}", json={"value": PLAINTEXT})
    r = env.client.post(f"{BASE}/{KEY_ENV}/test")
    assert r.json()["ok"] is False and PLAINTEXT not in r.text


def test_rate_limit(env):
    env.app.state.secrets_limiter = RateLimiter(limit=3, window=60)
    codes = [env.client.get(BASE).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert env.client.get("/api/v1/runs").status_code == 200


def test_rate_limiter_window():
    now = [0.0]
    lim = RateLimiter(limit=1, window=10, clock=lambda: now[0])
    lim.check("k")
    try:
        lim.check("k")
        raise AssertionError("expected limit")
    except ApiError as e:
        assert e.status == 429
    now[0] = 11
    lim.check("k")
