from agent0.verify import CheckType, Criterion, VerdictStatus
from agent0.verify.checks import NEEDS_APPROVAL, HumanCheck


async def test_human_is_pending(ctx_factory):
    c = Criterion(id="h1", description="Approve before sending", type=CheckType.HUMAN)
    v = await HumanCheck().run(c, ctx_factory())
    assert v.status == VerdictStatus.PENDING
    assert v.evidence.startswith(NEEDS_APPROVAL)
    assert "Approve before sending" in v.evidence
