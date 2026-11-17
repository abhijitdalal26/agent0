from __future__ import annotations

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, verdict

NEEDS_APPROVAL = "needs_approval"


class HumanCheck:
    """Never decides; the orchestrator sees `needs_approval` and waits for the human."""

    type = CheckType.HUMAN
    stage = CheckStage.HUMAN

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        message = criterion.config.get("message") or criterion.description
        return verdict(criterion, VerdictStatus.PENDING, f"{NEEDS_APPROVAL}: {message}")
