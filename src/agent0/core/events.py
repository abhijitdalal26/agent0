from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from typing import Any, Protocol

from agent0.core.types import Event, EventType


def event_hash(
    run_id: str,
    seq: int,
    type: EventType | str,
    payload: dict[str, Any],
    created_at: datetime,
    prev_hash: str | None,
) -> str:
    """One link of the per-run hash chain. Canonical JSON keeps the digest stable across writers."""
    body = {
        "run_id": run_id,
        "seq": seq,
        "type": str(type),
        "payload": payload,
        "created_at": created_at.isoformat(),
        "prev_hash": prev_hash or "",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list[Event]) -> tuple[bool, int | None]:
    """Recompute the chain; returns (ok, first_bad_seq). Events without a hash break it."""
    prev: str | None = None
    for e in sorted(events, key=lambda e: e.seq):
        if e.hash is None:
            return False, e.seq
        expected = event_hash(e.run_id, e.seq, e.type, e.payload, e.created_at, prev)
        if e.hash != expected or e.prev_hash != prev:
            return False, e.seq
        prev = e.hash
    return True, None


class EventSink(Protocol):
    async def emit(self, run_id: str, type: EventType, payload: dict[str, Any] | None = None) -> Event: ...


class MemoryEventSink:
    """In-process sink for tests and the CLI; the Postgres sink persists to `events`."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self._seq: dict[str, int] = defaultdict(int)
        self._heads: dict[str, str] = {}
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def emit(self, run_id: str, type: EventType, payload: dict[str, Any] | None = None) -> Event:
        self._seq[run_id] += 1
        prev = self._heads.get(run_id)
        event = Event(run_id=run_id, seq=self._seq[run_id], type=type, payload=payload or {})
        event.hash = event_hash(run_id, event.seq, type, event.payload, event.created_at, prev)
        event.prev_hash = prev
        self._heads[run_id] = event.hash
        self.events.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue
