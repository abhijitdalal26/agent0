from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from agent0.api.deps import ApiDeps, Deps
from agent0.api.errors import ApiError
from agent0.api.shapes import event_out
from agent0.core.types import Event, RunStatus

router = APIRouter()

HEARTBEAT_SECONDS = 15
REPLAY_PAGE = 1000
TERMINAL = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.STOPPED}


def _frame(event: Event, with_id: bool) -> dict[str, Any]:
    frame: dict[str, Any] = {"event": str(event.type), "data": json.dumps(event_out(event))}
    if with_id:
        frame["id"] = str(event.seq)
    return frame


def _last_seq(request: Request) -> int:
    raw = request.headers.get("last-event-id", "")
    return int(raw) if raw.isdigit() else 0


async def _run_events(deps: ApiDeps, run_id: str, last_seq: int) -> AsyncIterator[dict[str, Any]]:
    live = deps.event_stream.subscribe(run_id)
    first = asyncio.ensure_future(anext(live, None))
    try:
        # Let the subscriber attach before replaying so events between the two are not lost.
        await asyncio.sleep(0)
        while True:
            batch = await deps.repos.events.list(run_id, after_seq=last_seq, limit=REPLAY_PAGE)
            for event in batch:
                last_seq = event.seq
                yield _frame(event, True)
            if len(batch) < REPLAY_PAGE:
                break
        run = await deps.repos.runs.get(run_id)
        if run is not None and run.status in TERMINAL:
            return
        event = await first
        while event is not None:
            if event.seq > last_seq:
                last_seq = event.seq
                yield _frame(event, True)
            event = await anext(live, None)
    finally:
        first.cancel()
        aclose = getattr(live, "aclose", None)
        if aclose:
            await aclose()


async def _all_events(deps: ApiDeps) -> AsyncIterator[dict[str, Any]]:
    live = deps.event_stream.subscribe(None)
    try:
        async for event in live:
            yield _frame(event, False)
    finally:
        aclose = getattr(live, "aclose", None)
        if aclose:
            await aclose()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request, deps: Deps) -> EventSourceResponse:
    if await deps.repos.runs.get(run_id) is None:
        raise ApiError(404, "not_found", f"run {run_id} not found")
    return EventSourceResponse(
        _run_events(deps, run_id, _last_seq(request)),
        ping=HEARTBEAT_SECONDS,
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/stream")
async def stream_all(deps: Deps) -> EventSourceResponse:
    return EventSourceResponse(_all_events(deps), ping=HEARTBEAT_SECONDS, headers={"X-Accel-Buffering": "no"})
