import asyncio
import json
import os
import uuid

import pytest
from psycopg import AsyncConnection, sql
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from agent0.core.events import verify_chain
from agent0.core.types import EventType, Run, Task
from agent0.db.backfill import backfill_event_hashes
from agent0.db.pool import apply_schema, close_pool, create_pool
from agent0.db.repos import PgEventSink, PgUsageSink, Repos
from agent0.memory.base import Fact, RunSummary
from agent0.memory.pg import PgMemoryStore
from agent0.models.base import UsageRecord

pytestmark = pytest.mark.integration

URL = os.environ.get("AGENT0_DATABASE_URL")


@pytest.fixture
async def pool():
    if not URL:
        pytest.skip("AGENT0_DATABASE_URL not set")
    from agent0.config import Settings

    # A private schema per run keeps integration rows out of the dev database.
    schema = f"agent0_it_{os.getpid()}_{uuid.uuid4().hex[:8]}"
    admin = await create_pool(Settings(database_url=URL))
    try:
        async with admin.connection() as conn:
            await conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        test_pool = AsyncConnectionPool[AsyncConnection[DictRow]](
            URL,
            min_size=1,
            max_size=4,
            open=False,
            # public stays in the path so the vector extension's types resolve.
            kwargs={"row_factory": dict_row, "options": f"-c search_path={schema},public"},
        )
        await test_pool.open(wait=True)
        await apply_schema(test_pool)
        yield test_pool
        await test_pool.close()
    finally:
        async with admin.connection() as conn:
            await conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        await close_pool(admin)


async def test_tasks_runs_events_usage(pool):
    repos = Repos(pool)
    task = await repos.tasks.create(Task(title="t", prompt="p"))
    run = await repos.runs.create(Run(task_id=task.id))
    sink = PgEventSink(pool)
    a = await sink.emit(run.id, EventType.RUN_STARTED)
    b = await sink.emit(run.id, EventType.TOOL_CALL, {"tool": "shell"})
    assert (a.seq, b.seq) == (1, 2)
    assert [e.seq for e in await repos.events.list(run.id, after_seq=1)] == [2]
    await PgUsageSink(pool).record(
        UsageRecord(run_id=run.id, profile="p", provider="groq", model="m", capability="chat", cost_usd=0.5)
    )
    rows = await repos.usage.summary(group_by=("provider", "agent"))
    assert any(r["provider"] == "groq" and r["agent"] == run.agent for r in rows)


async def test_event_sink_streams_live(pool):
    sink = PgEventSink(pool)
    stream = sink.subscribe("live-run")
    first = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.3)
    await sink.emit("live-run", EventType.RUN_STARTED)
    event = await asyncio.wait_for(first, 5)
    assert event.run_id == "live-run"
    await stream.aclose()


async def test_backfill_chains_legacy_events(pool):
    repos = Repos(pool)
    run = await repos.runs.create(Run(task_id=(await repos.tasks.create(Task(title="t", prompt="p"))).id))
    # Simulate pre-chain rows: insert directly so hash stays NULL.
    async with pool.connection() as conn:
        for seq, payload in enumerate(({"a": 1}, {"b": 2}), start=1):
            await conn.execute(
                "INSERT INTO events (id, run_id, seq, type, payload) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (f"legacy-{seq}", run.id, seq, "run.started", json.dumps(payload)),
            )
    result = await backfill_event_hashes(pool)
    assert result == {"runs": 1, "events": 2}
    events = await repos.events.list(run.id)
    assert verify_chain(events) == (True, None)
    assert await backfill_event_hashes(pool) == {"runs": 0, "events": 0}


async def test_memory_versioning(pool):
    store = PgMemoryStore(pool)
    old = Fact(content="integration zebra prefers csv exports")
    await store.apply(old, "new")
    new = Fact(content="integration zebra prefers parquet exports")
    await store.apply(new, "changes", old.id)
    await store.save_run(RunSummary(run_id=f"r-{old.id}", summary="zebra export run", outcome="ok"))
    recall = await store.recall("zebra exports")
    ids = [f.id for f in recall.facts]
    assert new.id in ids and old.id not in ids
    assert recall.past_runs
