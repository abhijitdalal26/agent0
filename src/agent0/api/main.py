from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path

from fastapi import FastAPI

from agent0.agents.definitions import AgentCatalog
from agent0.api.app import create_app
from agent0.api.deps import ApiDeps
from agent0.api.errors import ApiError
from agent0.api.testers import default_tester
from agent0.config import Settings, get_settings
from agent0.core.types import Run, Task
from agent0.db.pool import apply_schema, close_pool, create_pool
from agent0.db.repos import PgEventSink, Repos
from agent0.extensions.mcp import McpRegistry
from agent0.extensions.plugins import PluginManager
from agent0.extensions.skills import SkillLibrary
from agent0.models.registry import ModelRegistry
from agent0.models.router import Router
from agent0.secrets import PgSecretStore

ORCHESTRATOR_ENV = "AGENT0_ORCHESTRATOR_FACTORY"


class UnavailableOrchestrator:
    async def _fail(self) -> None:
        raise ApiError(503, "orchestrator_unavailable", f"set {ORCHESTRATOR_ENV}=module:factory")

    async def submit(self, task: Task) -> Run:
        await self._fail()
        raise AssertionError

    async def stop(self, run_id: str) -> None:
        await self._fail()

    async def retry(self, task_id: str) -> Run:
        await self._fail()
        raise AssertionError

    async def decide_approval(self, approval_id: str, decision: str, by: str, note: str | None) -> None:
        await self._fail()


async def _orchestrator(settings: Settings, repos: Repos):
    ref = os.environ.get(ORCHESTRATOR_ENV)
    if not ref:
        return UnavailableOrchestrator()
    module, _, attr = ref.partition(":")
    result = getattr(importlib.import_module(module), attr)(settings, repos)
    return await result if inspect.isawaitable(result) else result


async def build_deps() -> ApiDeps:
    settings = get_settings()
    pool = await create_pool(settings)
    await apply_schema(pool)
    repos = Repos(pool)
    registry = ModelRegistry.load(settings.config_dir / "models.yaml")
    plugins = PluginManager(settings.plugins_dirs)
    skills = SkillLibrary([*settings.skills_dirs, *plugins.skill_dirs()])
    mcp = McpRegistry.from_file(settings.config_dir / "mcp.yaml")
    mcp.merge(plugins.mcp_servers())
    agents = AgentCatalog.load([Path("agents"), Path.home() / ".agent0" / "agents", *plugins.agent_dirs()])
    return ApiDeps(
        close=lambda: close_pool(pool),
        repos=repos,
        orchestrator=await _orchestrator(settings, repos),
        registry=registry,
        router=Router(registry),
        secrets=PgSecretStore(pool, settings.secret_key),
        skills=skills,
        mcp=mcp,
        plugins=plugins,
        agents=agents,
        event_stream=PgEventSink(pool),
        settings=settings,
        secret_tester=default_tester,
    )


def app_factory() -> FastAPI:
    """uvicorn agent0.api.main:app_factory --factory"""
    return create_app(build_deps=build_deps)
