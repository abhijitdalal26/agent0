from __future__ import annotations

from collections.abc import Iterator

import httpx

from agent0.verify.base import Check, CheckType
from agent0.verify.checks.artifact import ArtifactCheck
from agent0.verify.checks.command import CommandCheck
from agent0.verify.checks.grounded import GroundedCheck
from agent0.verify.checks.http import HttpCheck
from agent0.verify.checks.human import HumanCheck
from agent0.verify.checks.llm_judge import LlmJudgeCheck
from agent0.verify.judge import JudgeModelFactory


class CheckRegistry:
    """Maps a criterion `type` name to the check that runs it. Plugins call `register`."""

    def __init__(self) -> None:
        self._checks: dict[str, Check] = {}

    def register(self, name: str, check: Check, *, replace: bool = False) -> None:
        key = str(name)
        if key in self._checks and not replace:
            raise ValueError(f"check type {key!r} is already registered")
        self._checks[key] = check

    def get(self, name: str) -> Check | None:
        return self._checks.get(str(name))

    def names(self) -> list[str]:
        return sorted(self._checks)

    def __contains__(self, name: object) -> bool:
        return str(name) in self._checks

    def __iter__(self) -> Iterator[str]:
        return iter(self._checks)


def default_registry(
    judge_factory: JudgeModelFactory | None = None, http_transport: httpx.AsyncBaseTransport | None = None
) -> CheckRegistry:
    registry = CheckRegistry()
    registry.register(CheckType.COMMAND, CommandCheck())
    registry.register(CheckType.ARTIFACT, ArtifactCheck())
    registry.register(CheckType.HTTP, HttpCheck(transport=http_transport))
    registry.register(CheckType.GROUNDED, GroundedCheck(judge_factory))
    registry.register(CheckType.LLM_JUDGE, LlmJudgeCheck(judge_factory))
    registry.register(CheckType.HUMAN, HumanCheck())
    return registry
