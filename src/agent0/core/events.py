from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Protocol

from agent0.core.types import Event, EventType


class EventSink(Protocol):
    async def emit(self, run_id: str, type: EventType, payload: dict[str, Any] | None = None) -> Event: ...


class MemoryEventSink:
    """In-process sink for tests and the CLI; the Postgres sink persists to `events`."""

    def __init__(self) -> None:
        self.events: list[Event] = []
        self._seq: dict[str, int] = defaultdict(int)
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def emit(self, run_id: str, type: EventType, payload: dict[str, Any] | None = None) -> Event:
        self._seq[run_id] += 1
        event = Event(run_id=run_id, seq=self._seq[run_id], type=type, payload=payload or {})
        self.events.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)
        return event

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(queue)
        return queue
