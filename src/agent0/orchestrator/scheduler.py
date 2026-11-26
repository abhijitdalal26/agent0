from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from croniter import croniter

from agent0.core.types import Task, utcnow

log = logging.getLogger(__name__)


def next_run(cron: str, after: datetime) -> datetime:
    return croniter(cron, after).get_next(datetime)


class Scheduler:
    """Fires due schedules as tasks. One pass per interval; missed occurrences collapse into one run."""

    def __init__(
        self,
        repos: Any,
        orchestrator: Any,
        agents: Any,
        *,
        interval_s: float = 30.0,
    ) -> None:
        self.repos = repos
        self.orchestrator = orchestrator
        self.agents = agents
        self.interval_s = interval_s
        self._task: asyncio.Task[None] | None = None

    async def tick(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        fired = 0
        for row in await self.repos.schedules.list(enabled_only=True):
            nxt = row.get("next_run_at")
            if nxt is None:
                # Rows predating next_run_at: schedule their next occurrence from now.
                try:
                    await self.repos.schedules.set_next_run(row["id"], next_run(row["cron"], now))
                except Exception:
                    log.warning("schedule %s has an invalid cron %r", row["id"], row["cron"])
                continue
            if nxt > now:
                continue
            if row["agent"] not in self.agents:
                log.warning("schedule %s skipped: unknown agent %r", row["id"], row["agent"])
                continue
            try:
                following = next_run(row["cron"], now)
            except Exception:
                log.warning("schedule %s has an invalid cron %r", row["id"], row["cron"])
                continue
            task = Task(
                title=" ".join(row["prompt"].split())[:80],
                prompt=row["prompt"],
                source="schedule",
                agent=row["agent"],
            )
            try:
                await self.orchestrator.submit(task)
            except Exception:
                log.exception("schedule %s failed to submit", row["id"])
                continue
            await self.repos.schedules.mark_ran(row["id"], now, following)
            fired += 1
        return fired

    async def run(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("scheduler tick failed")
            await asyncio.sleep(self.interval_s)

    def start(self) -> None:
        self._task = asyncio.create_task(self.run(), name="scheduler")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
