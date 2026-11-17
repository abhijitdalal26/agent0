from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from agent0.db.fts import or_tsquery, vector_literal
from agent0.db.pool import PgPool
from agent0.memory.base import Fact, FactVerdict, Recall, RunSummary
from agent0.memory.fusion import rrf, take_within_budget

EmbedFn = Callable[[str], Awaitable[list[float]]]

_FACT_COLS = "id, scope, scope_id, content, source_id, valid_from, valid_to, superseded_by"
_SCOPE = "(scope = 'global' OR (scope = %(scope)s AND scope_id IS NOT DISTINCT FROM %(scope_id)s))"


class PgMemoryStore:
    def __init__(
        self,
        pool: PgPool,
        embed: EmbedFn | None = None,
        max_chars: int = 2000,
        max_facts: int = 8,
        max_runs: int = 3,
        candidates: int = 20,
    ) -> None:
        self.pool = pool
        self.embed = embed
        self.max_chars = max_chars
        self.max_facts = max_facts
        self.max_runs = max_runs
        self.candidates = candidates

    async def _query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        async with self.pool.connection() as conn:
            cur = await conn.execute(sql, params)  # type: ignore[arg-type]
            return await cur.fetchall()

    async def _ranked_facts(self, query: str, scope: str, scope_id: str | None, limit: int) -> list[Fact]:
        base = {"scope": scope, "scope_id": scope_id, "limit": limit}
        rankings: list[list[str]] = []
        by_id: dict[str, Fact] = {}
        tsq = or_tsquery(query)
        if tsq:
            rows = await self._query(
                f"SELECT {_FACT_COLS} FROM facts WHERE valid_to IS NULL AND {_SCOPE}"
                " AND tsv @@ to_tsquery('english', %(q)s)"
                " ORDER BY ts_rank_cd(tsv, to_tsquery('english', %(q)s)) DESC,"
                " valid_from DESC LIMIT %(limit)s",
                {**base, "q": tsq},
            )
            rankings.append([r["id"] for r in rows])
            by_id.update({r["id"]: Fact.model_validate(r) for r in rows})
        if self.embed is not None:
            vec = vector_literal(await self.embed(query))
            rows = await self._query(
                f"SELECT {_FACT_COLS} FROM facts WHERE valid_to IS NULL AND {_SCOPE}"
                " AND embedding IS NOT NULL"
                " ORDER BY embedding <=> %(vec)s::vector LIMIT %(limit)s",
                {**base, "vec": vec},
            )
            rankings.append([r["id"] for r in rows])
            by_id.update({r["id"]: Fact.model_validate(r) for r in rows})
        return [by_id[i] for i, _ in rrf(rankings)]

    async def _ranked_runs(self, query: str, limit: int) -> list[RunSummary]:
        rankings: list[list[str]] = []
        by_id: dict[str, RunSummary] = {}
        tsq = or_tsquery(query)
        if tsq:
            rows = await self._query(
                "SELECT run_id, summary, outcome FROM run_summaries WHERE tsv @@ to_tsquery('english', %(q)s)"
                " ORDER BY ts_rank_cd(tsv, to_tsquery('english', %(q)s)) DESC,"
                " created_at DESC LIMIT %(limit)s",
                {"q": tsq, "limit": limit},
            )
            rankings.append([r["run_id"] for r in rows])
            by_id.update({r["run_id"]: RunSummary.model_validate(r) for r in rows})
        if self.embed is not None:
            vec = vector_literal(await self.embed(query))
            rows = await self._query(
                "SELECT run_id, summary, outcome FROM run_summaries WHERE embedding IS NOT NULL"
                " ORDER BY embedding <=> %(vec)s::vector LIMIT %(limit)s",
                {"vec": vec, "limit": limit},
            )
            rankings.append([r["run_id"] for r in rows])
            by_id.update({r["run_id"]: RunSummary.model_validate(r) for r in rows})
        return [by_id[i] for i, _ in rrf(rankings)]

    async def recall(self, query: str, scope: str = "global", scope_id: str | None = None) -> Recall:
        facts = (await self._ranked_facts(query, scope, scope_id, self.candidates))[: self.max_facts]
        runs = (await self._ranked_runs(query, self.candidates))[: self.max_runs]
        facts = take_within_budget(facts, lambda f: f.content, self.max_chars)
        used = sum(len(f.content) + 3 for f in facts)
        runs = take_within_budget(runs, lambda r: r.summary, max(self.max_chars - used, 0))
        return Recall(facts=facts, past_runs=runs)

    async def save_run(self, summary: RunSummary) -> None:
        vec = vector_literal(await self.embed(summary.summary)) if self.embed else None
        async with self.pool.connection() as conn:
            await conn.execute(
                "INSERT INTO run_summaries (run_id, summary, outcome, embedding)"
                " VALUES (%s, %s, %s, %s::vector)"
                " ON CONFLICT (run_id) DO UPDATE SET summary = EXCLUDED.summary, outcome = EXCLUDED.outcome,"
                " embedding = EXCLUDED.embedding",
                (summary.run_id, summary.summary, summary.outcome, vec),
            )

    async def apply(self, fact: Fact, verdict: FactVerdict, target_id: str | None = None) -> None:
        if verdict == "repeats":
            return
        if verdict != "new" and target_id is None:
            raise ValueError(f"verdict {verdict!r} needs a target_id")
        vec = None
        if verdict in ("new", "changes") and self.embed:
            vec = vector_literal(await self.embed(fact.content))
        async with self.pool.connection() as conn, conn.transaction():
            if verdict in ("changes", "ends"):
                superseded_by = fact.id if verdict == "changes" else None
                await conn.execute(
                    "UPDATE facts SET valid_to = now(), superseded_by = %s"
                    " WHERE id = %s AND valid_to IS NULL",
                    (superseded_by, target_id),
                )
            if verdict in ("new", "changes"):
                await conn.execute(
                    "INSERT INTO facts (id, scope, scope_id, content, source_id, valid_from, valid_to,"
                    " superseded_by, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)"
                    " ON CONFLICT (id) DO NOTHING",
                    (
                        fact.id,
                        fact.scope,
                        fact.scope_id,
                        fact.content,
                        fact.source_id,
                        fact.valid_from,
                        fact.valid_to,
                        fact.superseded_by,
                        vec,
                    ),
                )

    async def similar_facts(self, content: str, limit: int = 5) -> list[Fact]:
        rankings: list[list[str]] = []
        by_id: dict[str, Fact] = {}
        tsq = or_tsquery(content)
        if tsq:
            rows = await self._query(
                f"SELECT {_FACT_COLS} FROM facts WHERE valid_to IS NULL"
                " AND tsv @@ to_tsquery('english', %(q)s)"
                " ORDER BY ts_rank_cd(tsv, to_tsquery('english', %(q)s)) DESC LIMIT %(limit)s",
                {"q": tsq, "limit": limit},
            )
            rankings.append([r["id"] for r in rows])
            by_id.update({r["id"]: Fact.model_validate(r) for r in rows})
        if self.embed is not None:
            rows = await self._query(
                f"SELECT {_FACT_COLS} FROM facts WHERE valid_to IS NULL AND embedding IS NOT NULL"
                " ORDER BY embedding <=> %(vec)s::vector LIMIT %(limit)s",
                {"vec": vector_literal(await self.embed(content)), "limit": limit},
            )
            rankings.append([r["id"] for r in rows])
            by_id.update({r["id"]: Fact.model_validate(r) for r in rows})
        return [by_id[i] for i, _ in rrf(rankings)][:limit]
