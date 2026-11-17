from __future__ import annotations

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from agent0.core.events import EventSink
from agent0.core.types import EventType
from agent0.verify.base import Check, Criterion, TaskSpec, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, head, verdict
from agent0.verify.judge import JudgedCheck, JudgeModelFactory, JudgeRequest, judge_batch, pick_judge
from agent0.verify.registry import CheckRegistry, default_registry

SKIPPED_PREFIX = "skipped"


class VerificationReport(BaseModel):
    verdicts: list[Verdict]
    passed: bool
    cost_usd: float = 0.0
    feedback: str = ""
    skipped: list[str] = Field(default_factory=list)
    awaiting_approval: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def failed(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.status in (VerdictStatus.FAIL, VerdictStatus.ERROR)]


@dataclass
class _Pass:
    run_id: str
    events: EventSink | None
    results: dict[str, Verdict] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)

    async def record(self, result: Verdict, skipped: bool = False) -> None:
        self.results[result.check_id] = result
        if self.events is not None:
            payload = result.model_dump(mode="json") | {"skipped": skipped}
            await self.events.emit(self.run_id, EventType.CHECK_RESULT, payload)

    async def skip(self, criterion: Criterion, blockers: list[str]) -> None:
        self.skipped.append(criterion.id)
        reason = f"{SKIPPED_PREFIX}: runs after {', '.join(blockers)} pass"
        await self.record(verdict(criterion, VerdictStatus.PENDING, reason), skipped=True)

    def blockers(self) -> list[str]:
        return [v.check_id for v in self.results.values() if v.status != VerdictStatus.PASS]


class Verifier:
    """Runs a task's criteria cheapest first: deterministic checks, then one batched judge call, then human.

    A failure in an earlier tier skips the later tiers, so a retry never pays for a judge or pings a human
    about work that is already known to be wrong.
    """

    def __init__(
        self,
        registry: CheckRegistry | None = None,
        judge_factory: JudgeModelFactory | None = None,
        events: EventSink | None = None,
        feedback_chars: int = 3000,
    ) -> None:
        self.registry = registry if registry is not None else default_registry(judge_factory)
        self.judge_factory = judge_factory
        self.events = events
        self.feedback_chars = feedback_chars

    async def verify(
        self, criteria: Sequence[Criterion] | TaskSpec, ctx: VerifyContext
    ) -> VerificationReport:
        criteria = list(criteria.criteria if isinstance(criteria, TaskSpec) else criteria)
        run = _Pass(run_id=ctx.run_id, events=self.events)
        tiers: dict[CheckStage, list[tuple[Criterion, Check | None]]] = {stage: [] for stage in CheckStage}
        for criterion in criteria:
            check = self.registry.get(criterion.type)
            stage = CheckStage(getattr(check, "stage", CheckStage.DETERMINISTIC)) if check else None
            tiers[stage or CheckStage.DETERMINISTIC].append((criterion, check))

        warnings = []
        if criteria and not tiers[CheckStage.DETERMINISTIC]:
            warnings.append("task has no deterministic checks; its result rests on the judge alone")

        for criterion, check in tiers[CheckStage.DETERMINISTIC]:
            if check is None:
                missing = f"no check registered for type {criterion.type!r}"
                await run.record(verdict(criterion, VerdictStatus.ERROR, missing))
            else:
                await run.record(await _safe(criterion, check.run(criterion, ctx)))

        batch: list[tuple[JudgedCheck, JudgeRequest]] = []
        unbatched: list[tuple[Criterion, Check]] = []
        for criterion, check in tiers[CheckStage.JUDGE]:
            assert check is not None
            if not isinstance(check, JudgedCheck):
                unbatched.append((criterion, check))
                continue
            prepared = await _safe(criterion, check.prepare(criterion, ctx))
            if isinstance(prepared, Verdict):
                await run.record(prepared)
            else:
                batch.append((check, prepared))

        if blockers := run.blockers():
            for criterion in [req.criterion for _, req in batch] + [c for c, _ in unbatched]:
                await run.skip(criterion, blockers)
        else:
            await self._judge(run, batch, ctx)
            for criterion, check in unbatched:
                await run.record(await _safe(criterion, check.run(criterion, ctx)))

        blockers = run.blockers()
        for criterion, check in tiers[CheckStage.HUMAN]:
            assert check is not None
            if blockers:
                await run.skip(criterion, blockers)
            else:
                await run.record(await _safe(criterion, check.run(criterion, ctx)))

        verdicts = [run.results[c.id] for c in criteria]
        passed = all(v.status == VerdictStatus.PASS for v in verdicts)
        return VerificationReport(
            verdicts=verdicts,
            passed=passed,
            cost_usd=round(sum(v.cost_usd for v in verdicts), 6),
            feedback="" if passed else self._feedback(verdicts, run.skipped),
            skipped=run.skipped,
            awaiting_approval=[
                v.check_id
                for v in verdicts
                if v.status == VerdictStatus.PENDING and v.check_id not in run.skipped
            ],
            warnings=warnings,
        )

    async def _judge(
        self, run: _Pass, batch: list[tuple[JudgedCheck, JudgeRequest]], ctx: VerifyContext
    ) -> None:
        if not batch:
            return
        requests = [req for _, req in batch]
        try:
            judge = pick_judge(self.judge_factory, ctx.executor_provider)
            outputs, cost = await judge_batch(judge, requests)
        except Exception as exc:
            for req in requests:
                await run.record(
                    verdict(req.criterion, VerdictStatus.ERROR, f"judge failed: {_describe(exc)}")
                )
            return
        share = cost / len(batch)
        for (check, req), output in zip(batch, outputs, strict=True):
            try:
                result = check.finalize(req, output, share)
            except Exception as exc:
                result = verdict(req.criterion, VerdictStatus.ERROR, _describe(exc), cost_usd=share)
            await run.record(result)

    def _feedback(self, verdicts: list[Verdict], skipped: list[str]) -> str:
        lines = ["Verification failed. Fix these, then finish again:"]
        for v in verdicts:
            if v.status in (VerdictStatus.FAIL, VerdictStatus.ERROR):
                label = "failed" if v.status == VerdictStatus.FAIL else "could not run"
                lines.append(f"- {v.check_id} ({v.type}) {label}: {head(v.evidence, 600)}")
        if len(lines) == 1:
            return ""
        if skipped:
            lines.append(f"Not yet checked (they run once the above pass): {', '.join(skipped)}")
        return head("\n".join(lines), self.feedback_chars)


async def _safe[T](criterion: Criterion, call: Awaitable[T]) -> T | Verdict:
    try:
        return await call
    except Exception as exc:
        return verdict(criterion, VerdictStatus.ERROR, _describe(exc))


def _describe(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"
