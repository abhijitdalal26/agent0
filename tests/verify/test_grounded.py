import pytest

from agent0.knowledge.base import SourceRecord
from agent0.verify import CheckType, Criterion, JudgeUnavailable, VerdictStatus
from agent0.verify.checks import GroundedCheck, parse_claims

SOURCES = [
    SourceRecord(
        source_id="sql:cac:1", source="warehouse", content="channel=search cac_usd=42.50 month=2026-10"
    ),
    SourceRecord(
        source_id="sql:cac:2", source="warehouse", content="channel=social cac_usd=61.00 month=2026-10"
    ),
    SourceRecord(source_id="doc:wiki:7", source="wiki", content="CAC is spend divided by new customers."),
]
GOOD_ANSWER = (
    "Search had a CAC of $42.50 in 2026-10 [src:sql:cac:1]. "
    "Social was the most expensive channel at $61 [src:sql:cac:2].\n"
    "CAC is spend over new customers. [src:doc:wiki:7]"
)


def crit(**config):
    return Criterion(id="g1", description="facts come from the data", type=CheckType.GROUNDED, config=config)


def labels(*items):
    def respond(prompt, sections):
        return {sections[0]: {"claims": [{"claim": n, "label": lab, "reason": r} for n, lab, r in items]}}

    return respond


def test_parse_claims():
    claims = parse_claims(GOOD_ANSWER + " Thanks for asking.")
    assert [c.source_ids for c in claims] == [["sql:cac:1"], ["sql:cac:2"], ["doc:wiki:7"]]
    assert claims[2].text == "CAC is spend over new customers."
    assert parse_claims("Both rose [src:a, src:b].")[0].source_ids == ["a", "b"]


async def test_fabricated_citation_fails_without_judge(ctx_factory, no_judge):
    answer = "Email CAC was $12 [src:sql:cac:99]. Search was $42.50 [src:sql:cac:1]."
    v = await GroundedCheck(no_judge).run(crit(), ctx_factory(answer, sources=SOURCES))
    assert v.status == VerdictStatus.FAIL
    assert "sql:cac:99" in v.evidence
    assert "sql:cac:1," not in v.evidence


async def test_number_not_in_cited_source_fails(ctx_factory, no_judge):
    answer = "Search had a CAC of $45.10 [src:sql:cac:1]."
    v = await GroundedCheck(no_judge).run(crit(), ctx_factory(answer, sources=SOURCES))
    assert v.status == VerdictStatus.FAIL
    assert "45.1" in v.evidence
    skip = await GroundedCheck(no_judge).prepare(
        crit(check_numbers=False), ctx_factory(answer, sources=SOURCES)
    )
    assert not hasattr(skip, "status")


async def test_context_numbers_are_not_data_claims(ctx_factory, no_judge):
    answer = (
        "In Q3 2025 the total was $42.50 [src:sql:cac:1].\n"
        "1. Search $61.00 [src:sql:cac:2]\n"
        "2. Social $42.50 [src:sql:cac:1]"
    )
    request = await GroundedCheck(no_judge).prepare(crit(), ctx_factory(answer, sources=SOURCES))
    assert not hasattr(request, "status")


async def test_years_ignored_unless_overridden(ctx_factory, no_judge):
    answer = "The 1999 figure was $42.50 [src:sql:cac:1]."
    request = await GroundedCheck(no_judge).prepare(crit(), ctx_factory(answer, sources=SOURCES))
    assert not hasattr(request, "status")
    v = await GroundedCheck(no_judge).prepare(
        crit(ignored_number_patterns=[]), ctx_factory(answer, sources=SOURCES)
    )
    assert v.status == VerdictStatus.FAIL
    assert "1999" in v.evidence


async def test_letter_glued_digits_are_not_numbers(ctx_factory, no_judge):
    answer = "Model gpt-oss-20b cost $42.50 [src:sql:cac:1]."
    request = await GroundedCheck(no_judge).prepare(crit(), ctx_factory(answer, sources=SOURCES))
    assert not hasattr(request, "status")


async def test_out_of_scope_source_fails(ctx_factory, no_judge):
    v = await GroundedCheck(no_judge).run(
        crit(allowed_sources=["warehouse"]), ctx_factory(GOOD_ANSWER, sources=SOURCES)
    )
    assert v.status == VerdictStatus.FAIL
    assert "doc:wiki:7" in v.evidence


async def test_abstention_passes_free(ctx_factory, no_judge):
    answer = "That metric is not in the data I can access."
    v = await GroundedCheck(no_judge).run(crit(), ctx_factory(answer, sources=SOURCES))
    assert v.status == VerdictStatus.PASS
    v = await GroundedCheck(no_judge).run(crit(allow_abstention=False), ctx_factory(answer, sources=SOURCES))
    assert v.status == VerdictStatus.FAIL


async def test_uncited_answer_fails(ctx_factory, no_judge):
    v = await GroundedCheck(no_judge).run(crit(), ctx_factory("Search CAC was $42.50.", sources=SOURCES))
    assert v.status == VerdictStatus.FAIL
    assert "[src:" in v.evidence


async def test_non_claim_patterns_skip_boilerplate(ctx_factory, judge):
    answer = GOOD_ANSWER + " See terms. [src:doc:wiki:7]"
    spy = judge(labels((1, "supported", ""), (2, "supported", ""), (3, "supported", "")))
    ctx = ctx_factory(answer, sources=SOURCES, executor_provider="groq")
    v = await GroundedCheck(spy.factory).run(crit(non_claim_patterns=["see terms"]), ctx)
    assert v.status == VerdictStatus.PASS
    assert "See terms" not in spy.prompts[0]


async def test_supported_claims_pass(ctx_factory, judge):
    spy = judge(labels((1, "supported", ""), (2, "supported", ""), (3, "supported", "")))
    ctx = ctx_factory(GOOD_ANSWER, sources=SOURCES, executor_provider="groq")
    v = await GroundedCheck(spy.factory).run(crit(), ctx)
    assert v.status == VerdictStatus.PASS
    assert v.cost_usd == pytest.approx(0.002)
    assert spy.excluded == ["groq"]
    prompt = spy.prompts[0]
    assert "cac_usd=42.50" in prompt
    assert "<untrusted>" in prompt


async def test_unsupported_claim_fails_per_claim(ctx_factory, judge):
    spy = judge(
        labels(
            (1, "supported", ""),
            (2, "unsupported", "source gives a value, not a ranking"),
            (3, "contradicted", "source says new customers, not revenue"),
        )
    )
    v = await GroundedCheck(spy.factory).run(crit(), ctx_factory(GOOD_ANSWER, sources=SOURCES))
    assert v.status == VerdictStatus.FAIL
    lines = v.evidence.splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("claim 2 unsupported") and "ranking" in lines[0]
    assert lines[1].startswith("claim 3 contradicted")


async def test_missing_label_counts_as_unsupported(ctx_factory, judge):
    spy = judge(labels((1, "supported", ""), (2, "supported", "")))
    v = await GroundedCheck(spy.factory).run(crit(), ctx_factory(GOOD_ANSWER, sources=SOURCES))
    assert v.status == VerdictStatus.FAIL
    assert "claim 3 unsupported" in v.evidence


async def test_judge_must_be_another_provider(ctx_factory, judge):
    spy = judge(labels(), provider="groq")
    with pytest.raises(JudgeUnavailable):
        await GroundedCheck(spy.factory).run(
            crit(), ctx_factory(GOOD_ANSWER, sources=SOURCES, executor_provider="groq")
        )
    assert spy.calls == 0
