from __future__ import annotations

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, ConfigError, require, tail, verdict


class CommandCheck:
    type = CheckType.COMMAND
    stage = CheckStage.DETERMINISTIC

    def __init__(self, evidence_chars: int = 1500) -> None:
        self.evidence_chars = evidence_chars

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        cmd = str(require(criterion, "cmd"))
        if ctx.sandbox is None:
            raise ConfigError("command check needs a sandbox")
        cfg = criterion.config
        expect_exit = int(cfg.get("expect_exit", 0))
        result = await ctx.sandbox.exec(cmd, timeout_s=int(cfg.get("timeout_s", 120)), cwd=cfg.get("cwd"))
        output = "\n".join(part for part in (result.stdout, result.stderr) if part.strip())
        evidence_tail = tail(output, self.evidence_chars)

        if result.timed_out:
            return verdict(criterion, VerdictStatus.FAIL, f"`{cmd}` timed out.\n{evidence_tail}")
        if result.exit_code != expect_exit:
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                f"`{cmd}` exited {result.exit_code} (expected {expect_exit}).\n{evidence_tail}",
            )
        needle = cfg.get("expect_stdout_contains")
        if needle and str(needle) not in result.stdout:
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                f"`{cmd}` stdout does not contain {needle!r}.\n{evidence_tail}",
            )
        return verdict(
            criterion, VerdictStatus.PASS, f"`{cmd}` exited {result.exit_code}.\n{tail(output, 300)}"
        )
