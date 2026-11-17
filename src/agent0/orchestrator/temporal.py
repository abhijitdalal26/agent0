from __future__ import annotations

import asyncio
from datetime import timedelta

from pydantic import BaseModel
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from agent0.core.types import Run, RunStatus, Task
    from agent0.orchestrator.local import final_message
    from agent0.orchestrator.loop import Decision, Outcome, drive
    from agent0.orchestrator.steps import AttemptResult, Engine, Report
    from agent0.verify import TaskSpec


class RunInput(BaseModel):
    task: Task
    run_id: str


class StatusIn(BaseModel):
    task: Task
    run_id: str
    status: RunStatus
    step: str | None = None


class ExecuteIn(BaseModel):
    task: Task
    run_id: str
    spec: TaskSpec
    attempt: int
    feedback: str | None = None
    approved: list[str] = []


class VerifyIn(BaseModel):
    task: Task
    run_id: str
    spec: TaskSpec
    result: AttemptResult


class AskIn(BaseModel):
    task: Task
    run_id: str
    question: str


class DecisionIn(BaseModel):
    run_id: str
    approval_id: str
    decision: Decision


class NotifyIn(BaseModel):
    task: Task
    text: str
    attachments: list[str] = []


class FinishIn(BaseModel):
    task: Task
    run_id: str
    outcome: Outcome
    result: AttemptResult | None = None


class Activities:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @activity.defn(name="set_status")
    async def set_status(self, a: StatusIn) -> None:
        await self.engine.set_status(a.task, a.run_id, a.status, a.step)

    @activity.defn(name="plan")
    async def plan(self, a: RunInput) -> TaskSpec:
        return await self.engine.plan(a.task, a.run_id)

    @activity.defn(name="execute")
    async def execute(self, a: ExecuteIn) -> AttemptResult:
        return await self.engine.execute(a.task, a.spec, a.run_id, a.attempt, a.feedback, a.approved)

    @activity.defn(name="verify")
    async def verify(self, a: VerifyIn) -> Report:
        return await self.engine.verify(a.task, a.spec, a.run_id, a.result)

    @activity.defn(name="create_approval")
    async def create_approval(self, a: AskIn) -> str:
        return await self.engine.create_approval(a.task, a.run_id, a.question)

    @activity.defn(name="record_decision")
    async def record_decision(self, a: DecisionIn) -> None:
        d = a.decision
        await self.engine.record_decision(
            a.run_id, a.approval_id, "approve" if d.approved else "reject", d.by
        )

    @activity.defn(name="notify")
    async def notify(self, a: NotifyIn) -> None:
        await self.engine.notify(a.task, a.text, a.attachments)

    @activity.defn(name="finish")
    async def finish(self, a: FinishIn) -> None:
        o = a.outcome
        await self.engine.finish(a.task, a.run_id, o.status, a.result, o.report, o.attempts)
        root = self.engine.rt.settings.workspace_root / a.run_id
        files = [str(root / p) for p in o.artifacts if (root / p).is_file()]
        await self.engine.notify(a.task, final_message(a.task, a.run_id, o), files)

    def all(self) -> list:
        return [
            self.set_status,
            self.plan,
            self.execute,
            self.verify,
            self.create_approval,
            self.record_decision,
            self.notify,
            self.finish,
        ]


_SHORT = dict(start_to_close_timeout=timedelta(minutes=2), retry_policy=RetryPolicy(maximum_attempts=3))
_MODEL = dict(start_to_close_timeout=timedelta(minutes=10), retry_policy=RetryPolicy(maximum_attempts=3))


@workflow.defn(name="RunWorkflow")
class RunWorkflow:
    def __init__(self) -> None:
        self.decisions: dict[str, Decision] = {}
        self.inp: RunInput | None = None

    @workflow.signal
    def decide(self, approval_id: str, decision: Decision) -> None:
        self.decisions[approval_id] = decision

    @workflow.run
    async def run(self, inp: RunInput) -> Outcome:
        self.inp = inp
        try:
            return await drive(inp.task, _WorkflowSteps(self))
        except asyncio.CancelledError:
            await workflow.execute_activity(
                "set_status", StatusIn(task=inp.task, run_id=inp.run_id, status=RunStatus.STOPPED), **_SHORT
            )
            raise


class _WorkflowSteps:
    def __init__(self, wf: RunWorkflow) -> None:
        self.wf = wf
        assert wf.inp is not None
        self.task, self.run_id = wf.inp.task, wf.inp.run_id

    async def status(self, status: RunStatus, step: str | None = None) -> None:
        await workflow.execute_activity(
            "set_status", StatusIn(task=self.task, run_id=self.run_id, status=status, step=step), **_SHORT
        )

    async def plan(self) -> TaskSpec:
        return await workflow.execute_activity(
            "plan", RunInput(task=self.task, run_id=self.run_id), result_type=TaskSpec, **_MODEL
        )

    async def execute(
        self, spec: TaskSpec, attempt: int, feedback: str | None, approved: list[str]
    ) -> AttemptResult:
        # One attempt is not idempotent (it spends tokens and writes files), so Temporal never re-runs it;
        # drive() owns retries with verifier feedback instead.
        return await workflow.execute_activity(
            "execute",
            ExecuteIn(
                task=self.task,
                run_id=self.run_id,
                spec=spec,
                attempt=attempt,
                feedback=feedback,
                approved=approved,
            ),
            result_type=AttemptResult,
            start_to_close_timeout=timedelta(minutes=self.task.budget.max_minutes + 5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

    async def verify(self, spec: TaskSpec, result: AttemptResult) -> Report:
        return await workflow.execute_activity(
            "verify",
            VerifyIn(task=self.task, run_id=self.run_id, spec=spec, result=result),
            result_type=Report,
            **_MODEL,
        )

    async def ask(self, question: str) -> Decision:
        approval_id = await workflow.execute_activity(
            "create_approval",
            AskIn(task=self.task, run_id=self.run_id, question=question),
            result_type=str,
            **_SHORT,
        )
        await workflow.wait_condition(lambda: approval_id in self.wf.decisions)
        decision = self.wf.decisions[approval_id]
        await workflow.execute_activity(
            "record_decision",
            DecisionIn(run_id=self.run_id, approval_id=approval_id, decision=decision),
            **_SHORT,
        )
        return decision

    async def milestone(self, text: str) -> None:
        if self.task.notify_level != "final_only":
            await workflow.execute_activity("notify", NotifyIn(task=self.task, text=text), **_SHORT)

    async def finish(self, outcome: Outcome, result: AttemptResult | None) -> None:
        await workflow.execute_activity(
            "finish", FinishIn(task=self.task, run_id=self.run_id, outcome=outcome, result=result), **_SHORT
        )


def workflow_id(run_id: str) -> str:
    return f"agent0-run-{run_id}"


async def connect(settings):
    from temporalio.client import Client
    from temporalio.contrib.pydantic import pydantic_data_converter

    return await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )


class TemporalOrchestrator:
    """Durable runs: survives API/worker restarts. Requires a Temporal server and `agent0 worker`."""

    def __init__(self, rt, client) -> None:
        self.rt, self.client = rt, client

    async def submit(self, task: Task) -> Run:
        run = Run(task_id=task.id, agent=task.agent)
        if self.rt.repos:
            if await self.rt.repos.tasks.get(task.id) is None:
                await self.rt.repos.tasks.create(task)
            await self.rt.repos.runs.create(run, temporal_workflow_id=workflow_id(run.id))
        await self.client.start_workflow(
            RunWorkflow.run,
            RunInput(task=task, run_id=run.id),
            id=workflow_id(run.id),
            task_queue=self.rt.settings.task_queue,
        )
        return run

    async def stop(self, run_id: str) -> None:
        await self.client.get_workflow_handle(workflow_id(run_id)).cancel()

    async def retry(self, task_id: str) -> Run:
        task = await self.rt.repos.tasks.get(task_id) if self.rt.repos else None
        if task is None:
            raise KeyError(task_id)
        return await self.submit(task)

    async def decide_approval(
        self, approval_id: str, decision: str, by: str, note: str | None = None
    ) -> None:
        row = await self.rt.repos.approvals.decide(
            approval_id, "approved" if decision == "approve" else "rejected", by, note
        )
        if row is None:
            return
        handle = self.client.get_workflow_handle(workflow_id(row["run_id"]))
        await handle.signal(
            RunWorkflow.decide, args=[approval_id, Decision(approved=decision == "approve", by=by, note=note)]
        )


async def run_worker(rt, client) -> None:
    from temporalio.worker import Worker

    acts = Activities(Engine(rt))
    worker = Worker(client, task_queue=rt.settings.task_queue, workflows=[RunWorkflow], activities=acts.all())
    await worker.run()
