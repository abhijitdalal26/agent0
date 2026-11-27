from __future__ import annotations

import pytest
from pydantic_ai.exceptions import ModelRateLimitError
from pydantic_ai.models.test import TestModel

from agent0.core.types import Capability
from agent0.models.base import Cost, ModelProfile
from agent0.models.chat import _CooldownModel
from agent0.models.cooldown import CooldownTracker
from agent0.models.registry import ModelRegistry
from agent0.models.router import Router


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("K_X", "secret")


def prof(name, provider="groq", tags=()):
    return ModelProfile(
        name=name, provider=provider, model=name, capability=Capability.CHAT,
        tags=list(tags), cost=Cost(), key_env="K_X",
    )


def test_tracker_backoff_and_expiry():
    now = [1000.0]
    t = CooldownTracker(clock=lambda: now[0])
    assert t.cooling("a") == 0.0
    assert t.record("a") == pytest.approx(60.0)
    assert t.cooling("a") == pytest.approx(60.0)
    assert t.record("a") == pytest.approx(120.0)  # second strike doubles
    now[0] += 110  # t=1110, cooldown ends at 1120
    assert t.cooling("a") == pytest.approx(10.0)
    now[0] += 11
    assert t.cooling("a") == 0.0  # expired, strikes reset
    assert t.record("a") == pytest.approx(60.0)


def test_tracker_retry_after_and_cap():
    t = CooldownTracker()
    assert t.record("a", retry_after_s=5) == pytest.approx(5.0)
    for _ in range(10):
        t.record("b")
    # exponential backoff caps at 1800s
    assert t.cooling("b") <= 1800.0


def test_router_demotes_cooled_profiles():
    reg = ModelRegistry([prof("a-hot", "groq", ["smart"]), prof("z-cool", "google", ["smart"])])
    tracker = CooldownTracker()
    r = Router(reg, tracker)
    assert r.pick(Capability.CHAT, "smart").name == "a-hot"
    tracker.record("a-hot")
    assert r.pick(Capability.CHAT, "smart").name == "z-cool"
    # cooled profiles stay eligible when everything is cooling
    tracker.record("z-cool")
    assert r.pick(Capability.CHAT, "smart").name in {"a-hot", "z-cool"}
    assert "cooled down" in r.explain(Capability.CHAT, "smart")


class _RateLimited(TestModel):
    async def request(self, *args, **kwargs):  # type: ignore[override]
        raise ModelRateLimitError("test", "429 too many requests", retry_after=42.0)


async def test_cooldown_model_records_strikes():
    tracker = CooldownTracker()
    model = _CooldownModel(_RateLimited(), "groq-fast", tracker)
    with pytest.raises(ModelRateLimitError):
        await model.request([], None, None)  # type: ignore[arg-type]
    assert tracker.cooling("groq-fast") > 0
