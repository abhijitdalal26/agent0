import pytest

from agent0.sandbox.base import ExecResult
from agent0.verify import CheckType, Criterion, VerdictStatus
from agent0.verify.checks import CommandCheck, ConfigError


def crit(**config):
    return Criterion(id="c1", description="tests pass", type=CheckType.COMMAND, config=config)


async def test_passes_on_exit_zero(ctx_factory, sandbox):
    box = sandbox(commands={"pytest": ExecResult(exit_code=0, stdout="5 passed", stderr="")})
    v = await CommandCheck().run(crit(cmd="pytest"), ctx_factory(sandbox=box))
    assert v.status == VerdictStatus.PASS
    assert "5 passed" in v.evidence


async def test_fails_with_output_tail(ctx_factory, sandbox):
    noisy = "\n".join(f"line {i}" for i in range(2000)) + "\nFAILED test_login"
    box = sandbox(commands={"pytest": ExecResult(exit_code=1, stdout=noisy, stderr="")})
    v = await CommandCheck(evidence_chars=200).run(crit(cmd="pytest"), ctx_factory(sandbox=box))
    assert v.status == VerdictStatus.FAIL
    assert "exited 1" in v.evidence
    assert "FAILED test_login" in v.evidence
    assert "line 0\n" not in v.evidence
    assert len(v.evidence) < 300


async def test_expect_exit_and_stdout(ctx_factory, sandbox):
    box = sandbox(commands={"grep x f": ExecResult(exit_code=1, stdout="", stderr="")})
    v = await CommandCheck().run(crit(cmd="grep x f", expect_exit=1), ctx_factory(sandbox=box))
    assert v.status == VerdictStatus.PASS

    box = sandbox(commands={"./app": ExecResult(exit_code=0, stdout="hello", stderr="")})
    v = await CommandCheck().run(
        crit(cmd="./app", expect_stdout_contains="goodbye"), ctx_factory(sandbox=box)
    )
    assert v.status == VerdictStatus.FAIL
    assert "goodbye" in v.evidence


async def test_timeout_fails(ctx_factory, sandbox):
    box = sandbox(commands={"sleep": ExecResult(exit_code=0, stdout="", stderr="", timed_out=True)})
    v = await CommandCheck().run(crit(cmd="sleep"), ctx_factory(sandbox=box))
    assert v.status == VerdictStatus.FAIL
    assert "timed out" in v.evidence


async def test_needs_cmd_and_sandbox(ctx_factory, sandbox):
    with pytest.raises(ConfigError):
        await CommandCheck().run(crit(), ctx_factory(sandbox=sandbox()))
    with pytest.raises(ConfigError):
        await CommandCheck().run(crit(cmd="ls"), ctx_factory())
