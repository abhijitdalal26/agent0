from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent0.agents.definitions import AgentCatalog
from agent0.extensions.mcp import McpRegistry
from agent0.extensions.plugins import PluginManager
from agent0.extensions.skills import SkillLibrary

ROOT = Path(__file__).parents[2]


def make_plugin(base: Path, name: str, enabled: bool = True, checks: str = "") -> Path:
    p = base / name
    (p / "skills" / f"{name}-skill").mkdir(parents=True)
    (p / "agents" / f"{name}-agent").mkdir(parents=True)
    (p / "plugin.yaml").write_text(
        f"name: {name}\ndescription: d\nversion: 1.0.0\nenabled: {str(enabled).lower()}\n{checks}",
        encoding="utf-8",
    )
    (p / "skills" / f"{name}-skill" / "SKILL.md").write_text(
        f"---\nname: {name}-skill\ndescription: from {name}\n---\nbody", encoding="utf-8"
    )
    (p / "agents" / f"{name}-agent" / "agent.md").write_text(
        f"---\ndescription: from {name}\n---\nDo {name}.", encoding="utf-8"
    )
    (p / "mcp.yaml").write_text(
        f"servers:\n  - {{name: {name}-srv, transport: http, url: 'https://{name}.test/mcp'}}\n",
        encoding="utf-8",
    )
    return p


def test_discover_enabled_and_merge(tmp_path: Path):
    make_plugin(tmp_path, "alpha")
    make_plugin(tmp_path, "beta", enabled=False)
    make_plugin(tmp_path, "gamma")
    mgr = PluginManager([tmp_path], disabled=["gamma"])
    assert [p.name for p in mgr.discover()] == ["alpha", "beta", "gamma"]
    assert [p.name for p in mgr.enabled()] == ["alpha"]

    lib = SkillLibrary(mgr.skill_dirs())
    assert lib.names() == ["alpha-skill"]
    cat = AgentCatalog.load(mgr.agent_dirs())
    assert cat.names() == ["alpha-agent"]
    reg = McpRegistry()
    reg.merge(mgr.mcp_servers())
    assert reg.names() == ["alpha-srv"]


def test_check_registrars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "plug_mod.py").write_text("def register(reg):\n    reg.append('ok')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("plug_mod", None)
    make_plugin(tmp_path / "plugins", "delta", checks="checks: plug_mod:register\n")
    fns = PluginManager([tmp_path / "plugins"]).check_registrars()
    seen: list[str] = []
    fns[0](seen)
    assert seen == ["ok"]


def test_bad_check_ref(tmp_path: Path):
    make_plugin(tmp_path, "eps", checks="checks: [nocolon]\n")
    with pytest.raises(ValueError):
        PluginManager([tmp_path]).check_registrars()


def test_example_plugin():
    mgr = PluginManager([ROOT / "plugins"])
    assert [p.name for p in mgr.enabled()] == ["creative"]
    assert "ad-compliance" in SkillLibrary(mgr.skill_dirs()).names()
    assert AgentCatalog.load(mgr.agent_dirs()).names() == ["art-director", "copywriter"]
