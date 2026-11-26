from __future__ import annotations

from pathlib import Path

import pytest

from agent0.agents.definitions import AgentCatalog, parse_agent
from agent0.core.types import Budget, Capability

ROOT = Path(__file__).parents[2]


def write(tmp_path: Path, name: str, text: str) -> Path:
    d = tmp_path / name
    d.mkdir(parents=True)
    f = d / "agent.md"
    f.write_text(text, encoding="utf-8")
    return f


def test_parse_full(tmp_path: Path):
    f = write(
        tmp_path,
        "writer",
        "---\ndescription: w\ncapability: vision\nprefer: fast\ntools: [a, b]\nskills: all\n"
        "mcp: [fs]\npolicy: {x: 1}\nbudget: {max_steps: 5}\n---\nBe brief.\n",
    )
    a = parse_agent(f)
    assert a.name == "writer"
    assert a.capability == Capability.VISION
    assert a.prefer == "fast"
    assert a.tools == ["a", "b"]
    assert a.skills == "all"
    assert a.mcp == ["fs"]
    assert a.policy == {"x": 1}
    assert a.instructions == "Be brief."
    assert a.effective_budget(Budget(max_steps=40)).max_steps == 5
    assert a.effective_budget(Budget(max_steps=3)).max_steps == 3
    assert a.effective_budget(Budget(max_steps=40)).max_usd == Budget().max_usd


def test_defaults_and_errors(tmp_path: Path):
    a = parse_agent(write(tmp_path, "min", "Just instructions."))
    assert a.capability == Capability.CHAT and a.skills == [] and a.prefer is None
    with pytest.raises(ValueError):
        parse_agent(write(tmp_path, "empty", "---\nname: empty\n---\n"))
    with pytest.raises(ValueError):
        parse_agent(write(tmp_path, "unterminated", "---\nname: u\nbody"))


def test_catalog_first_dir_wins_and_skips_bad(tmp_path: Path):
    write(tmp_path / "a", "x", "---\ndescription: first\n---\nA")
    write(tmp_path / "b", "x", "---\ndescription: second\n---\nB")
    write(tmp_path / "b", "broken", "---\nprefer: bogus\n---\nB")
    cat = AgentCatalog.load([tmp_path / "a", tmp_path / "b", tmp_path / "none"])
    assert cat.names() == ["x"]
    assert cat.get("x").description == "first"
    with pytest.raises(KeyError):
        cat.get("zzz")


def test_builtin_agents():
    cat = AgentCatalog.load([ROOT / "agents"])
    assert cat.names() == ["executor", "marketer", "planner", "verifier"]
    assert cat.get("executor").skills == "all"
    assert "[src:<id>]" in cat.get("executor").instructions
