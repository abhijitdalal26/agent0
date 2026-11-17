from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field

from agent0.knowledge.base import SourceRecord
from agent0.verify.base import CheckType, Criterion, Verdict, VerdictStatus, VerifyContext
from agent0.verify.checks._util import CheckStage, head, verdict
from agent0.verify.judge import JudgeModelFactory, JudgeRequest, run_judged, untrusted

CITATION = re.compile(r"\[src:\s*([^\]]+)\]", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
_LEADING_CITATIONS = re.compile(r"^(?:\[src:[^\]]+\][\s.,;:]*)+", re.IGNORECASE)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

DEFAULT_ABSTENTION_PATTERNS = [
    r"\bnot (?:in|available in|present in|found in|contained in) the (?:data|sources?|provided)",
    r"\b(?:data|sources?) (?:does|do) not (?:contain|include|say|mention|show)",
    r"\bno (?:relevant )?(?:data|information|records?) (?:is |was |were )?(?:available|found)",
    r"\binsufficient (?:data|information)",
    r"\bcannot be (?:determined|answered) from",
]


@dataclass
class Claim:
    text: str
    source_ids: list[str]


def parse_claims(output: str) -> list[Claim]:
    """Sentences carrying `[src:<id>]` citations; a citation opening a segment belongs to the one before."""
    segments: list[str] = []
    for raw in _SENTENCE_END.split(output):
        segment = raw.strip()
        if segments and (lead := _LEADING_CITATIONS.match(segment)):
            segments[-1] = f"{segments[-1]} {lead.group(0).strip()}"
            segment = segment[lead.end() :].strip()
        if segment:
            segments.append(segment)
    claims = []
    for segment in segments:
        ids = [
            part.strip().removeprefix("src:").strip()
            for match in CITATION.finditer(segment)
            for part in match.group(1).split(",")
        ]
        if ids := list(dict.fromkeys(i for i in ids if i)):
            claims.append(Claim(text=" ".join(CITATION.sub("", segment).split()), source_ids=ids))
    return claims


def _numbers(text: str) -> set[str]:
    found = set()
    for raw in _NUMBER.findall(text):
        try:
            found.add(format(Decimal(raw.replace(",", "")).normalize(), "f"))
        except InvalidOperation:
            continue
    return found


class ClaimLabel(BaseModel):
    claim: int = Field(description="The claim number as given")
    label: Literal["supported", "unsupported", "contradicted"]
    reason: str = Field(default="", description="One short sentence, required unless supported")


class GroundedJudgement(BaseModel):
    claims: list[ClaimLabel]


class GroundedCheck:
    """Config: allow_abstention (true), check_numbers (true), allowed_sources (source names in scope),
    abstention_patterns (regexes), max_source_chars (2000)."""

    type = CheckType.GROUNDED
    stage = CheckStage.JUDGE

    def __init__(self, judge_factory: JudgeModelFactory | None = None) -> None:
        self.judge_factory = judge_factory

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict:
        return await run_judged(self, self.judge_factory, criterion, ctx)

    async def prepare(self, criterion: Criterion, ctx: VerifyContext) -> Verdict | JudgeRequest:
        cfg = criterion.config
        text = ctx.output
        if path := cfg.get("path"):
            if ctx.sandbox is None:
                return verdict(criterion, VerdictStatus.ERROR, "grounded with a path needs a sandbox")
            try:
                text = (await ctx.sandbox.read_file(path)).decode("utf-8", errors="replace")
            except Exception as exc:
                return verdict(criterion, VerdictStatus.FAIL, f"{path} not found or unreadable: {exc}")
        claims = parse_claims(text)
        if not claims:
            patterns = cfg.get("abstention_patterns", DEFAULT_ABSTENTION_PATTERNS)
            if any(re.search(p, text, re.IGNORECASE) for p in patterns):
                if cfg.get("allow_abstention", True):
                    return verdict(
                        criterion, VerdictStatus.PASS, "answer abstains: the data does not contain it"
                    )
                return verdict(
                    criterion, VerdictStatus.FAIL, "answer abstains but this task requires an answer"
                )
            return verdict(
                criterion,
                VerdictStatus.FAIL,
                "answer has no cited claims: cite every fact as [src:<source_id>], "
                "or say the data does not contain the answer",
            )

        by_id = {s.source_id: s for s in ctx.sources}
        problems = []
        unknown = sorted({i for c in claims for i in c.source_ids if i not in by_id})
        if unknown:
            problems.append(f"cited source ids not in the retrieved data: {', '.join(unknown)}")
        if allowed := cfg.get("allowed_sources"):
            out_of_scope = sorted(
                {i for c in claims for i in c.source_ids if i in by_id and by_id[i].source not in allowed}
            )
            if out_of_scope:
                problems.append(f"cited sources outside the allowed scope: {', '.join(out_of_scope)}")
        if cfg.get("check_numbers", True):
            for n, claim in enumerate(claims, 1):
                cited_text = " ".join(by_id[i].content for i in claim.source_ids if i in by_id)
                if missing := sorted(_numbers(claim.text) - _numbers(cited_text)):
                    problems.append(
                        f"claim {n} numbers {', '.join(missing)} not found in its cited sources: "
                        f'"{head(claim.text, 160)}"'
                    )
        if problems:
            return verdict(criterion, VerdictStatus.FAIL, "\n".join(problems))

        prompt = self._prompt(claims, by_id, int(cfg.get("max_source_chars", 2000)))
        return JudgeRequest(criterion=criterion, prompt=prompt, output_type=GroundedJudgement, state=claims)

    @staticmethod
    def _prompt(claims: list[Claim], by_id: dict[str, SourceRecord], max_chars: int) -> str:
        cited = dict.fromkeys(i for c in claims for i in c.source_ids)
        sources = "\n".join(f"[src:{i}]\n{untrusted(head(by_id[i].content, max_chars))}" for i in cited)
        numbered = "\n".join(
            f"{n}. {untrusted(c.text)} cites: {', '.join(c.source_ids)}" for n, c in enumerate(claims, 1)
        )
        return (
            "Label every claim using only the text of the sources it cites: supported (the cited text "
            "states it), unsupported (the cited text does not state it), contradicted (the cited text says "
            f"otherwise).\nSources:\n{sources}\n\nClaims:\n{numbered}"
        )

    def finalize(self, request: JudgeRequest, result: BaseModel, cost_usd: float) -> Verdict:
        assert isinstance(result, GroundedJudgement)
        claims: list[Claim] = request.state
        labels = {item.claim: item for item in result.claims}
        failures = []
        for n, claim in enumerate(claims, 1):
            item = labels.get(n)
            label, reason = (item.label, item.reason) if item else ("unsupported", "judge gave no label")
            if label != "supported":
                failures.append(f'claim {n} {label}: "{head(claim.text, 160)}" — {reason}'.rstrip(" —"))
        if failures:
            return verdict(request.criterion, VerdictStatus.FAIL, "\n".join(failures), cost_usd=cost_usd)
        return verdict(
            request.criterion,
            VerdictStatus.PASS,
            f"{len(claims)} claims supported by their cited sources",
            cost_usd=cost_usd,
        )
