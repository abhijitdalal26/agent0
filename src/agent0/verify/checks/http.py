from __future__ import annotations

import httpx

from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, head, require, verdict


class HttpCheck:
    type = CheckType.HTTP
    stage = CheckStage.DETERMINISTIC

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        url = str(require(criterion, "url"))
        cfg = criterion.config
        expected = cfg.get("expect_status", 200)
        allowed = {int(s) for s in expected} if isinstance(expected, list) else {int(expected)}
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=float(cfg.get("timeout_s", 15)), follow_redirects=True
            ) as client:
                response = await client.get(url)
        except httpx.HTTPError as exc:
            return verdict(criterion, VerdictStatus.FAIL, f"GET {url} failed: {type(exc).__name__}: {exc}")

        if response.status_code not in allowed:
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                f"GET {url} returned {response.status_code}, expected {sorted(allowed)}.\n"
                f"{head(response.text, 500)}",
            )
        needle = cfg.get("expect_text")
        if needle and str(needle) not in response.text:
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                f"GET {url} body does not contain {needle!r}.\n{head(response.text, 500)}",
            )
        return verdict(criterion, VerdictStatus.PASS, f"GET {url} returned {response.status_code}")
