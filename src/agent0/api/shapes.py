from __future__ import annotations

from datetime import datetime
from typing import Any

from agent0.core.types import Artifact, Event, Run, Task
from agent0.models.base import ModelProfile
from agent0.models.registry import resolve_secret

_APPROVAL_STATUS = {
    "approve": "approved",
    "reject": "rejected",
    "approved": "approved",
    "rejected": "rejected",
}


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def run_out(run: Run, checks_total: int = 0, checks_passed: int = 0) -> dict[str, Any]:
    return {
        "id": run.id,
        "task_id": run.task_id,
        "attempt": run.attempt,
        "status": str(run.status),
        "agent": run.agent,
        "model_profile": run.model_profile or "",
        "current_step": run.current_step,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "cost_usd": run.cost_usd,
        "started_at": iso(run.started_at),
        "ended_at": iso(run.ended_at),
        "checks_total": checks_total,
        "checks_passed": checks_passed,
    }


def task_out(task: Task, attempts: int, latest_run: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "prompt": task.prompt,
        "source": task.source,
        "agent": task.agent,
        "status": str(task.status),
        "attempts": attempts,
        "notify_level": str(task.notify_level),
        "budget": {
            "max_usd": task.budget.max_usd,
            "max_steps": task.budget.max_steps,
            "max_minutes": task.budget.max_minutes,
        },
        "created_at": iso(task.created_at),
        "latest_run": latest_run,
    }


def event_out(event: Event) -> dict[str, Any]:
    return event.model_dump(mode="json")


def approval_out(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "question": row["question"],
        "options": row.get("options") or [],
        "status": _APPROVAL_STATUS.get(row["status"], row["status"]),
        "decided_by": row.get("decided_by"),
        "decided_at": iso(row.get("decided_at")),
        "note": row.get("note"),
    }


def artifact_out(artifact: Artifact) -> dict[str, Any]:
    return {
        "id": artifact.id,
        "run_id": artifact.run_id,
        "path": artifact.path,
        "kind": artifact.kind,
        "size": artifact.size,
        "url": f"/api/v1/runs/{artifact.run_id}/artifacts/{artifact.id}",
    }


def profile_out(p: ModelProfile) -> dict[str, Any]:
    return {
        "id": p.name,
        "name": p.name,
        "provider": p.provider,
        "model": p.model,
        "capability": str(p.capability),
        "tags": p.tags,
        "cost": p.cost.model_dump(),
        "context_window": p.context_window,
        "key_env": p.key_env,
        "key_configured": bool(resolve_secret(p.key_env)),
        "enabled": p.enabled,
        "settings": p.settings,
    }
