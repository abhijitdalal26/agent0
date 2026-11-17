from __future__ import annotations

from pydantic import BaseModel, Field

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, ConfigError, head, require, verdict
from agent0.verify.judge import JudgeModelFactory, JudgeRequest, run_judged, untrusted


class RubricVerdict(BaseModel):
    score: int = Field(ge=1, le=5, description="1 = fails the rubric badly, 5 = fully meets it")
    reasons: list[str] = Field(description="Short, specific reasons; name what to fix when score is low")


class LlmJudgeCheck:
    """Grades the output (or `config.path`) against `config.rubric`; passes at `config.threshold` (4)."""

    type = CheckType.LLM_JUDGE
    stage = CheckStage.JUDGE

    def __init__(
        self, judge_factory: JudgeModelFactory | None = None, max_subject_chars: int = 12_000
    ) -> None:
        self.judge_factory = judge_factory
        self.max_subject_chars = max_subject_chars

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        return await run_judged(self, self.judge_factory, criterion, ctx)

    async def prepare(self, criterion: Criterion, ctx: VerifyContext) -> Verdict | JudgeRequest:
        rubric = require(criterion, "rubric")
        rubric_text = "\n".join(f"- {r}" for r in rubric) if isinstance(rubric, list) else str(rubric)
        if path := criterion.config.get("path"):
            if ctx.sandbox is None:
                raise ConfigError("llm_judge with a path needs a sandbox")
            try:
                subject = (await ctx.sandbox.read_file(path)).decode("utf-8", errors="replace")
            except Exception as exc:
                return verdict(criterion, VerdictStatus.FAIL, f"{path} not found or unreadable: {exc}")
        else:
            subject = ctx.output
        prompt = (
            f"Score the work from 1 to 5 against this rubric.\nRubric:\n{rubric_text}\n\n"
            f"Task the work was made for:\n{untrusted(head(ctx.task_prompt, 2000))}\n\n"
            f"Work to grade:\n{untrusted(head(subject, self.max_subject_chars))}"
        )
        return JudgeRequest(criterion=criterion, prompt=prompt, output_type=RubricVerdict)

    def finalize(self, request: JudgeRequest, result: BaseModel, cost_usd: float) -> Verdict:
        assert isinstance(result, RubricVerdict)
        threshold = float(request.criterion.config.get("threshold", 4))
        status = VerdictStatus.PASS if result.score >= threshold else VerdictStatus.FAIL
        evidence = f"score {result.score}/5 (threshold {threshold:g}): " + "; ".join(result.reasons)
        return verdict(request.criterion, status, evidence, score=float(result.score), cost_usd=cost_usd)
