import asyncio
import os

import pytest

from agent0.core.types import EventType, Run, Task
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

    pool = await create_pool(Settings(database_url=URL))
    await apply_schema(pool)
    await apply_schema(pool)
    yield pool
    await close_pool(pool)


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
