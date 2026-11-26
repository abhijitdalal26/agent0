from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent0.core.types import Budget, Capability
from agent0.extensions.frontmatter import split_frontmatter

log = logging.getLogger(__name__)


class AgentDef(BaseModel):
    name: str
    description: str = ""
    instructions: str
    capability: Capability = Capability.CHAT
    prefer: Literal["cheap", "fast", "smart"] | None = None
    tools: list[str] = Field(default_factory=list)
    skills: list[str] | Literal["all"] = Field(default_factory=list)
    mcp: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, float | int] = Field(default_factory=dict)
    source: Path | None = None

    def effective_budget(self, base: Budget | None = None) -> Budget:
        # Agent budgets are caps: the stricter of task and agent wins per field.
        budget = (base or Budget()).model_copy()
        for key, limit in self.budget.items():
            if key in Budget.model_fields:
                setattr(budget, key, min(getattr(budget, key), limit))
        return budget


def parse_agent(path: Path) -> AgentDef:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    meta.setdefault("name", path.parent.name)
    if not body:
        raise ValueError(f"{path}: agent.md has no instructions body")
    return AgentDef.model_validate({**meta, "instructions": body, "source": path})


class AgentCatalog:
    def __init__(self, agents: dict[str, AgentDef] | None = None) -> None:
        self._agents = dict(agents or {})

    @classmethod
    def load(cls, dirs: Iterable[Path]) -> AgentCatalog:
        """Earlier dirs win on name clashes."""
        agents: dict[str, AgentDef] = {}
        for root in map(Path, dirs):
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                path = child / "agent.md"
                if not path.is_file():
                    continue
                try:
                    agent = parse_agent(path)
                except ValueError as exc:
                    log.warning("skipping agent %s: %s", path, exc)
                    continue
                agents.setdefault(agent.name, agent)
        return cls(agents)

    def get(self, name: str) -> AgentDef:
        try:
            return self._agents[name]
        except KeyError:
            raise KeyError(f"unknown agent {name!r}; available: {', '.join(self.names())}") from None

    def names(self) -> list[str]:
        return sorted(self._agents)

    def all(self) -> list[AgentDef]:
        return [self._agents[n] for n in self.names()]

    def __contains__(self, name: str) -> bool:
        return name in self._agents
