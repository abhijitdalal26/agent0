import pytest

from agent0.core.types import Budget, RunStatus, Task
from agent0.orchestrator.loop import Decision, drive
from agent0.orchestrator.steps import AttemptResult, PendingApproval, Report
from agent0.verify import Criterion, TaskSpec, Verdict, VerdictStatus
from agent0.verify.base import CheckType


def verdict(status, type=CheckType.COMMAND, cid="c1"):
    return Verdict(check_id=cid, type=type, status=status, evidence="e")


class FakeSteps:
    def __init__(self, attempts, reports, decisions=()):
        self.attempts, self.reports, self.decisions = list(attempts), list(reports), list(decisions)
        self.feedbacks, self.statuses, self.asked, self.finished = [], [], [], None

    async def status(self, status, step=None):
        self.statuses.append(status)

    async def plan(self):
        return TaskSpec(goal="g", criteria=[Criterion(id="c1", description="d", type=CheckType.COMMAND)])

    async def execute(self, spec, attempt, feedback, approved):
        self.feedbacks.append((feedback, list(approved)))
        return self.attempts.pop(0)

    async def verify(self, spec, result):
        return self.reports.pop(0)

    async def ask(self, question):
        self.asked.append(question)
        return self.decisions.pop(0)

    async def milestone(self, text):
        pass

    async def finish(self, outcome, result):
        self.finished = outcome


def task(retries=2):
    return Task(title="t", prompt="p", budget=Budget(max_retries=retries))


def done(output="ok"):
    return AttemptResult(status="done", output=output, provider="groq")


async def test_retry_with_feedback_then_pass():
    fail = Report(passed=False, verdicts=[verdict(VerdictStatus.FAIL)], feedback="fix c1")
    ok = Report(passed=True, verdicts=[verdict(VerdictStatus.PASS)])
    steps = FakeSteps([done(), done()], [fail, ok])
    out = await drive(task(), steps)
    assert out.status == RunStatus.SUCCEEDED and out.attempts == 2
    assert steps.feedbacks[1][0] == "fix c1"


async def test_gives_up_after_max_retries():
    fail = Report(passed=False, verdicts=[verdict(VerdictStatus.FAIL)], feedback="x")
    steps = FakeSteps([done()] * 2, [fail] * 2)
    out = await drive(task(retries=1), steps)
    assert out.status == RunStatus.FAILED and out.attempts == 2


async def test_tool_approval_resumes_with_key():
    pending = AttemptResult(
        status="needs_approval",
        approval=PendingApproval(tool="shell", args={"command": "git push"}, reason="r", key="k1"),
    )
    ok = Report(passed=True, verdicts=[verdict(VerdictStatus.PASS)])
    steps = FakeSteps([pending, done()], [ok], [Decision(approved=True, by="me")])
    out = await drive(task(), steps)
    assert out.status == RunStatus.SUCCEEDED
    assert steps.feedbacks[1][1] == ["k1"]
    assert RunStatus.WAITING_APPROVAL in steps.statuses


async def test_human_check_rejection_retries():
    human = Report(
        passed=False,
        verdicts=[verdict(VerdictStatus.PASS), verdict(VerdictStatus.PENDING, CheckType.HUMAN, "c2")],
        awaiting_approval=["c2"],
    )
    steps = FakeSteps(
        [done(), done()],
        [human, human],
        [Decision(approved=False, by="me", note="too salesy"), Decision(approved=True, by="me")],
    )
    out = await drive(task(), steps)
    assert out.status == RunStatus.SUCCEEDED and out.attempts == 2
    assert "too salesy" in steps.feedbacks[1][0]


async def test_budget_stops_run():
    steps = FakeSteps([AttemptResult(status="budget", error="usd")], [])
    out = await drive(task(), steps)
    assert out.status == RunStatus.STOPPED and steps.finished is out


def test_check_plan_rejects_unrunnable_criteria():
    from pydantic_ai.exceptions import ModelRetry

    from agent0.orchestrator.steps import check_plan
    from agent0.verify import Criterion, TaskSpec

    ok = TaskSpec(
        goal="g",
        criteria=[
            Criterion(id="c1", type="command", description="tests pass", config={"cmd": "pytest"}),
            Criterion(id="c2", type="artifact", description="file exists", config={"path": "a.py"}),
        ],
    )
    assert check_plan(ok) is ok
    bad = TaskSpec(goal="g", criteria=[Criterion(id="c1", type="command", description="tests pass")])
    with pytest.raises(ModelRetry, match="c1.*config.cmd"):
        check_plan(bad)
