from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    """A row or passage returned by a knowledge source; `source_id` is what answers must cite."""

    source_id: str
    source: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSource(Protocol):
    name: str
    kind: str

    async def search(self, query: str, limit: int = 5) -> list[SourceRecord]: ...
    async def get(self, source_id: str) -> SourceRecord | None: ...
