from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, Field, SkipValidation

from agent0.knowledge.base import SourceRecord
from agent0.sandbox.base import Sandbox


class CheckType(StrEnum):
    COMMAND = "command"
    ARTIFACT = "artifact"
    HTTP = "http"
    BROWSER = "browser"
    GROUNDED = "grounded"
    LLM_JUDGE = "llm_judge"
    HUMAN = "human"


class VerdictStatus(StrEnum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


# Plugin check types register by name, so a criterion may carry a type outside the built-in enum.
CheckTypeName = Annotated[CheckType | str, Field(union_mode="left_to_right")]


class Criterion(BaseModel):
    id: str
    description: str
    type: CheckTypeName
    config: dict[str, Any] = Field(default_factory=dict)


class Verdict(BaseModel):
    check_id: str
    type: CheckTypeName
    status: VerdictStatus
    evidence: str = ""
    score: float | None = None
    cost_usd: float = 0.0


class TaskSpec(BaseModel):
    goal: str
    steps: list[str] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)


class VerifyContext(BaseModel):
    """Everything a check may inspect. Never includes the executor's self-assessment."""

    model_config = {"arbitrary_types_allowed": True}

    run_id: str
    task_prompt: str
    output: str
    # Sandbox is a non-runtime Protocol, so pydantic cannot isinstance-check it.
    sandbox: SkipValidation[Sandbox | None] = None
    sources: list[SourceRecord] = Field(default_factory=list)
    executor_provider: str | None = None


class Check(Protocol):
    @property
    def type(self) -> CheckType | str: ...

    async def run(self, criterion: Criterion, ctx: VerifyContext) -> Verdict: ...
