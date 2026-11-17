from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agent0.core.types import Capability

Preference = Literal["cheap", "fast", "smart"]


class Cost(BaseModel):
    input_per_mtok: float = 0.0
    output_per_mtok: float = 0.0
    per_image: float = 0.0
    per_1k_chars: float = 0.0
    per_minute: float = 0.0


class ModelProfile(BaseModel):
    name: str
    provider: str
    model: str
    capability: Capability
    tags: list[str] = Field(default_factory=list)
    cost: Cost = Field(default_factory=Cost)
    context_window: int | None = None
    key_env: str
    enabled: bool = True
    settings: dict = Field(default_factory=dict)


class UsageRecord(BaseModel):
    run_id: str | None = None
    profile: str
    provider: str
    model: str
    capability: Capability
    input_units: int = 0
    output_units: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    ok: bool = True


class UsageSink(Protocol):
    async def record(self, usage: UsageRecord) -> None: ...


class NoProfileAvailable(LookupError):
    pass
