from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import BaseModel

from agent0.core.types import Artifact, Event, EventType, Run, RunStatus, Task, new_id, utcnow


class FakeCriterion(BaseModel):
    id: str
    description: str = ""
    type: str = "command"
    config: dict = {}


class FakeSpec(BaseModel):
    goal: str = ""
    steps: list[str] = []
    criteria: list[FakeCriterion] = []


class FakeVerdict(BaseModel):
    check_id: str
    type: str = "command"
    status: str
    evidence: str = ""
    score: float | None = None
    cost_usd: float = 0.0


class _Tasks:
    def __init__(self) -> None:
        self.rows: dict[str, Task] = {}

    async def create(self, task: Task) -> Task:
        self.rows[task.id] = task
        return task

    async def get(self, task_id: str) -> Task | None:
        return self.rows.get(task_id)

    async def list(self, status: str | None = None, limit: int = 50, offset: int = 0) -> list[Task]:
        rows = sorted(self.rows.values(), key=lambda t: t.created_at, reverse=True)
        return [t for t in rows if status is None or t.status == status][offset : offset + limit]


class _Runs:
    def __init__(self) -> None:
        self.rows: dict[str, Run] = {}

    async def create(self, run: Run) -> Run:
        self.rows[run.id] = run
        return run

    async def get(self, run_id: str) -> Run | None:
        return self.rows.get(run_id)

    async def list(
        self, task_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Run]:
        rows = sorted(self.rows.values(), key=lambda r: r.started_at, reverse=True)
        rows = [
            r
            for r in rows
            if (task_id is None or r.task_id == task_id) and (status is None or r.status == status)
        ]
        return rows[offset : offset + limit]


class _Specs:
    def __init__(self) -> None:
        self.rows: dict[str, FakeSpec] = {}

    async def get(self, task_id: str) -> FakeSpec | None:
        return self.rows.get(task_id)

    async def upsert(self, task_id: str, spec: Any) -> None:
        self.rows[task_id] = spec


class _Events:
    def __init__(self) -> None:
        self.rows: list[Event] = []

    async def list(self, run_id: str, after_seq: int = 0, limit: int = 1000) -> list[Event]:
        return [e for e in self.rows if e.run_id == run_id and e.seq > after_seq][:limit]

    async def list_global(self, types=None, run_id=None, since=None, before=None, limit: int = 100):
        rows = sorted(self.rows, key=lambda e: e.created_at, reverse=True)
        return [
            e
            for e in rows
            if (not types or e.type in types)
            and (run_id is None or e.run_id == run_id)
            and (before is None or e.created_at < before)
        ][:limit]


class _Verdicts:
    def __init__(self) -> None:
        self.rows: dict[str, list[FakeVerdict]] = {}

    async def list(self, run_id: str) -> list[FakeVerdict]:
        return self.rows.get(run_id, [])


class _Approvals:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def get(self, approval_id: str):
        return self.rows.get(approval_id)

    async def list(self, status: str | None = None, run_id: str | None = None, limit: int = 100):
        return [
            r
            for r in self.rows.values()
            if (status is None or r["status"] == status) and (run_id is None or r["run_id"] == run_id)
        ][:limit]


class _Artifacts:
    def __init__(self) -> None:
        self.rows: dict[str, Artifact] = {}

    async def get(self, artifact_id: str) -> Artifact | None:
        return self.rows.get(artifact_id)

    async def list(self, run_id: str) -> list[Artifact]:
        return [a for a in self.rows.values() if a.run_id == run_id]


class _Usage:
    async def summary(self, group_by=("provider",), since=None, until=None):
        return [{group_by[0]: "groq", "calls": 2, "cost_usd": 0.5}]


class _Profiles:
    def __init__(self) -> None:
        self.rows: dict[str, Any] = {}

    async def upsert(self, profile) -> None:
        self.rows[profile.name] = profile

    async def list(self, capability=None, enabled_only=False):
        return list(self.rows.values())

    async def delete(self, name: str) -> bool:
        return self.rows.pop(name, None) is not None


class _Extensions:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def upsert(self, id, kind, name, description="", enabled=True, config=None) -> None:
        self.rows[id] = {"id": id, "kind": kind, "name": name, "enabled": enabled}

    async def list(self, kind=None):
        return list(self.rows.values())


class _Schedules:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def upsert(self, id, agent, cron, prompt, enabled=True) -> None:
        self.rows[id] = {
            "id": id,
            "agent": agent,
            "cron": cron,
            "prompt": prompt,
            "enabled": enabled,
            "last_run_at": None,
        }

    async def get(self, id):
        return self.rows.get(id)

    async def list(self, enabled_only=False):
        return list(self.rows.values())

    async def delete(self, id) -> bool:
        return self.rows.pop(id, None) is not None


class _Facts:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def list(self, scope=None, scope_id=None, include_expired=False, limit=500):
        return [r for r in self.rows if include_expired or r["valid_to"] is None][:limit]

    async def search(self, q, limit=50):
        return [r for r in self.rows if r["valid_to"] is None and q.lower() in r["content"].lower()][:limit]

    async def get(self, fact_id):
        return next((r for r in self.rows if r["id"] == fact_id), None)

    async def history(self, fact_id):
        return [r for r in self.rows if r["id"] == fact_id]


class FakeRepos:
    def __init__(self) -> None:
        self.tasks = _Tasks()
        self.runs = _Runs()
        self.task_specs = _Specs()
        self.events = _Events()
        self.verdicts = _Verdicts()
        self.approvals = _Approvals()
        self.artifacts = _Artifacts()
        self.usage = _Usage()
        self.model_profiles = _Profiles()
        self.extensions = _Extensions()
        self.schedules = _Schedules()
        self.facts = _Facts()

    async def seed_run(
        self, status: RunStatus = RunStatus.EXECUTING, agent: str = "executor", **task_kw
    ) -> Run:
        title = task_kw.pop("title", "t")
        task = await self.tasks.create(Task(title=title, prompt="p", agent=agent, **task_kw))
        return await self.runs.create(Run(task_id=task.id, agent=agent, status=status))

    def add_events(self, run_id: str, n: int) -> list[Event]:
        base = utcnow()
        evs = [
            Event(
                run_id=run_id,
                seq=i,
                type=EventType.TOOL_CALL,
                payload={"i": i},
                created_at=base + timedelta(seconds=i),
            )
            for i in range(1, n + 1)
        ]
        self.events.rows.extend(evs)
        return evs

    def add_approval(self, run_id: str, status: str = "pending") -> dict[str, Any]:
        row = {
            "id": new_id(),
            "run_id": run_id,
            "question": "ok?",
            "options": ["approve", "reject"],
            "status": status,
            "decided_by": None,
            "decided_at": None,
            "note": None,
        }
        self.approvals.rows[row["id"]] = row
        return row


class FakeOrchestrator:
    def __init__(self, repos: FakeRepos) -> None:
        self.repos = repos
        self.calls: list[tuple] = []

    async def submit(self, task: Task) -> Run:
        self.calls.append(("submit", task.id))
        return await self.repos.runs.create(Run(task_id=task.id, agent=task.agent))

    async def stop(self, run_id: str) -> None:
        self.calls.append(("stop", run_id))
        self.repos.runs.rows[run_id].status = RunStatus.STOPPED

    async def retry(self, task_id: str) -> Run:
        self.calls.append(("retry", task_id))
        return await self.repos.runs.create(Run(task_id=task_id, attempt=2))

    async def decide_approval(self, approval_id: str, decision: str, by: str, note: str | None) -> None:
        self.calls.append(("decide", approval_id, decision, by, note))
        row = self.repos.approvals.rows[approval_id]
        row.update(status="approved" if decision == "approve" else "rejected", decided_by=by, note=note)


class FakeStream:
    def __init__(self, live: list[Event] | None = None) -> None:
        self.live = live or []

    async def subscribe(self, run_id: str | None = None):
        for e in self.live:
            if run_id is None or e.run_id == run_id:
                yield e
