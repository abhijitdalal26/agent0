from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from agent0.core.types import Artifact, Budget, Event, EventType, Run, Task, new_id
from agent0.models.base import ModelProfile, UsageRecord

if TYPE_CHECKING:
    from agent0.verify.base import TaskSpec, Verdict

EVENTS_CHANNEL = "agent0_events"
_NOTIFY_LIMIT = 7000

Row = dict[str, Any]


def _clean(row: Row | None) -> Row | None:
    if row is None:
        return None
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}


def _clean_all(rows: Sequence[Row]) -> list[Row]:
    return [_clean(r) for r in rows]  # type: ignore[misc]


class _Repo:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool

    async def _one(self, sql: str, params: Sequence[Any] = ()) -> Row | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)  # type: ignore[arg-type]
            return _clean(await cur.fetchone())

    async def _all(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)  # type: ignore[arg-type]
            return _clean_all(await cur.fetchall())

    async def _exec(self, sql: str, params: Sequence[Any] = ()) -> int:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)  # type: ignore[arg-type]
            return cur.rowcount


def _set_clause(fields: dict[str, Any], allowed: set[str]) -> tuple[str, list[Any]]:
    bad = set(fields) - allowed
    if bad:
        raise ValueError(f"cannot update columns: {sorted(bad)}")
    cols = list(fields)
    return ", ".join(f"{c} = %s" for c in cols), [fields[c] for c in cols]


def _task(row: Row) -> Task:
    return Task.model_validate({**row, "budget": Budget.model_validate(row["budget"])})


class TaskRepo(_Repo):
    async def create(self, task: Task) -> Task:
        await self._exec(
            "INSERT INTO tasks (id, title, prompt, source, agent, status, notify_level, budget, chat_id,"
            " created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                task.id,
                task.title,
                task.prompt,
                task.source,
                task.agent,
                str(task.status),
                str(task.notify_level),
                Jsonb(task.budget.model_dump()),
                task.chat_id,
                task.created_at,
            ),
        )
        return task

    async def get(self, task_id: str) -> Task | None:
        row = await self._one("SELECT * FROM tasks WHERE id = %s", (task_id,))
        return _task(row) if row else None

    async def list(self, status: str | None = None, limit: int = 50, offset: int = 0) -> list[Task]:
        rows = await self._all(
            "SELECT * FROM tasks WHERE (%s::text IS NULL OR status = %s) ORDER BY created_at DESC"
            " LIMIT %s OFFSET %s",
            (status, status, limit, offset),
        )
        return [_task(r) for r in rows]

    async def set_status(self, task_id: str, status: str) -> None:
        await self._exec("UPDATE tasks SET status = %s WHERE id = %s", (str(status), task_id))


class RunRepo(_Repo):
    _UPDATABLE = {
        "status",
        "model_profile",
        "current_step",
        "temporal_workflow_id",
        "tokens_in",
        "tokens_out",
        "cost_usd",
        "ended_at",
    }

    async def create(self, run: Run, temporal_workflow_id: str | None = None) -> Run:
        await self._exec(
            "INSERT INTO runs (id, task_id, attempt, status, agent, model_profile, current_step,"
            " temporal_workflow_id, tokens_in, tokens_out, cost_usd, started_at, ended_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                run.id,
                run.task_id,
                run.attempt,
                str(run.status),
                run.agent,
                run.model_profile,
                run.current_step,
                temporal_workflow_id,
                run.tokens_in,
                run.tokens_out,
                run.cost_usd,
                run.started_at,
                run.ended_at,
            ),
        )
        return run

    async def get(self, run_id: str) -> Run | None:
        row = await self._one("SELECT * FROM runs WHERE id = %s", (run_id,))
        return Run.model_validate(row) if row else None

    async def list(
        self, task_id: str | None = None, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[Run]:
        rows = await self._all(
            "SELECT * FROM runs WHERE (%s::text IS NULL OR task_id = %s)"
            " AND (%s::text IS NULL OR status = %s)"
            " ORDER BY started_at DESC LIMIT %s OFFSET %s",
            (task_id, task_id, status, status, limit, offset),
        )
        return [Run.model_validate(r) for r in rows]

    async def update(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        if "status" in fields:
            fields["status"] = str(fields["status"])
        clause, params = _set_clause(fields, self._UPDATABLE)
        await self._exec(f"UPDATE runs SET {clause} WHERE id = %s", [*params, run_id])

    async def add_usage(self, run_id: str, tokens_in: int, tokens_out: int, cost_usd: float) -> None:
        await self._exec(
            "UPDATE runs SET tokens_in = tokens_in + %s, tokens_out = tokens_out + %s,"
            " cost_usd = cost_usd + %s WHERE id = %s",
            (tokens_in, tokens_out, cost_usd, run_id),
        )


class TaskSpecRepo(_Repo):
    async def upsert(self, task_id: str, spec: TaskSpec) -> None:
        await self._exec(
            "INSERT INTO task_specs (task_id, goal, steps, criteria) VALUES (%s,%s,%s,%s)"
            " ON CONFLICT (task_id) DO UPDATE SET goal = EXCLUDED.goal, steps = EXCLUDED.steps,"
            " criteria = EXCLUDED.criteria",
            (
                task_id,
                spec.goal,
                Jsonb(spec.steps),
                Jsonb([c.model_dump(mode="json") for c in spec.criteria]),
            ),
        )

    async def get(self, task_id: str) -> TaskSpec | None:
        row = await self._one("SELECT goal, steps, criteria FROM task_specs WHERE task_id = %s", (task_id,))
        from agent0.verify.base import TaskSpec  # lazy: verify.base currently fails to import (see report)

        return TaskSpec.model_validate(row) if row else None


def _event(row: Row) -> Event:
    return Event.model_validate({**row, "type": EventType(row["type"])})


def _event_notice(event: Event) -> str:
    body = event.model_dump_json()
    if len(body.encode()) <= _NOTIFY_LIMIT:
        return body
    # NOTIFY payloads are capped near 8000 bytes; subscribers refetch by (run_id, seq).
    slim = event.model_copy(update={"payload": {"truncated": True}})
    return slim.model_dump_json()


class EventRepo(_Repo):
    async def append(
        self, run_id: str, type: EventType, payload: dict[str, Any] | None = None, notify: bool = True
    ) -> Event:
        event_id = new_id()
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (run_id,))
            cur = await conn.execute(
                "INSERT INTO events (id, run_id, seq, type, payload)"
                " SELECT %s::text, %s::text, COALESCE(MAX(seq), 0) + 1, %s::text, %s::jsonb"
                " FROM events WHERE run_id = %s"
                " RETURNING *",
                (event_id, run_id, str(type), Jsonb(payload or {}), run_id),
            )
            event = _event(await cur.fetchone())  # type: ignore[arg-type]
            if notify:
                await conn.execute("SELECT pg_notify(%s, %s)", (EVENTS_CHANNEL, _event_notice(event)))
        return event

    async def list(self, run_id: str, after_seq: int = 0, limit: int = 1000) -> list[Event]:
        rows = await self._all(
            "SELECT * FROM events WHERE run_id = %s AND seq > %s ORDER BY seq LIMIT %s",
            (run_id, after_seq, limit),
        )
        return [_event(r) for r in rows]

    async def list_global(
        self,
        types: Sequence[str] | None = None,
        run_id: str | None = None,
        since: datetime | None = None,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        rows = await self._all(
            "SELECT * FROM events WHERE (%s::text[] IS NULL OR type = ANY(%s))"
            " AND (%s::text IS NULL OR run_id = %s)"
            " AND (%s::timestamptz IS NULL OR created_at >= %s)"
            " AND (%s::timestamptz IS NULL OR created_at < %s)"
            " ORDER BY created_at DESC, seq DESC LIMIT %s",
            (
                list(types) if types else None,
                list(types) if types else None,
                run_id,
                run_id,
                since,
                since,
                before,
                before,
                limit,
            ),
        )
        return [_event(r) for r in rows]


class VerdictRepo(_Repo):
    async def add(self, run_id: str, verdict: Verdict) -> str:
        verdict_id = new_id()
        await self._exec(
            "INSERT INTO verdicts (id, run_id, check_id, type, status, evidence, score, cost_usd)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                verdict_id,
                run_id,
                verdict.check_id,
                str(verdict.type),
                str(verdict.status),
                verdict.evidence,
                verdict.score,
                verdict.cost_usd,
            ),
        )
        return verdict_id

    async def list(self, run_id: str) -> list[Verdict]:
        rows = await self._all(
            "SELECT check_id, type, status, evidence, score, cost_usd FROM verdicts WHERE run_id = %s"
            " ORDER BY id",
            (run_id,),
        )
        from agent0.verify.base import Verdict

        return [Verdict.model_validate(r) for r in rows]


class ApprovalRepo(_Repo):
    async def create(self, run_id: str, question: str, options: Sequence[str] = ("approve", "reject")) -> Row:
        row = await self._one(
            "INSERT INTO approvals (id, run_id, question, options) VALUES (%s,%s,%s,%s) RETURNING *",
            (new_id(), run_id, question, Jsonb(list(options))),
        )
        return row  # type: ignore[return-value]

    async def get(self, approval_id: str) -> Row | None:
        return await self._one("SELECT * FROM approvals WHERE id = %s", (approval_id,))

    async def list(self, status: str | None = None, run_id: str | None = None, limit: int = 100) -> list[Row]:
        return await self._all(
            "SELECT * FROM approvals WHERE (%s::text IS NULL OR status = %s)"
            " AND (%s::text IS NULL OR run_id = %s) ORDER BY id DESC LIMIT %s",
            (status, status, run_id, run_id, limit),
        )

    async def decide(
        self, approval_id: str, status: str, decided_by: str, note: str | None = None
    ) -> Row | None:
        # Only a pending approval can be decided; a second decision is a no-op returning None.
        return await self._one(
            "UPDATE approvals SET status = %s, decided_by = %s, decided_at = now(), note = %s"
            " WHERE id = %s AND status = 'pending' RETURNING *",
            (status, decided_by, note, approval_id),
        )


class ArtifactRepo(_Repo):
    async def add(self, artifact: Artifact) -> Artifact:
        await self._exec(
            "INSERT INTO artifacts (id, run_id, path, kind, size, storage_url) VALUES (%s,%s,%s,%s,%s,%s)",
            (artifact.id, artifact.run_id, artifact.path, artifact.kind, artifact.size, artifact.url),
        )
        return artifact

    async def get(self, artifact_id: str) -> Artifact | None:
        row = await self._one(
            "SELECT id, run_id, path, kind, size, storage_url AS url FROM artifacts WHERE id = %s",
            (artifact_id,),
        )
        return Artifact.model_validate(row) if row else None

    async def list(self, run_id: str) -> list[Artifact]:
        rows = await self._all(
            "SELECT id, run_id, path, kind, size, storage_url AS url FROM artifacts WHERE run_id = %s"
            " ORDER BY path",
            (run_id,),
        )
        return [Artifact.model_validate(r) for r in rows]


_USAGE_DIMS = {
    "provider": "u.provider",
    "capability": "u.capability",
    "agent": "COALESCE(r.agent, 'unknown')",
    "day": "to_char(date_trunc('day', u.created_at), 'YYYY-MM-DD')",
}


class UsageRepo(_Repo):
    async def insert(self, usage: UsageRecord) -> None:
        await self._exec(
            "INSERT INTO usage (run_id, profile, provider, model, capability, input_units, output_units,"
            " cost_usd, latency_ms, ok) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                usage.run_id,
                usage.profile,
                usage.provider,
                usage.model,
                str(usage.capability),
                usage.input_units,
                usage.output_units,
                usage.cost_usd,
                usage.latency_ms,
                usage.ok,
            ),
        )

    async def list(
        self, since: datetime | None = None, until: datetime | None = None, limit: int = 1000
    ) -> list[Row]:
        return await self._all(
            "SELECT u.*, r.agent FROM usage u LEFT JOIN runs r ON r.id = u.run_id"
            " WHERE (%s::timestamptz IS NULL OR u.created_at >= %s)"
            " AND (%s::timestamptz IS NULL OR u.created_at < %s) ORDER BY u.id DESC LIMIT %s",
            (since, since, until, until, limit),
        )

    async def summary(
        self,
        group_by: Sequence[str] = ("provider", "capability", "agent", "day"),
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Row]:
        unknown = [g for g in group_by if g not in _USAGE_DIMS]
        if unknown or not group_by:
            raise ValueError(f"group_by must be a non-empty subset of {sorted(_USAGE_DIMS)}")
        dims = ", ".join(f"{_USAGE_DIMS[g]} AS {g}" for g in group_by)
        keys = ", ".join(str(i + 1) for i in range(len(group_by)))
        return await self._all(
            f"SELECT {dims}, COUNT(*)::int AS calls, SUM(u.input_units)::bigint AS input_units,"
            " SUM(u.output_units)::bigint AS output_units, SUM(u.cost_usd) AS cost_usd,"
            " COUNT(*) FILTER (WHERE NOT u.ok)::int AS errors"
            " FROM usage u LEFT JOIN runs r ON r.id = u.run_id"
            " WHERE (%s::timestamptz IS NULL OR u.created_at >= %s)"
            " AND (%s::timestamptz IS NULL OR u.created_at < %s)"
            f" GROUP BY {keys} ORDER BY {keys}",
            (since, since, until, until),
        )


class ModelProfileRepo(_Repo):
    async def upsert(self, profile: ModelProfile) -> None:
        await self._exec(
            "INSERT INTO model_profiles (name, provider, model, capability, tags, cost, settings, key_env,"
            " enabled) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (name) DO UPDATE SET provider = EXCLUDED.provider, model = EXCLUDED.model,"
            " capability = EXCLUDED.capability, tags = EXCLUDED.tags, cost = EXCLUDED.cost,"
            " settings = EXCLUDED.settings, key_env = EXCLUDED.key_env, enabled = EXCLUDED.enabled",
            (
                profile.name,
                profile.provider,
                profile.model,
                str(profile.capability),
                profile.tags,
                Jsonb(profile.cost.model_dump()),
                Jsonb(profile.settings),
                profile.key_env,
                profile.enabled,
            ),
        )

    async def get(self, name: str) -> ModelProfile | None:
        row = await self._one("SELECT * FROM model_profiles WHERE name = %s", (name,))
        return ModelProfile.model_validate(row) if row else None

    async def list(self, capability: str | None = None, enabled_only: bool = False) -> list[ModelProfile]:
        rows = await self._all(
            "SELECT * FROM model_profiles WHERE (%s::text IS NULL OR capability = %s)"
            " AND (NOT %s OR enabled) ORDER BY name",
            (capability, capability, enabled_only),
        )
        return [ModelProfile.model_validate(r) for r in rows]

    async def set_enabled(self, name: str, enabled: bool) -> bool:
        return await self._exec("UPDATE model_profiles SET enabled = %s WHERE name = %s", (enabled, name)) > 0

    async def delete(self, name: str) -> bool:
        return await self._exec("DELETE FROM model_profiles WHERE name = %s", (name,)) > 0


class ExtensionRepo(_Repo):
    async def upsert(
        self,
        id: str,
        kind: str,
        name: str,
        description: str = "",
        enabled: bool = True,
        config: dict[str, Any] | None = None,
    ) -> None:
        await self._exec(
            "INSERT INTO extensions (id, kind, name, description, enabled, config) VALUES (%s,%s,%s,%s,%s,%s)"
            " ON CONFLICT (id) DO UPDATE SET kind = EXCLUDED.kind, name = EXCLUDED.name,"
            " description = EXCLUDED.description, enabled = EXCLUDED.enabled, config = EXCLUDED.config",
            (id, kind, name, description, enabled, Jsonb(config or {})),
        )

    async def get(self, id: str) -> Row | None:
        return await self._one("SELECT * FROM extensions WHERE id = %s", (id,))

    async def list(self, kind: str | None = None) -> list[Row]:
        return await self._all(
            "SELECT * FROM extensions WHERE (%s::text IS NULL OR kind = %s) ORDER BY kind, name", (kind, kind)
        )

    async def set_enabled(self, id: str, enabled: bool) -> bool:
        return await self._exec("UPDATE extensions SET enabled = %s WHERE id = %s", (enabled, id)) > 0

    async def delete(self, id: str) -> bool:
        return await self._exec("DELETE FROM extensions WHERE id = %s", (id,)) > 0


class ScheduleRepo(_Repo):
    async def upsert(self, id: str, agent: str, cron: str, prompt: str, enabled: bool = True) -> None:
        await self._exec(
            "INSERT INTO schedules (id, agent, cron, prompt, enabled) VALUES (%s,%s,%s,%s,%s)"
            " ON CONFLICT (id) DO UPDATE SET agent = EXCLUDED.agent, cron = EXCLUDED.cron,"
            " prompt = EXCLUDED.prompt, enabled = EXCLUDED.enabled",
            (id, agent, cron, prompt, enabled),
        )

    async def get(self, id: str) -> Row | None:
        return await self._one("SELECT * FROM schedules WHERE id = %s", (id,))

    async def list(self, enabled_only: bool = False) -> list[Row]:
        return await self._all(
            "SELECT * FROM schedules WHERE (NOT %s OR enabled) ORDER BY id", (enabled_only,)
        )

    async def set_enabled(self, id: str, enabled: bool) -> bool:
        return await self._exec("UPDATE schedules SET enabled = %s WHERE id = %s", (enabled, id)) > 0

    async def mark_ran(self, id: str, at: datetime) -> None:
        await self._exec("UPDATE schedules SET last_run_at = %s WHERE id = %s", (at, id))

    async def delete(self, id: str) -> bool:
        return await self._exec("DELETE FROM schedules WHERE id = %s", (id,)) > 0


class FactRepo(_Repo):
    _COLS = "id, scope, scope_id, content, source_id, valid_from, valid_to, superseded_by"

    async def list(
        self,
        scope: str | None = None,
        scope_id: str | None = None,
        include_expired: bool = False,
        limit: int = 500,
    ) -> list[Row]:
        return await self._all(
            f"SELECT {self._COLS} FROM facts WHERE (%s::text IS NULL OR scope = %s)"
            " AND (%s::text IS NULL OR scope_id = %s) AND (%s OR valid_to IS NULL)"
            " ORDER BY valid_from DESC LIMIT %s",
            (scope, scope, scope_id, scope_id, include_expired, limit),
        )

    async def search(self, q: str, limit: int = 50) -> list[Row]:
        from agent0.db.fts import or_tsquery

        query = or_tsquery(q)
        if not query:
            return []
        return await self._all(
            f"SELECT {self._COLS} FROM facts WHERE valid_to IS NULL AND tsv @@ to_tsquery('english', %s)"
            " ORDER BY ts_rank(tsv, to_tsquery('english', %s)) DESC LIMIT %s",
            (query, query, limit),
        )

    async def get(self, fact_id: str) -> Row | None:
        return await self._one(f"SELECT {self._COLS} FROM facts WHERE id = %s", (fact_id,))

    async def history(self, fact_id: str) -> list[Row]:
        return await self._all(
            f"WITH RECURSIVE chain AS (SELECT {self._COLS} FROM facts WHERE id = %s"
            f" UNION SELECT f.id, f.scope, f.scope_id, f.content, f.source_id, f.valid_from, f.valid_to,"
            " f.superseded_by FROM facts f JOIN chain c ON f.superseded_by = c.id)"
            " SELECT * FROM chain ORDER BY valid_from DESC",
            (fact_id,),
        )


class Repos:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool
        self.tasks = TaskRepo(pool)
        self.runs = RunRepo(pool)
        self.task_specs = TaskSpecRepo(pool)
        self.events = EventRepo(pool)
        self.verdicts = VerdictRepo(pool)
        self.approvals = ApprovalRepo(pool)
        self.artifacts = ArtifactRepo(pool)
        self.usage = UsageRepo(pool)
        self.model_profiles = ModelProfileRepo(pool)
        self.extensions = ExtensionRepo(pool)
        self.schedules = ScheduleRepo(pool)
        self.facts = FactRepo(pool)


class PgEventSink:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.pool = pool
        self.events = EventRepo(pool)

    async def emit(self, run_id: str, type: EventType, payload: dict[str, Any] | None = None) -> Event:
        return await self.events.append(run_id, type, payload)

    async def subscribe(self, run_id: str | None = None) -> AsyncIterator[Event]:
        """Live events from every process; a dedicated connection holds LISTEN for the generator's life."""
        conn = await psycopg.AsyncConnection.connect(self.pool.conninfo, autocommit=True)
        try:
            await conn.execute(f"LISTEN {EVENTS_CHANNEL}")
            async for notice in conn.notifies():
                data = json.loads(notice.payload)
                if run_id is not None and data.get("run_id") != run_id:
                    continue
                if data.get("payload") == {"truncated": True}:
                    rows = await self.events.list(data["run_id"], after_seq=data["seq"] - 1, limit=1)
                    if not rows:
                        continue
                    yield rows[0]
                else:
                    yield _event({**data, "type": data["type"]})
        finally:
            await asyncio.shield(conn.close())


class PgUsageSink:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self.usage = UsageRepo(pool)

    async def record(self, usage: UsageRecord) -> None:
        await self.usage.insert(usage)
