import pytest

from agent0.core.events import MemoryEventSink
from agent0.core.types import EventType
from agent0.knowledge.base import SourceRecord
from agent0.sandbox.base import ExecResult
from agent0.verify import (
    CheckRegistry,
    CheckType,
    Criterion,
    TaskSpec,
    VerdictStatus,
    Verifier,
    default_registry,
)
from agent0.verify.checks import CheckStage

SOURCES = [SourceRecord(source_id="s1", source="db", content="revenue=1200 month=2026-10")]
ANSWER = "Revenue was 1,200 in 2026-10 [src:s1]."

CRITERIA = [
    Criterion(id="tests", description="tests pass", type=CheckType.COMMAND, config={"cmd": "pytest"}),
    Criterion(
        id="ad",
        description="no banned claims",
        type=CheckType.ARTIFACT,
        config={"forbidden_patterns": ["guaranteed"]},
    ),
    Criterion(id="facts", description="facts come from the data", type=CheckType.GROUNDED),
    Criterion(id="voice", description="brand voice", type=CheckType.LLM_JUDGE, config={"rubric": "Friendly"}),
    Criterion(id="approve", description="Approve before publishing", type=CheckType.HUMAN),
]


def ok_box(sandbox, exit_code=0):
    return sandbox(commands={"pytest": ExecResult(exit_code=exit_code, stdout="", stderr="1 failed: test_x")})


def batch_answer(prompt, sections):
    assert sections == ["s0", "s1"]
    return {
        "s0": {"claims": [{"claim": 1, "label": "supported"}]},
        "s1": {"score": 5, "reasons": ["friendly"]},
    }


async def test_all_pass_with_one_batched_judge_call(ctx_factory, sandbox, judge):
    spy = judge(batch_answer, cost_per_call=0.004)
    events = MemoryEventSink()
    verifier = Verifier(judge_factory=spy.factory, events=events)
    ctx = ctx_factory(ANSWER, sandbox=ok_box(sandbox), sources=SOURCES, executor_provider="groq")

    report = await verifier.verify(CRITERIA[:4], ctx)

    assert report.passed, report.feedback
    assert spy.calls == 1
    assert spy.excluded == ["groq"]
    assert report.cost_usd == pytest.approx(0.004)
    assert [v.cost_usd for v in report.verdicts] == [0, 0, 0.002, 0.002]
    assert report.feedback == ""
    assert [e.type for e in events.events] == [EventType.CHECK_RESULT] * 4
    assert {e.payload["check_id"] for e in events.events} == {"tests", "ad", "facts", "voice"}


async def test_deterministic_failure_skips_paid_and_human(ctx_factory, sandbox, no_judge):
    events = MemoryEventSink()
    verifier = Verifier(judge_factory=no_judge, events=events)
    ctx = ctx_factory("Lose weight, guaranteed!", sandbox=ok_box(sandbox, exit_code=1), sources=SOURCES)

    report = await verifier.verify(TaskSpec(goal="ad", criteria=CRITERIA), ctx)

    assert not report.passed
    assert report.cost_usd == 0
    status = {v.check_id: v.status for v in report.verdicts}
    assert status == {
        "tests": VerdictStatus.FAIL,
        "ad": VerdictStatus.FAIL,
        "facts": VerdictStatus.FAIL,
        "voice": VerdictStatus.PENDING,
        "approve": VerdictStatus.PENDING,
    }
    assert report.skipped == ["voice", "approve"]
    assert report.awaiting_approval == []
    assert "tests (command) failed" in report.feedback
    assert "'guaranteed'" in report.feedback
    assert "no cited claims" in report.feedback
    assert "Not yet checked" in report.feedback and "voice" in report.feedback
    assert len(events.events) == 5
    assert [e.payload["skipped"] for e in events.events][-2:] == [True, True]


async def test_grounded_precheck_failure_skips_judge(ctx_factory, sandbox, no_judge):
    ctx = ctx_factory("Revenue was 9 [src:nope].", sandbox=ok_box(sandbox), sources=SOURCES)
    report = await Verifier(judge_factory=no_judge).verify(CRITERIA[:4], ctx)
    assert report.verdicts[2].status == VerdictStatus.FAIL
    assert "nope" in report.verdicts[2].evidence
    assert report.skipped == ["voice"]


async def test_judge_failure_after_pass_goes_to_human(ctx_factory, sandbox, judge):
    spy = judge(batch_answer)
    ctx = ctx_factory(ANSWER, sandbox=ok_box(sandbox), sources=SOURCES)
    report = await Verifier(judge_factory=spy.factory).verify(CRITERIA, ctx)
    assert not report.passed
    assert report.awaiting_approval == ["approve"]
    assert report.failed == []
    assert report.feedback == ""


async def test_judge_rejection_blocks_human(ctx_factory, sandbox, judge):
    def low(prompt, sections):
        return {
            "s0": {"claims": [{"claim": 1, "label": "supported"}]},
            "s1": {"score": 1, "reasons": ["rude"]},
        }

    report = await Verifier(judge_factory=judge(low).factory).verify(
        CRITERIA, ctx_factory(ANSWER, sandbox=ok_box(sandbox), sources=SOURCES)
    )
    assert report.skipped == ["approve"]
    assert "voice (llm_judge) failed: score 1/5" in report.feedback


async def test_no_judge_available_is_error(ctx_factory, sandbox, judge):
    spy = judge(batch_answer, provider="groq")
    ctx = ctx_factory(ANSWER, sandbox=ok_box(sandbox), sources=SOURCES, executor_provider="groq")
    report = await Verifier(judge_factory=spy.factory).verify(CRITERIA[:4], ctx)
    assert [v.status for v in report.verdicts[2:]] == [VerdictStatus.ERROR] * 2
    assert "must differ" in report.verdicts[3].evidence
    assert "could not run" in report.feedback
    assert spy.calls == 0


async def test_errors_and_unknown_types_block(ctx_factory, no_judge):
    criteria = [
        Criterion(id="cmd", description="needs sandbox", type=CheckType.COMMAND, config={"cmd": "ls"}),
        Criterion(id="mystery", description="?", type="does_not_exist"),
        CRITERIA[3],
    ]
    report = await Verifier(judge_factory=no_judge).verify(criteria, ctx_factory("x"))
    assert [v.status for v in report.verdicts] == [
        VerdictStatus.ERROR,
        VerdictStatus.ERROR,
        VerdictStatus.PENDING,
    ]
    assert "ConfigError" in report.verdicts[0].evidence
    assert "does_not_exist" in report.verdicts[1].evidence


class WordCountCheck:
    type = "word_count"
    stage = CheckStage.DETERMINISTIC

    async def run(self, criterion, ctx):
        from agent0.verify import Verdict

        n = len(ctx.output.split())
        ok = n <= criterion.config["max_words"]
        return Verdict(
            check_id=criterion.id,
            type=criterion.type,
            status=VerdictStatus.PASS if ok else VerdictStatus.FAIL,
            evidence=f"{n} words",
        )


async def test_plugin_check_registers_by_name(ctx_factory):
    registry = default_registry()
    registry.register("word_count", WordCountCheck())
    with pytest.raises(ValueError):
        registry.register("word_count", WordCountCheck())
    assert "word_count" in registry and CheckType.COMMAND in registry

    criterion = Criterion.model_validate(
        {"id": "w", "description": "short", "type": "word_count", "config": {"max_words": 3}}
    )
    builtin = Criterion.model_validate({"id": "b", "description": "x", "type": "command"})
    assert builtin.type is CheckType.COMMAND
    report = await Verifier(registry).verify([criterion], ctx_factory("one two three four"))
    assert not report.passed
    assert report.verdicts[0].evidence == "4 words"


async def test_judge_only_task_warns(ctx_factory, judge):
    spy = judge(lambda p, s: {"s0": {"score": 4, "reasons": []}})
    report = await Verifier(judge_factory=spy.factory).verify([CRITERIA[3]], ctx_factory("hi"))
    assert report.passed
    assert report.warnings


def test_empty_registry():
    assert CheckRegistry().names() == []
