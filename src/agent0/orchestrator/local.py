from __future__ import annotations

import asyncio
import logging

from agent0.channels.formatting import CheckLine, render_verdict_table
from agent0.core.types import EventType, RunStatus, Task
from agent0.orchestrator.loop import Decision, Outcome, drive
from agent0.orchestrator.runtime import Runtime
from agent0.orchestrator.steps import AttemptResult, Engine, Report
from agent0.verify import TaskSpec

log = logging.getLogger(__name__)


def final_message(task: Task, run_id: str, outcome: Outcome) -> str:
    lines = [
        f"{task.title}: {outcome.status.value.upper()} after {outcome.attempts} attempt(s),"
        f" ${outcome.cost_usd:.4f}",
        f"run {run_id}",
    ]
    if outcome.report:
        rows = [
            CheckLine(check_id=v.check_id, status=v.status.value, evidence=v.evidence)
            for v in outcome.report.verdicts
        ]
        lines.append(render_verdict_table(rows))
    if outcome.output:
        lines.append(outcome.output[:1500])
    return "\n\n".join(lines)


class EngineSteps:
    def __init__(
        self, engine: Engine, task: Task, run_id: str, approvals: dict[str, asyncio.Future[Decision]]
    ):
        self.engine, self.task, self.run_id, self.approvals = engine, task, run_id, approvals

    async def status(self, status: RunStatus, step: str | None = None) -> None:
        await self.engine.set_status(self.task, self.run_id, status, step)

    async def plan(self) -> TaskSpec:
        return await self.engine.plan(self.task, self.run_id)

    async def execute(
        self, spec: TaskSpec, attempt: int, feedback: str | None, approved: list[str]
    ) -> AttemptResult:
        return await self.engine.execute(self.task, spec, self.run_id, attempt, feedback, approved)

    async def verify(self, spec: TaskSpec, result: AttemptResult) -> Report:
        return await self.engine.verify(self.task, spec, self.run_id, result)

    async def ask(self, question: str) -> Decision:
        approval_id = await self.engine.create_approval(self.task, self.run_id, question)
        future: asyncio.Future[Decision] = asyncio.get_running_loop().create_future()
        self.approvals[approval_id] = future
        try:
            decision = await future
        finally:
            self.approvals.pop(approval_id, None)
        await self.engine.record_decision(
            self.run_id, approval_id, "approve" if decision.approved else "reject", decision.by
        )
        return decision

    async def milestone(self, text: str) -> None:
        if self.task.notify_level != "final_only":
            await self.engine.notify(self.task, text)

    async def finish(self, outcome: Outcome, result: AttemptResult | None) -> None:
        await self.engine.finish(
            self.task, self.run_id, outcome.status, result, outcome.report, outcome.attempts
        )
        await self.engine.notify(
            self.task, final_message(self.task, self.run_id, outcome), self._files(outcome)
        )

    def _files(self, outcome: Outcome) -> list[str]:
        root = self.engine.rt.settings.workspace_root / self.run_id
        return [str(root / p) for p in outcome.artifacts if (root / p).is_file()]


class LocalOrchestrator:
    """Runs tasks as asyncio tasks in this process. No Temporal needed; runs don't survive a restart."""

    def __init__(self, rt: Runtime) -> None:
        self.rt = rt
        self.engine = Engine(rt)
        self.approvals: dict[str, asyncio.Future[Decision]] = {}
        self.running: dict[str, asyncio.Task[Outcome]] = {}
        self.tasks: dict[str, Task] = {}
        self.run_tasks: dict[str, Task] = {}

    async def _create_run(self, task: Task):
        from agent0.core.types import Run

        run = Run(task_id=task.id, agent=task.agent)
        if self.rt.repos:
            if await self.rt.repos.tasks.get(task.id) is None:
                await self.rt.repos.tasks.create(task)
            await self.rt.repos.runs.create(run)
        return run

    async def submit(self, task: Task):
        run = await self._create_run(task)
        self.tasks[task.id] = task
        self.run_tasks[run.id] = task
        steps = EngineSteps(self.engine, task, run.id, self.approvals)
        self.running[run.id] = asyncio.create_task(self._guarded(task, run.id, steps), name=f"run-{run.id}")
        return run

    async def _guarded(self, task: Task, run_id: str, steps: EngineSteps) -> Outcome:
        # drive() records its own outcomes; this catches what escapes it (e.g. planning) so no run is stuck.
        try:
            return await drive(task, steps)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("run %s crashed", run_id)
            message = f"{type(exc).__name__}: {exc}"[:500]
            await self.rt.events.emit(run_id, EventType.ERROR, {"message": message})
            await self.engine.set_status(task, run_id, RunStatus.FAILED, "error")
            return Outcome(status=RunStatus.FAILED, attempts=0, cost_usd=0.0)

    async def run_to_end(self, task: Task) -> tuple[str, Outcome]:
        run = await self.submit(task)
        return run.id, await self.running[run.id]

    async def stop(self, run_id: str) -> None:
        job = self.running.get(run_id)
        if job and not job.done():
            job.cancel()
        task = self.run_tasks.get(run_id)
        if task is None and self.rt.repos and (run := await self.rt.repos.runs.get(run_id)):
            # Left over from before a restart: nothing is running it, so just record the stop.
            task = await self.rt.repos.tasks.get(run.task_id)
        if task is not None:
            await self.engine.set_status(task, run_id, RunStatus.STOPPED, "stopped by user")

    async def retry(self, task_id: str):
        task = self.tasks.get(task_id)
        if task is None and self.rt.repos:
            task = await self.rt.repos.tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return await self.submit(task)

    async def decide_approval(
        self, approval_id: str, decision: str, by: str, note: str | None = None
    ) -> None:
        if self.rt.repos:
            await self.rt.repos.approvals.decide(
                approval_id, "approved" if decision == "approve" else "rejected", by, note
            )
        future = self.approvals.get(approval_id)
        if future and not future.done():
            future.set_result(Decision(approved=decision == "approve", by=by, note=note))
