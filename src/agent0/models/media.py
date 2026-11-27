from __future__ import annotations

import io
import wave
from collections.abc import Awaitable, Callable
from math import gcd
from typing import Any

import google.genai as genai
from google.genai import types as gtypes
from groq import AsyncGroq
from pydantic_ai.embeddings.google import GoogleEmbeddingModel
from pydantic_ai.images.google import GoogleImageGenerationModel
from pydantic_ai.providers.google import GoogleProvider

from agent0.core.types import Capability
from agent0.models.base import ModelProfile
from agent0.models.chat import api_key
from agent0.models.cooldown import default_tracker
from agent0.models.usage import Units, UsageMeter

# An adapter does the provider call and returns (result, units consumed). Register a new provider by
# adding one entry per capability to ADAPTERS; tests swap entries for fakes.
Adapter = Callable[..., Awaitable[tuple[Any, Units]]]

GEMINI_PCM_RATE = 24000


def _aspect_ratio(size: str) -> str:
    if ":" in size:
        return size
    w, h = (int(x) for x in size.lower().split("x"))
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def _wav(pcm: bytes, rate: int = GEMINI_PCM_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _wav_seconds(audio: bytes) -> float:
    try:
        with wave.open(io.BytesIO(audio)) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError):
        return 0.0


async def _google_image(profile: ModelProfile, prompt: str, size: str) -> tuple[bytes, Units]:
    model = GoogleImageGenerationModel(profile.model, provider=GoogleProvider(api_key=api_key(profile)))
    result = await model.generate(prompt, settings={"aspect_ratio": _aspect_ratio(size)})  # pyright: ignore[reportArgumentType]
    return result.images[0].content.data, Units(images=len(result.images))


async def _google_tts(profile: ModelProfile, text: str, voice: str | None) -> tuple[bytes, Units]:
    client = genai.Client(api_key=api_key(profile))
    voice_name = voice or profile.settings.get("voice", "Kore")
    config = gtypes.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=gtypes.SpeechConfig(
            voice_config=gtypes.VoiceConfig(
                prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        ),
    )
    resp = await client.aio.models.generate_content(model=profile.model, contents=text, config=config)
    parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else None
    if not parts or not parts[0].inline_data or not parts[0].inline_data.data:
        raise RuntimeError("Gemini TTS returned no audio")
    meta = resp.usage_metadata
    units = Units(
        chars=len(text),
        input_tokens=(meta.prompt_token_count or 0) if meta else 0,
        output_tokens=(meta.candidates_token_count or 0) if meta else 0,
    )
    return _wav(parts[0].inline_data.data), units


async def _google_embed(profile: ModelProfile, texts: list[str]) -> tuple[list[list[float]], Units]:
    model = GoogleEmbeddingModel(profile.model, provider=GoogleProvider(api_key=api_key(profile)))
    settings: Any = {}
    if dims := profile.settings.get("dimensions"):
        settings["dimensions"] = dims
    result = await model.embed(texts, input_type="document", settings=settings or None)
    return [list(v) for v in result.embeddings], Units(input_tokens=result.usage.input_tokens)


async def _groq_tts(profile: ModelProfile, text: str, voice: str | None) -> tuple[bytes, Units]:
    client = AsyncGroq(api_key=api_key(profile))
    resp = await client.audio.speech.create(
        model=profile.model,
        input=text,
        voice=voice or profile.settings.get("voice", "autumn"),
        response_format="wav",
    )
    return await resp.read(), Units(chars=len(text))


async def _groq_stt(profile: ModelProfile, audio: bytes) -> tuple[str, Units]:
    client = AsyncGroq(api_key=api_key(profile))
    resp = await client.audio.transcriptions.create(
        model=profile.model, file=("audio.wav", audio), response_format="verbose_json"
    )
    seconds = getattr(resp, "duration", None) or _wav_seconds(audio)
    return resp.text, Units(seconds=float(seconds))


ADAPTERS: dict[Capability, dict[str, Adapter]] = {
    Capability.IMAGE_GEN: {"google": _google_image},
    Capability.TTS: {"google": _google_tts, "groq": _groq_tts},
    Capability.STT: {"groq": _groq_stt},
    Capability.EMBEDDING: {"google": _google_embed},
}


def _is_rate_limit(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 429 or "ratelimit" in type(exc).__name__.lower()


async def _run(profile: ModelProfile, capability: Capability, meter: UsageMeter | None, *args: Any) -> Any:
    if profile.capability != capability:
        raise ValueError(f"profile {profile.name} has capability {profile.capability}, need {capability}")
    try:
        adapter = ADAPTERS[capability][profile.provider]
    except KeyError:
        raise ValueError(f"no {capability.value} adapter for provider {profile.provider!r}") from None
    try:
        if meter is None:
            value, _ = await adapter(profile, *args)
            return value
        async with meter.track(profile) as units:
            value, used = await adapter(profile, *args)
            units.__dict__.update(used.__dict__)
        return value
    except Exception as exc:
        if _is_rate_limit(exc):
            default_tracker().record(profile.name)
        raise


async def generate_image(
    profile: ModelProfile, prompt: str, size: str = "1024x1024", *, meter: UsageMeter | None = None
) -> bytes:
    return await _run(profile, Capability.IMAGE_GEN, meter, prompt, size)


async def speak(
    profile: ModelProfile, text: str, voice: str | None = None, *, meter: UsageMeter | None = None
) -> bytes:
    return await _run(profile, Capability.TTS, meter, text, voice)


async def transcribe(profile: ModelProfile, audio: bytes, *, meter: UsageMeter | None = None) -> str:
    return await _run(profile, Capability.STT, meter, audio)


async def embed(
    profile: ModelProfile, texts: list[str], *, meter: UsageMeter | None = None
) -> list[list[float]]:
    return await _run(profile, Capability.EMBEDDING, meter, texts)
