from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent0.agents.definitions import AgentCatalog
from agent0.config import Settings, get_settings
from agent0.core.events import EventSink, MemoryEventSink
from agent0.extensions.mcp import McpRegistry
from agent0.extensions.plugins import PluginManager
from agent0.extensions.skills import SkillLibrary
from agent0.knowledge.base import KnowledgeSource
from agent0.knowledge.registry import load_sources
from agent0.memory.base import MemoryStore
from agent0.memory.inmemory import InMemoryMemoryStore
from agent0.models.base import UsageSink
from agent0.models.registry import ModelRegistry
from agent0.models.router import Router
from agent0.models.usage import InMemoryUsageSink
from agent0.sandbox import get_provider
from agent0.sandbox.base import SandboxProvider

Notifier = Callable[[str | None, str, list[str]], Awaitable[None]]
ApprovalNotifier = Callable[[str | None, str, str, str], Awaitable[None]]


async def _no_notify(chat_id: str | None, text: str, attachments: list[str]) -> None:
    return None


async def _no_approval_notify(chat_id: str | None, run_id: str, approval_id: str, question: str) -> None:
    return None


@dataclass
class Runtime:
    settings: Settings
    registry: ModelRegistry
    router: Router
    agents: AgentCatalog
    skills: SkillLibrary
    mcp: McpRegistry
    plugins: PluginManager
    knowledge: dict[str, KnowledgeSource]
    memory: MemoryStore
    events: EventSink
    usage: UsageSink
    sandboxes: SandboxProvider
    repos: Any = None
    notify: Notifier = _no_notify
    notify_approval: ApprovalNotifier = _no_approval_notify
    check_registrars: list[Callable[..., Any]] = field(default_factory=list)


def build_runtime(
    settings: Settings | None = None,
    *,
    pool: Any = None,
    events: EventSink | None = None,
    notify: Notifier | None = None,
) -> Runtime:
    s = settings or get_settings()
    plugins = PluginManager(s.plugins_dirs)
    registry = ModelRegistry.load(s.config_dir / "models.yaml")
    agents = AgentCatalog.load([Path("agents"), *plugins.agent_dirs()])
    skills = SkillLibrary([*s.skills_dirs, *plugins.skill_dirs()])
    mcp = McpRegistry.from_file(s.config_dir / "mcp.yaml")
    mcp.merge(plugins.mcp_servers())
    knowledge = load_sources(s.config_dir / "knowledge.yaml", pool=pool)

    if pool is not None:
        from agent0.db.repos import PgEventSink, PgUsageSink, Repos
        from agent0.memory.pg import PgMemoryStore

        repos: Any = Repos(pool)
        memory: MemoryStore = PgMemoryStore(pool)
        sink: EventSink = events or PgEventSink(pool)
        usage: UsageSink = PgUsageSink(pool)
    else:
        repos, memory = None, InMemoryMemoryStore()
        sink, usage = events or MemoryEventSink(), InMemoryUsageSink()

    return Runtime(
        settings=s,
        registry=registry,
        router=Router(registry),
        agents=agents,
        skills=skills,
        mcp=mcp,
        plugins=plugins,
        knowledge=knowledge,
        memory=memory,
        events=sink,
        usage=usage,
        sandboxes=get_provider(s),
        repos=repos,
        notify=notify or _no_notify,
        check_registrars=plugins.check_registrars(),
    )
