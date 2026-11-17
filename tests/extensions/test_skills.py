from __future__ import annotations

from pathlib import Path

import pytest

from agent0.core.events import MemoryEventSink
from agent0.core.types import EventType
from agent0.extensions.skills import SkillError, SkillLibrary, skill_toolset

SKILL = "---\nname: demo\ndescription: >\n  Does a demo\n  thing.\n---\n# Body\nhello\n"


@pytest.fixture
def lib(tmp_path: Path) -> SkillLibrary:
    d = tmp_path / "skills" / "demo"
    (d / "refs").mkdir(parents=True)
    (d / "SKILL.md").write_text(SKILL, encoding="utf-8")
    (d / "refs" / "a.txt").write_text("ref-a", encoding="utf-8")
    (tmp_path / "skills" / "bad").mkdir()
    (tmp_path / "skills" / "bad" / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    return SkillLibrary([tmp_path / "skills", tmp_path / "missing"])


def test_discovery_and_index(lib: SkillLibrary):
    assert lib.names() == ["demo"]
    assert lib.index() == "demo: Does a demo thing."
    assert lib.index(only=["other"]) == ""


def test_first_dir_wins(tmp_path: Path):
    for root, desc in (("a", "first"), ("b", "second")):
        d = tmp_path / root / "x"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: x\ndescription: {desc}\n---\nbody", encoding="utf-8")
    assert SkillLibrary([tmp_path / "a", tmp_path / "b"]).index() == "x: first"


async def test_load_skill_emits_event(lib: SkillLibrary):
    sink = MemoryEventSink()
    ts = skill_toolset(lib, sink, "run1")
    assert set(ts.tools) == {"load_skill", "read_skill_file"}
    body = await ts.tools["load_skill"].function(name="demo")
    assert body == "# Body\nhello"
    assert sink.events[0].type == EventType.SKILL_LOADED
    assert sink.events[0].payload["name"] == "demo"


async def test_read_skill_file_confined(lib: SkillLibrary):
    ts = skill_toolset(lib)
    read = ts.tools["read_skill_file"].function
    assert await read(name="demo", path="refs/a.txt") == "ref-a"
    for bad in ("../../secret.txt", "../bad/SKILL.md", "/etc/passwd"):
        with pytest.raises(SkillError):
            await read(name="demo", path=bad)
    with pytest.raises(SkillError):
        await read(name="demo", path="missing.txt")


async def test_allowed_filter_and_unknown(lib: SkillLibrary):
    ts = skill_toolset(lib, allowed=[])
    with pytest.raises(SkillError):
        await ts.tools["load_skill"].function(name="demo")
    with pytest.raises(SkillError):
        lib.get("nope")


def test_builtin_skill_parses():
    lib = SkillLibrary([Path(__file__).parents[2] / "skills"])
    assert "report-html" in lib.names()
