from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from pydantic_ai.usage import RunUsage

from agent0.core.types import Capability
from agent0.models.base import ModelProfile, UsageRecord, UsageSink


class InMemoryUsageSink:
    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    async def record(self, usage: UsageRecord) -> None:
        self.records.append(usage)


@dataclass
class Units:
    input_tokens: int = 0
    output_tokens: int = 0
    images: int = 0
    chars: int = 0
    seconds: float = 0.0


def compute_cost(profile: ModelProfile, u: Units) -> float:
    c = profile.cost
    return (
        c.input_per_mtok * u.input_tokens / 1e6
        + c.output_per_mtok * u.output_tokens / 1e6
        + c.per_image * u.images
        + c.per_1k_chars * u.chars / 1000
        + c.per_minute * u.seconds / 60
    )


def _record_units(profile: ModelProfile, u: Units) -> tuple[int, int]:
    # UsageRecord unit conventions: image_gen -> output=images, tts -> input=chars,
    # stt -> input=seconds, chat/vision/embedding -> tokens.
    match profile.capability:
        case Capability.IMAGE_GEN:
            return 0, u.images
        case Capability.TTS:
            return u.chars, u.output_tokens
        case Capability.STT:
            return round(u.seconds), 0
        case _:
            return u.input_tokens, u.output_tokens


def build_record(
    profile: ModelProfile, u: Units, *, run_id: str | None = None, latency_ms: int = 0, ok: bool = True
) -> UsageRecord:
    in_u, out_u = _record_units(profile, u)
    return UsageRecord(
        run_id=run_id,
        profile=profile.name,
        provider=profile.provider,
        model=profile.model,
        capability=profile.capability,
        input_units=in_u,
        output_units=out_u,
        cost_usd=compute_cost(profile, u),
        latency_ms=latency_ms,
        ok=ok,
    )


def record_from_run_usage(
    profile: ModelProfile, usage: RunUsage, *, run_id: str | None = None, latency_ms: int = 0, ok: bool = True
) -> UsageRecord:
    u = Units(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
    return build_record(profile, u, run_id=run_id, latency_ms=latency_ms, ok=ok)


class UsageMeter:
    def __init__(self, sink: UsageSink, run_id: str | None = None) -> None:
        self.sink = sink
        self.run_id = run_id

    @asynccontextmanager
    async def track(self, profile: ModelProfile) -> AsyncIterator[Units]:
        """Fill the yielded Units; a record is written on exit, ok=False if the body raised."""
        units = Units()
        start = time.perf_counter()
        ok = True
        try:
            yield units
        except BaseException:
            ok = False
            raise
        finally:
            ms = round((time.perf_counter() - start) * 1000)
            await self.sink.record(build_record(profile, units, run_id=self.run_id, latency_ms=ms, ok=ok))

    async def record_chat(
        self, profile: ModelProfile, usage: RunUsage, latency_ms: int = 0, ok: bool = True
    ) -> UsageRecord:
        rec = record_from_run_usage(profile, usage, run_id=self.run_id, latency_ms=latency_ms, ok=ok)
        await self.sink.record(rec)
        return rec
