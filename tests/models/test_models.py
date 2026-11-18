from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from agent0.core.types import Capability
from agent0.models import media
from agent0.models.base import Cost, ModelProfile, NoProfileAvailable
from agent0.models.chat import MissingKeyError, build_fallback, build_model
from agent0.models.registry import ModelRegistry
from agent0.models.router import Router
from agent0.models.usage import InMemoryUsageSink, Units, UsageMeter, compute_cost, record_from_run_usage

CONFIG = Path(__file__).parents[2] / "config" / "models.yaml"


def prof(name, provider="groq", cap=Capability.CHAT, tags=(), cost=None, ctx=None, key="K_" + "X", **kw):
    return ModelProfile(
        name=name,
        provider=provider,
        model=name,
        capability=cap,
        tags=list(tags),
        cost=cost or Cost(),
        context_window=ctx,
        key_env=key,
        **kw,
    )


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("K_X", "secret")


def test_load_real_config(monkeypatch):
    reg = ModelRegistry.load(CONFIG)
    names = {p.name for p in reg.all()}
    assert {"groq-fast", "gemini-pro", "groq-tts", "groq-stt", "gemini-embed"} <= names
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert reg.available() == []
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert {p.provider for p in reg.available()} == {"groq"}


def test_registry_crud_and_enabled(keys):
    reg = ModelRegistry([prof("a")])
    reg.add(prof("b"))
    with pytest.raises(ValueError):
        reg.add(prof("b"))
    reg.update(prof("b", enabled=False))
    assert [p.name for p in reg.available()] == ["a"]
    reg.remove("a")
    with pytest.raises(KeyError):
        reg.get("a")
    with pytest.raises(KeyError):
        reg.update(prof("zzz"))


def test_router_prefers_tag_and_cost(keys):
    reg = ModelRegistry(
        [
            prof("cheapo", tags=["cheap"], cost=Cost(input_per_mtok=0.05), ctx=1000),
            prof("mid", tags=["cheap", "smart"], cost=Cost(input_per_mtok=0.5), ctx=2000),
            prof("big", tags=["smart"], cost=Cost(input_per_mtok=5), ctx=100000),
        ]
    )
    r = Router(reg)
    assert r.pick(Capability.CHAT, "cheap").name == "cheapo"
    assert r.pick(Capability.CHAT, "smart").name == "big"
    assert r.pick("chat", "smart", needs_context=50000).name == "big"
    with pytest.raises(NoProfileAvailable):
        r.pick(Capability.CHAT, needs_context=10**9)


def test_router_exclusion_capability_and_explain(keys, monkeypatch):
    reg = ModelRegistry(
        [
            prof("g1", "groq", tags=["smart"]),
            prof("m1", "google", tags=["smart"]),
            prof("tts", "groq", Capability.TTS),
        ]
    )
    r = Router(reg)
    assert r.pick(Capability.CHAT, "smart", exclude_provider="groq").provider == "google"
    assert r.pick(Capability.TTS).name == "tts"
    with pytest.raises(NoProfileAvailable):
        r.pick(Capability.STT)
    assert "excluded provider groq" in r.explain(Capability.CHAT, "smart", exclude_provider="groq")
    assert "no available profile" in r.explain(Capability.STT)
    monkeypatch.delenv("K_X")
    with pytest.raises(NoProfileAvailable):
        r.pick(Capability.CHAT)


def test_router_deterministic_tiebreak(keys):
    r = Router(ModelRegistry([prof("b"), prof("a")]))
    assert r.pick(Capability.CHAT).name == "a"


def test_cost_math():
    p = prof(
        "x",
        cost=Cost(input_per_mtok=2, output_per_mtok=10, per_image=0.05, per_1k_chars=0.02, per_minute=0.6),
    )
    assert compute_cost(p, Units(input_tokens=500_000, output_tokens=100_000)) == pytest.approx(2.0)
    assert compute_cost(p, Units(images=2, chars=500, seconds=30)) == pytest.approx(0.1 + 0.01 + 0.3)


def test_record_from_run_usage():
    p = prof("c", cost=Cost(input_per_mtok=1, output_per_mtok=2))
    rec = record_from_run_usage(p, RunUsage(input_tokens=1_000_000, output_tokens=500_000), run_id="r1")
    assert (rec.input_units, rec.output_units, rec.run_id) == (1_000_000, 500_000, "r1")
    assert rec.cost_usd == pytest.approx(2.0)


async def test_chat_run_metered(keys):
    p = prof("c", cost=Cost(input_per_mtok=1, output_per_mtok=1))
    sink = InMemoryUsageSink()
    result = await Agent(TestModel()).run("hi")
    rec = await UsageMeter(sink, "run").record_chat(p, result.usage, latency_ms=5)
    assert sink.records == [rec] and rec.input_units > 0 and rec.latency_ms == 5


def test_build_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "g")
    monkeypatch.setenv("GEMINI_API_KEY", "m")
    groq = prof("g", "groq", key="GROQ_API_KEY")
    gem = prof("m", "google", key="GEMINI_API_KEY")
    assert build_model(groq).model_name == "g"
    assert isinstance(build_fallback([groq, gem]), FallbackModel)
    assert not isinstance(build_fallback([groq]), FallbackModel)
    with pytest.raises(ValueError):
        build_model(prof("o", "openai", key="GROQ_API_KEY"))
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(MissingKeyError):
        build_model(groq)


def test_build_openai_compatible(monkeypatch):
    monkeypatch.setenv("GONKA_API_KEY", "k")
    p = prof(
        "deepseek", "openai_compat", key="GONKA_API_KEY", settings={"base_url": "https://broker.test/v1"}
    )
    model = build_model(p)
    assert model.model_name == "deepseek" and "broker.test" in model.base_url


@pytest.fixture
def fake_adapters(monkeypatch):
    calls = []

    async def img(profile, prompt, size):
        calls.append(("img", prompt, size))
        return b"png", Units(images=2)

    async def tts(profile, text, voice):
        calls.append(("tts", text, voice))
        return b"wav", Units(chars=len(text))

    async def stt(profile, audio):
        return "hello", Units(seconds=90)

    async def emb(profile, texts):
        return [[0.1, 0.2] for _ in texts], Units(input_tokens=1000)

    table = {
        Capability.IMAGE_GEN: {"google": img},
        Capability.TTS: {"groq": tts},
        Capability.STT: {"groq": stt},
        Capability.EMBEDDING: {"google": emb},
    }
    monkeypatch.setattr(media, "ADAPTERS", table)
    return calls


async def test_media_dispatch_and_metering(fake_adapters):
    sink = InMemoryUsageSink()
    meter = UsageMeter(sink, "r")
    image = prof("i", "google", Capability.IMAGE_GEN, cost=Cost(per_image=0.05))
    tts = prof("t", "groq", Capability.TTS, cost=Cost(per_1k_chars=1.0))
    stt = prof("s", "groq", Capability.STT, cost=Cost(per_minute=0.2))
    emb = prof("e", "google", Capability.EMBEDDING, cost=Cost(input_per_mtok=1.0))

    assert await media.generate_image(image, "cat", "1024x1024", meter=meter) == b"png"
    assert await media.speak(tts, "x" * 500, "v", meter=meter) == b"wav"
    assert await media.transcribe(stt, b"audio", meter=meter) == "hello"
    assert await media.embed(emb, ["a", "b"], meter=meter) == [[0.1, 0.2]] * 2
    assert fake_adapters[0] == ("img", "cat", "1024x1024")

    costs = [r.cost_usd for r in sink.records]
    assert costs == pytest.approx([0.1, 0.5, 0.3, 0.001])
    assert all(r.ok and r.run_id == "r" for r in sink.records)


async def test_media_errors(fake_adapters):
    sink = InMemoryUsageSink()
    wrong_provider = prof("t", "google", Capability.TTS)
    with pytest.raises(ValueError, match="no tts adapter"):
        await media.speak(wrong_provider, "hi")
    with pytest.raises(ValueError, match="capability"):
        await media.speak(prof("c"), "hi")

    async def boom(profile, audio):
        raise RuntimeError("x")

    media.ADAPTERS[Capability.STT]["groq"] = boom
    with pytest.raises(RuntimeError):
        await media.transcribe(prof("s", "groq", Capability.STT), b"a", meter=UsageMeter(sink))
    assert [r.ok for r in sink.records] == [False]


def test_helpers():
    assert media._aspect_ratio("1024x1024") == "1:1"
    assert media._aspect_ratio("1920x1080") == "16:9"
    assert media._aspect_ratio("4:3") == "4:3"
    assert media._wav_seconds(media._wav(b"\0\0" * 24000)) == pytest.approx(1.0)
