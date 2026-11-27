from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel
from pydantic_ai.toolsets import FunctionToolset

from agent0.core.events import EventSink
from agent0.core.types import EventType
from agent0.extensions.frontmatter import split_frontmatter

log = logging.getLogger(__name__)

MAX_FILE_BYTES = 200_000


class Skill(BaseModel):
    name: str
    description: str
    dir: Path

    @property
    def body_path(self) -> Path:
        return self.dir / "SKILL.md"


class SkillError(Exception):
    pass


def parse_skill(skill_dir: Path) -> Skill:
    meta, _ = split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    name, description = meta.get("name"), meta.get("description")
    if not isinstance(name, str) or not isinstance(description, str) or not name or not description:
        raise ValueError(f"{skill_dir}: SKILL.md needs frontmatter name and description")
    return Skill(name=name, description=" ".join(description.split()), dir=skill_dir)


class SkillLibrary:
    """Earlier dirs win on name clashes, so project skills shadow user and plugin ones."""

    def __init__(self, dirs: Iterable[Path] = ()) -> None:
        self._dirs = [Path(d) for d in dirs]
        self._skills: dict[str, Skill] = {}
        self.refresh()

    def refresh(self) -> None:
        skills: dict[str, Skill] = {}
        for root in self._dirs:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not (child / "SKILL.md").is_file():
                    continue
                try:
                    skill = parse_skill(child)
                except (ValueError, OSError) as exc:
                    log.warning("skipping skill %s: %s", child, exc)
                    continue
                skills.setdefault(skill.name, skill)
        self._skills = skills

    def names(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError:
            raise SkillError(
                f"unknown skill {name!r}; available: {', '.join(self.names()) or 'none'}"
            ) from None

    def index(self, only: list[str] | None = None) -> str:
        names = self.names() if only is None else [n for n in self.names() if n in only]
        return "\n".join(f"{n}: {self._skills[n].description}" for n in names)

    def body(self, name: str) -> str:
        _, body = split_frontmatter(self.get(name).body_path.read_text(encoding="utf-8"))
        return body

    def read_file(self, name: str, path: str) -> str:
        root = self.get(name).dir.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            raise SkillError(f"path {path!r} escapes the skill directory")
        if not target.is_file():
            raise SkillError(f"no such file in skill {name!r}: {path}")
        if target.stat().st_size > MAX_FILE_BYTES:
            raise SkillError(f"file too large (>{MAX_FILE_BYTES} bytes): {path}")
        return target.read_text(encoding="utf-8", errors="replace")


def skill_toolset(
    library: SkillLibrary,
    sink: EventSink | None = None,
    run_id: str = "",
    allowed: list[str] | None = None,
) -> FunctionToolset:
    def check(name: str) -> None:
        if allowed is not None and name not in allowed:
            raise SkillError(f"skill {name!r} is not enabled for this agent")

    async def load_skill(name: str) -> str:
        """Load the full instructions of a skill listed in the skill index."""
        try:
            check(name)
            body = library.body(name)
        except (SkillError, OSError) as exc:
            return f"error: {exc}"
        if sink is not None:
            await sink.emit(run_id, EventType.SKILL_LOADED, {"name": name, "chars": len(body)})
        return body

    async def read_skill_file(name: str, path: str) -> str:
        """Read a file bundled with a skill, by path relative to the skill folder."""
        try:
            check(name)
            return library.read_file(name, path)
        except (SkillError, OSError) as exc:
            return f"error: {exc}"

    return FunctionToolset([load_skill, read_skill_file], id="skills")
