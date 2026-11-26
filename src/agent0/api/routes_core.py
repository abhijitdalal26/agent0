from __future__ import annotations

import mimetypes
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agent0.api.deps import Deps
from agent0.api.errors import ApiError, decode_cursor, decode_offset, encode_cursor, paginate
from agent0.api.shapes import approval_out, artifact_out, event_out, iso, run_out, task_out
from agent0.core.events import verify_chain
from agent0.core.types import Budget, NotifyLevel, Run, RunStatus, Task, utcnow
from agent0.policy.budget import daily_cap_reason

router = APIRouter()

Limit = Annotated[int, Query(ge=1, le=200)]
Cursor = Annotated[str | None, Query()]
ACTIVE = {RunStatus.PLANNING, RunStatus.EXECUTING, RunStatus.VERIFYING}
MAX_SCAN = 1000


async def _checks(deps: Any, run: Run) -> tuple[Any, list[dict[str, Any]], int, int]:
    spec = await deps.repos.task_specs.get(run.task_id)
    latest = {v.check_id: v for v in await deps.repos.verdicts.list(run.id)}
    verdicts = [v.model_dump(mode="json") for v in latest.values()]
    if spec is not None:
        for c in spec.criteria:
            if c.id not in latest:
                verdicts.append(
                    {
                        "check_id": c.id,
                        "type": str(c.type),
                        "status": "pending",
                        "evidence": "",
                        "score": None,
                        "cost_usd": 0.0,
                    }
                )
    total = len(spec.criteria) if spec is not None else len(latest)
    passed = sum(1 for v in latest.values() if v.status == "pass")
    return spec, verdicts, total, passed


async def _run_view(deps: Any, run: Run) -> dict[str, Any]:
    _, _, total, passed = await _checks(deps, run)
    return run_out(run, total, passed)


def _status(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(RunStatus(value))
    except ValueError:
        raise ApiError(422, "validation_error", f"unknown status {value!r}") from None


def _when(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ApiError(422, "validation_error", f"{name} must be an ISO datetime") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=utcnow().tzinfo)


@router.get("/stats/overview")
async def overview(deps: Deps) -> dict[str, Any]:
    runs = await deps.repos.runs.list(limit=MAX_SCAN)
    now = utcnow()
    day_ago = now - timedelta(hours=24)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def finished_recently(r: Run, status: RunStatus) -> bool:
        return r.status == status and (r.ended_at or r.started_at) >= day_ago

    return {
        "running": sum(1 for r in runs if r.status in ACTIVE),
        "waiting_approval": sum(1 for r in runs if r.status == RunStatus.WAITING_APPROVAL),
        "succeeded_24h": sum(1 for r in runs if finished_recently(r, RunStatus.SUCCEEDED)),
        "failed_24h": sum(1 for r in runs if finished_recently(r, RunStatus.FAILED)),
        "spend_today_usd": round(sum(r.cost_usd for r in runs if r.started_at >= midnight), 6),
    }


@router.get("/tasks")
async def list_tasks(
    deps: Deps,
    limit: Limit = 50,
    cursor: Cursor = None,
    status: str | None = None,
    agent: str | None = None,
    source: str | None = None,
    q: str | None = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: str | None = None,
) -> dict[str, Any]:
    since, until = _when(from_, "from"), _when(to, "to")
    tasks = await deps.repos.tasks.list(status=_status(status), limit=MAX_SCAN)
    needle = q.lower() if q else None
    tasks = [
        t
        for t in tasks
        if (agent is None or t.agent == agent)
        and (source is None or t.source == source)
        and (needle is None or needle in t.title.lower())
        and (since is None or t.created_at >= since)
        and (until is None or t.created_at < until)
    ]
    page = paginate(tasks, limit, cursor)
    items = []
    for t in page["items"]:
        runs = await deps.repos.runs.list(task_id=t.id, limit=MAX_SCAN)
        latest = await _run_view(deps, runs[0]) if runs else None
        items.append(task_out(t, len(runs), latest))
    return {"items": items, "next_cursor": page["next_cursor"]}


class BudgetIn(BaseModel):
    max_usd: float | None = Field(default=None, gt=0)
    max_steps: int | None = Field(default=None, gt=0)
    max_minutes: int | None = Field(default=None, gt=0)


class TaskCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=50_000)
    title: str | None = Field(default=None, max_length=200)
    agent: str = "executor"
    notify_level: NotifyLevel = NotifyLevel.MILESTONES
    budget: BudgetIn | None = None
    criteria: list[dict[str, Any]] | None = None


@router.post("/tasks", status_code=201)
async def create_task(body: TaskCreate, deps: Deps) -> dict[str, Any]:
    if body.agent not in deps.agents:
        raise ApiError(422, "unknown_agent", f"unknown agent {body.agent!r}")
    if reason := await daily_cap_reason(deps.settings, deps.repos):
        raise ApiError(429, "daily_budget_exceeded", reason)
    budget = Budget.model_validate(body.budget.model_dump(exclude_none=True) if body.budget else {})
    title = body.title or " ".join(body.prompt.split())[:80]
    task = Task(
        title=title,
        prompt=body.prompt,
        source="api",
        agent=body.agent,
        notify_level=body.notify_level,
        budget=budget,
    )
    if body.criteria:
        from agent0.verify.base import TaskSpec  # lazy: verify.base import is currently broken upstream

        try:
            spec = TaskSpec.model_validate({"goal": body.prompt, "criteria": body.criteria})
        except ValueError as exc:
            raise ApiError(422, "invalid_criteria", str(exc)) from None
    else:
        spec = None
    await deps.repos.tasks.create(task)
    if spec is not None:
        await deps.repos.task_specs.upsert(task.id, spec)
    run = await deps.orchestrator.submit(task)
    return {"task": task_out(task, 1), "run": await _run_view(deps, run)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, deps: Deps) -> dict[str, Any]:
    task = await deps.repos.tasks.get(task_id)
    if task is None:
        raise ApiError(404, "not_found", f"task {task_id} not found")
    runs = await deps.repos.runs.list(task_id=task_id, limit=MAX_SCAN)
    return {
        "task": task_out(task, len(runs), await _run_view(deps, runs[0]) if runs else None),
        "runs": [await _run_view(deps, r) for r in runs],
    }


@router.post("/tasks/{task_id}/retry", status_code=201)
async def retry_task(task_id: str, deps: Deps) -> dict[str, Any]:
    if await deps.repos.tasks.get(task_id) is None:
        raise ApiError(404, "not_found", f"task {task_id} not found")
    run = await deps.orchestrator.retry(task_id)
    return {"run": await _run_view(deps, run)}


@router.get("/runs")
async def list_runs(
    deps: Deps,
    limit: Limit = 50,
    cursor: Cursor = None,
    status: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    offset = decode_offset(cursor)
    runs = await deps.repos.runs.list(task_id=task_id, status=_status(status), limit=limit + 1, offset=offset)
    more = len(runs) > limit
    return {
        "items": [await _run_view(deps, r) for r in runs[:limit]],
        "next_cursor": encode_cursor(str(offset + limit)) if more else None,
    }


async def _get_run(deps: Any, run_id: str) -> Run:
    run = await deps.repos.runs.get(run_id)
    if run is None:
        raise ApiError(404, "not_found", f"run {run_id} not found")
    return run


@router.get("/runs/{run_id}")
async def get_run(run_id: str, deps: Deps) -> dict[str, Any]:
    run = await _get_run(deps, run_id)
    spec, verdicts, total, passed = await _checks(deps, run)
    return {
        "run": run_out(run, total, passed),
        "spec": spec.model_dump(mode="json") if spec is not None else None,
        "verdicts": verdicts,
        "artifacts": [artifact_out(a) for a in await deps.repos.artifacts.list(run_id)],
    }


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: str,
    deps: Deps,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    await _get_run(deps, run_id)
    events = await deps.repos.events.list(run_id, after_seq=after_seq, limit=limit + 1)
    return {
        "items": [event_out(e) for e in events[:limit]],
        "next_cursor": encode_cursor(str(events[limit - 1].seq)) if len(events) > limit else None,
    }


@router.get("/runs/{run_id}/verify")
async def verify_run_events(run_id: str, deps: Deps) -> dict[str, Any]:
    """Recompute the event hash chain: proof the recorded trail wasn't altered after the fact."""
    await _get_run(deps, run_id)
    events = await deps.repos.events.list(run_id, limit=MAX_SCAN)
    ok, bad_seq = verify_chain(events)
    head = events[-1].hash if events else None
    return {
        "ok": ok,
        "events": len(events),
        "bad_seq": bad_seq,
        "head_hash": head,
    }


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str, deps: Deps) -> dict[str, Any]:
    run = await _get_run(deps, run_id)
    if run.status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.STOPPED}:
        raise ApiError(409, "run_finished", f"run is already {run.status}")
    await deps.orchestrator.stop(run_id)
    return {"run": await _run_view(deps, await _get_run(deps, run_id))}


def confined_path(root: Path, artifact_path: str) -> Path:
    rel = artifact_path.replace("\\", "/")
    if rel.startswith("/workspace/"):
        rel = rel[len("/workspace/") :]
    if PurePosixPath(rel).is_absolute() or Path(rel).is_absolute():
        raise ApiError(403, "forbidden", "artifact path is outside the run workspace")
    base = root.resolve()
    target = (base / rel).resolve()
    if not target.is_relative_to(base):
        raise ApiError(403, "forbidden", "artifact path is outside the run workspace")
    return target


@router.get("/runs/{run_id}/artifacts/{artifact_id}")
async def download_artifact(
    run_id: str, artifact_id: str, deps: Deps, download: bool = False
) -> FileResponse:
    artifact = await deps.repos.artifacts.get(artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise ApiError(404, "not_found", f"artifact {artifact_id} not found")
    target = confined_path(deps.settings.workspace_root / run_id, artifact.path)
    if not target.is_file():
        raise ApiError(404, "not_found", "artifact file is not in the run workspace")
    media = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return FileResponse(
        target,
        media_type=media,
        filename=target.name,
        content_disposition_type="attachment" if download else "inline",
    )


@router.get("/approvals")
async def list_approvals(
    deps: Deps, limit: Limit = 50, cursor: Cursor = None, status: str | None = None, run_id: str | None = None
) -> dict[str, Any]:
    if status in {"approved", "rejected"}:
        rows = [
            r
            for r in await deps.repos.approvals.list(run_id=run_id, limit=MAX_SCAN)
            if approval_out(r)["status"] == status
        ]
    else:
        rows = await deps.repos.approvals.list(status=status, run_id=run_id, limit=MAX_SCAN)
    return paginate(rows, limit, cursor, approval_out)


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=2000)


@router.post("/approvals/{approval_id}")
async def decide_approval(approval_id: str, body: Decision, deps: Deps) -> dict[str, Any]:
    row = await deps.repos.approvals.get(approval_id)
    if row is None:
        raise ApiError(404, "not_found", f"approval {approval_id} not found")
    if row["status"] != "pending":
        raise ApiError(409, "already_decided", "approval was already decided")
    await deps.orchestrator.decide_approval(approval_id, body.decision, "dashboard", body.note)
    fresh = await deps.repos.approvals.get(approval_id)
    return approval_out(fresh or row)


@router.get("/events")
async def global_events(
    deps: Deps,
    limit: Limit = 100,
    cursor: Cursor = None,
    type: str | None = None,
    agent: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    before = _when(decode_cursor(cursor), "cursor") if cursor else None
    types = [t for t in (type or "").split(",") if t] or None
    events = await deps.repos.events.list_global(types=types, run_id=run_id, before=before, limit=limit + 1)
    more = len(events) > limit
    events = events[:limit]
    last = events[-1] if events else None
    if agent:
        agents: dict[str, str] = {}
        kept = []
        for e in events:
            if e.run_id not in agents:
                run = await deps.repos.runs.get(e.run_id)
                agents[e.run_id] = run.agent if run else ""
            if agents[e.run_id] == agent:
                kept.append(e)
        events = kept
    return {
        "items": [event_out(e) for e in events],
        "next_cursor": encode_cursor(iso(last.created_at) or "") if more and last else None,
    }
