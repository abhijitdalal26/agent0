from datetime import UTC, datetime, timedelta

from agent0.agents.definitions import AgentCatalog, AgentDef
from agent0.orchestrator.scheduler import Scheduler, next_run

UTC = UTC


class _Schedules:
    def __init__(self, rows):
        self.rows = {r["id"]: dict(r) for r in rows}
        self.next_sets = []

    async def list(self, enabled_only=False):
        return [r for r in self.rows.values() if not enabled_only or r["enabled"]]

    async def set_next_run(self, id, at):
        self.next_sets.append((id, at))
        self.rows[id]["next_run_at"] = at

    async def mark_ran(self, id, at, next_run_at=None):
        self.rows[id]["last_run_at"] = at
        self.rows[id]["next_run_at"] = next_run_at


class _Orchestrator:
    def __init__(self):
        self.submitted = []

    async def submit(self, task):
        self.submitted.append(task)
        return task


class _Repos:
    def __init__(self, rows):
        self.schedules = _Schedules(rows)


def _agents():
    return AgentCatalog({"executor": AgentDef(name="executor", instructions="do it")})


def _row(id="s1", cron="*/5 * * * *", agent="executor", enabled=True, next_run_at=None, **kw):
    return {
        "id": id,
        "agent": agent,
        "cron": cron,
        "prompt": "check the thing",
        "enabled": enabled,
        "last_run_at": None,
        "next_run_at": next_run_at,
        **kw,
    }


def test_next_run_advances_by_cron():
    after = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert next_run("*/5 * * * *", after) == datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    assert next_run("0 9 * * 1", after).weekday() == 0


async def test_tick_fires_due_schedule():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    due = _row(next_run_at=now - timedelta(seconds=1))
    future = _row(id="s2", next_run_at=now + timedelta(hours=1))
    repos = _Repos([due, future])
    orch = _Orchestrator()
    sched = Scheduler(repos, orch, _agents())

    assert await sched.tick(now) == 1
    assert len(orch.submitted) == 1
    task = orch.submitted[0]
    assert task.agent == "executor" and task.source == "schedule"
    assert task.prompt == "check the thing"
    row = repos.schedules.rows["s1"]
    assert row["last_run_at"] == now
    assert row["next_run_at"] > now


async def test_tick_skips_disabled_unknown_and_bad_cron():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    past = now - timedelta(seconds=1)
    rows = [
        _row(id="off", enabled=False, next_run_at=past),
        _row(id="ghost", agent="nope", next_run_at=past),
        _row(id="bad", cron="not a cron", next_run_at=past),
    ]
    repos = _Repos(rows)
    orch = _Orchestrator()
    sched = Scheduler(repos, orch, _agents())

    assert await sched.tick(now) == 0
    assert orch.submitted == []


async def test_tick_backfills_missing_next_run():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    repos = _Repos([_row(next_run_at=None)])
    orch = _Orchestrator()
    sched = Scheduler(repos, orch, _agents())

    assert await sched.tick(now) == 0
    assert orch.submitted == []
    assert repos.schedules.next_sets and repos.schedules.next_sets[0][1] > now
