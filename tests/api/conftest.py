from __future__ import annotations

import pytest
from api_fakes import FakeOrchestrator, FakeRepos, FakeStream
from fastapi.testclient import TestClient

from agent0.agents.definitions import AgentCatalog, AgentDef
from agent0.api import ApiDeps, create_app
from agent0.config import Settings
from agent0.core.types import Capability
from agent0.extensions.mcp import McpRegistry
from agent0.extensions.plugins import PluginManager
from agent0.extensions.skills import SkillLibrary
from agent0.models.base import Cost, ModelProfile
from agent0.models.registry import ModelRegistry, set_secret_resolver
from agent0.models.router import Router
from agent0.secrets import InMemorySecretStore, generate_key

API_KEY = "test-api-key"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
KEY_ENV = "TEST_GROQ_API_KEY"


def make_profile(name: str, key_env: str = KEY_ENV, cap: Capability = Capability.CHAT, **kw) -> ModelProfile:
    return ModelProfile(
        name=name,
        provider="groq",
        model=name,
        capability=cap,
        key_env=key_env,
        tags=["cheap"],
        cost=Cost(input_per_mtok=1.0),
        **kw,
    )


class Env:
    def __init__(self, tmp_path) -> None:
        self.repos = FakeRepos()
        self.orchestrator = FakeOrchestrator(self.repos)
        self.stream = FakeStream()
        self.registry = ModelRegistry([make_profile("fast"), make_profile("vis", cap=Capability.VISION)])
        self.secrets = InMemorySecretStore(generate_key())
        self.tested: list[tuple] = []
        self.settings = Settings(
            _env_file=None,
            api_key=API_KEY,
            workspace_root=tmp_path / "ws",
            secret_key=None,
            cors_origins=["http://dash.example"],
        )
        skill = tmp_path / "skills" / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: a demo skill\n---\nbody text\n")

        async def tester(name: str, value: str, profile):
            self.tested.append((name, profile.provider if profile else None))
            return True, f"ok {value}"

        self.deps = ApiDeps(
            repos=self.repos,
            orchestrator=self.orchestrator,
            registry=self.registry,
            router=Router(self.registry),
            secrets=self.secrets,
            skills=SkillLibrary([tmp_path / "skills"]),
            mcp=McpRegistry({}),
            plugins=PluginManager([]),
            agents=AgentCatalog({"executor": AgentDef(name="executor", instructions="do it")}),
            event_stream=self.stream,
            settings=self.settings,
            secret_tester=tester,
        )
        self.app = create_app(self.deps)
        self.client = TestClient(self.app, headers=HEADERS)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv(KEY_ENV, raising=False)
    monkeypatch.delenv("AGENT0_TELEGRAM_BOT_TOKEN", raising=False)
    e = Env(tmp_path)
    yield e
    set_secret_resolver(None)


@pytest.fixture
def client(env):
    return env.client
