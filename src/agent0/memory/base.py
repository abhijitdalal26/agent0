from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agent0.core.types import new_id, utcnow

FactVerdict = Literal["new", "repeats", "changes", "ends"]


class Fact(BaseModel):
    id: str = Field(default_factory=new_id)
    scope: str = "global"
    scope_id: str | None = None
    content: str
    source_id: str | None = None
    valid_from: datetime = Field(default_factory=utcnow)
    valid_to: datetime | None = None
    superseded_by: str | None = None


class RunSummary(BaseModel):
    run_id: str
    summary: str
    outcome: str


class Recall(BaseModel):
    facts: list[Fact] = Field(default_factory=list)
    past_runs: list[RunSummary] = Field(default_factory=list)

    def render(self) -> str:
        parts = []
        if self.facts:
            parts.append("Known facts:\n" + "\n".join(f"- {f.content}" for f in self.facts))
        if self.past_runs:
            parts.append(
                "Similar past runs:\n" + "\n".join(f"- [{r.outcome}] {r.summary}" for r in self.past_runs)
            )
        return "\n\n".join(parts)


class MemoryStore(Protocol):
    async def recall(self, query: str, scope: str = "global", scope_id: str | None = None) -> Recall: ...
    async def save_run(self, summary: RunSummary) -> None: ...
    async def apply(self, fact: Fact, verdict: FactVerdict, target_id: str | None = None) -> None: ...
    async def similar_facts(self, content: str, limit: int = 5) -> list[Fact]: ...
