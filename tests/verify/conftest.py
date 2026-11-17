from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from agent0.sandbox.base import ExecResult
from agent0.verify import JudgeModel, VerifyContext

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


class FakeSandbox:
    def __init__(
        self, files: dict[str, bytes | str] | None = None, commands: dict[str, ExecResult] | None = None
    ) -> None:
        self.id = "fake"
        self.files = {k: v.encode() if isinstance(v, str) else v for k, v in (files or {}).items()}
        self.commands = commands or {}
        self.executed: list[str] = []

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult:
        self.executed.append(command)
        return self.commands.get(
            command, ExecResult(exit_code=127, stdout="", stderr=f"{command}: not found")
        )

    async def read_file(self, path: str) -> bytes:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def write_file(self, path: str, data: bytes) -> None:
        self.files[path] = data

    async def list_files(self, path: str = ".") -> list[str]:
        return sorted(self.files)

    async def destroy(self) -> None:
        pass


@dataclass
class JudgeSpy:
    """Builds FunctionModel judges and records every prompt the judge was sent."""

    respond: Callable[[str, list[str]], dict[str, Any]]
    provider: str = "judgeco"
    cost_per_call: float = 0.002
    prompts: list[str] = field(default_factory=list)
    instructions: list[str | None] = field(default_factory=list)
    excluded: list[str | None] = field(default_factory=list)

    def _fn(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompt = "\n".join(
            str(part.content)
            for msg in messages
            if isinstance(msg, ModelRequest)
            for part in msg.parts
            if isinstance(part, UserPromptPart)
        )
        self.prompts.append(prompt)
        self.instructions.append(info.instructions)
        tool = info.output_tools[0]
        sections = list(tool.parameters_json_schema["properties"])
        return ModelResponse(parts=[ToolCallPart(tool_name=tool.name, args=self.respond(prompt, sections))])

    def factory(self, exclude_provider: str | None) -> JudgeModel:
        self.excluded.append(exclude_provider)
        return JudgeModel(
            model=FunctionModel(self._fn), provider=self.provider, cost_fn=lambda _u: self.cost_per_call
        )

    @property
    def calls(self) -> int:
        return len(self.prompts)


def forbidden_factory(exclude_provider: str | None) -> JudgeModel:
    raise AssertionError("the judge must not be called")


@pytest.fixture
def ctx_factory() -> Callable[..., VerifyContext]:
    def make(output: str = "", **kw: Any) -> VerifyContext:
        return VerifyContext(
            run_id="r1", task_prompt=kw.pop("task_prompt", "do the task"), output=output, **kw
        )

    return make


@pytest.fixture
def sandbox() -> type[FakeSandbox]:
    return FakeSandbox


@pytest.fixture
def judge() -> type[JudgeSpy]:
    return JudgeSpy


@pytest.fixture
def no_judge() -> Callable[[str | None], JudgeModel]:
    return forbidden_factory
