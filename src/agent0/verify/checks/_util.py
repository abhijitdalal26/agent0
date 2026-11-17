from __future__ import annotations

from enum import StrEnum

from agent0.verify.base import Criterion, Verdict, VerdictStatus


class CheckStage(StrEnum):
    DETERMINISTIC = "deterministic"
    JUDGE = "judge"
    HUMAN = "human"


class ConfigError(ValueError):
    pass


def tail(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"…{text[-limit:]}"


def head(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else f"{text[:limit]}…"


def require(criterion: Criterion, key: str) -> object:
    if key not in criterion.config:
        raise ConfigError(f"criterion {criterion.id!r} ({criterion.type}) needs config.{key}")
    return criterion.config[key]


def verdict(
    criterion: Criterion,
    status: VerdictStatus,
    evidence: str,
    *,
    score: float | None = None,
    cost_usd: float = 0.0,
) -> Verdict:
    return Verdict(
        check_id=criterion.id,
        type=criterion.type,
        status=status,
        evidence=evidence,
        score=score,
        cost_usd=cost_usd,
    )
