from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from agent0.core.types import RunStatus, Task
from agent0.orchestrator.steps import AttemptResult, Report, approval_question, human_question
from agent0.verify import TaskSpec, Verdict, VerdictStatus
from agent0.verify.base import CheckType


class Decision(BaseModel):
    approved: bool
    by: str = ""
    note: str | None = None


class Outcome(BaseModel):
    status: RunStatus
    attempts: int
    output: str = ""
    report: Report | None = None
    cost_usd: float = 0.0
    artifacts: list[str] = []


class Steps(Protocol):
    async def status(self, status: RunStatus, step: str | None = None) -> None: ...
    async def plan(self) -> TaskSpec: ...
    async def execute(
        self, spec: TaskSpec, attempt: int, feedback: str | None, approved: list[str]
    ) -> AttemptResult: ...
    async def verify(self, spec: TaskSpec, result: AttemptResult) -> Report: ...
    async def ask(self, question: str) -> Decision: ...
    async def milestone(self, text: str) -> None: ...
    async def finish(self, outcome: Outcome, result: AttemptResult | None) -> None: ...


def _approve_humans(report: Report, decision: Decision) -> Report:
    status = VerdictStatus.PASS if decision.approved else VerdictStatus.FAIL
    note = f"{'approved' if decision.approved else 'rejected'} by {decision.by or 'reviewer'}"
    if decision.note:
        note += f": {decision.note}"
    verdicts = [
        Verdict(**{**v.model_dump(), "status": status, "evidence": note}) if v.type == CheckType.HUMAN else v
        for v in report.verdicts
    ]
    passed = all(v.status == VerdictStatus.PASS for v in verdicts)
    feedback = (
        report.feedback if passed or decision.approved else f"Human reviewer rejected the result. {note}"
    )
    return report.model_copy(update={"verdicts": verdicts, "passed": passed, "feedback": feedback})


async def drive(task: Task, steps: Steps) -> Outcome:
    """Plan once, then execute, verify and retry with feedback. Shared by the local and Temporal runners."""
    await steps.status(RunStatus.PLANNING, "planning")
    spec = await steps.plan()
    await steps.milestone(f"Plan: {spec.goal} ({len(spec.criteria)} checks)")

    feedback: str | None = None
    approved: list[str] = []
    total_cost = 0.0
    result: AttemptResult | None = None
    report: Report | None = None
    max_attempts = task.budget.max_retries + 1

    for attempt in range(1, max_attempts + 1):
        await steps.status(RunStatus.EXECUTING, f"attempt {attempt}/{max_attempts}")
        while True:
            result = await steps.execute(spec, attempt, feedback, approved)
            total_cost += result.cost_usd
            if result.status != "needs_approval" or result.approval is None:
                break
            await steps.status(RunStatus.WAITING_APPROVAL, f"approve {result.approval.tool}?")
            decision = await steps.ask(approval_question(result.approval))
            await steps.status(RunStatus.EXECUTING, f"attempt {attempt}/{max_attempts}")
            if decision.approved:
                approved.append(result.approval.key)
            else:
                feedback = (
                    f"The user rejected `{result.approval.tool}` ({decision.note or 'no reason given'}). "
                    "Do not attempt it again; finish the task another way or explain why you cannot."
                )

        if result.status == "budget":
            outcome = Outcome(status=RunStatus.STOPPED, attempts=attempt, cost_usd=total_cost)
            await steps.finish(outcome, result)
            return outcome
        if result.status == "error":
            outcome = Outcome(status=RunStatus.FAILED, attempts=attempt, cost_usd=total_cost)
            await steps.finish(outcome, result)
            return outcome

        await steps.status(RunStatus.VERIFYING, f"checking attempt {attempt}")
        report = await steps.verify(spec, result)
        total_cost += report.cost_usd

        if report.awaiting_approval and not any(
            v.status in (VerdictStatus.FAIL, VerdictStatus.ERROR) for v in report.verdicts
        ):
            await steps.status(RunStatus.WAITING_APPROVAL, "waiting for your review")
            report = _approve_humans(report, await steps.ask(human_question(task, result, report)))

        if report.passed:
            outcome = Outcome(
                status=RunStatus.SUCCEEDED,
                attempts=attempt,
                output=result.output,
                report=report,
                cost_usd=total_cost,
                artifacts=result.artifacts,
            )
            await steps.finish(outcome, result)
            return outcome

        feedback = report.feedback
        failed = [v.check_id for v in report.verdicts if v.status != VerdictStatus.PASS]
        await steps.milestone(
            f"Attempt {attempt} failed checks {', '.join(failed)}; retrying"
            if attempt < max_attempts
            else f"Attempt {attempt} failed checks {', '.join(failed)}"
        )

    outcome = Outcome(
        status=RunStatus.FAILED,
        attempts=max_attempts,
        output=result.output if result else "",
        report=report,
        cost_usd=total_cost,
        artifacts=result.artifacts if result else [],
    )
    await steps.finish(outcome, result)
    return outcome
