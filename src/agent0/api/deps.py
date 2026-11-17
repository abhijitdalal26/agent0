from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Protocol

from fastapi import Depends, Request

from agent0.agents.definitions import AgentCatalog
from agent0.config import Settings
from agent0.core.types import Event, Run, Task
from agent0.extensions.mcp import McpRegistry
from agent0.extensions.plugins import PluginManager
from agent0.extensions.skills import SkillLibrary
from agent0.models.registry import ModelRegistry
from agent0.models.router import Router
from agent0.secrets import SecretStore


class Orchestrator(Protocol):
    async def submit(self, task: Task) -> Run: ...
    async def stop(self, run_id: str) -> None: ...
    async def retry(self, task_id: str) -> Run: ...
    async def decide_approval(self, approval_id: str, decision: str, by: str, note: str | None) -> None: ...


class EventStream(Protocol):
    def subscribe(self, run_id: str | None = None) -> AsyncIterator[Event]: ...


# (secret name, plaintext value, provider of the profiles using it) -> (ok, message)
SecretTester = Callable[[str, str, str | None], Awaitable[tuple[bool, str]]]


@dataclass
class ApiDeps:
    repos: Any
    orchestrator: Orchestrator
    registry: ModelRegistry
    router: Router
    secrets: SecretStore
    skills: SkillLibrary
    mcp: McpRegistry
    plugins: PluginManager
    agents: AgentCatalog
    event_stream: EventStream
    settings: Settings
    secret_tester: SecretTester | None = None
    close: Callable[[], Awaitable[None]] | None = None


def get_deps(request: Request) -> ApiDeps:
    return request.app.state.deps


Deps = Annotated[ApiDeps, Depends(get_deps)]
