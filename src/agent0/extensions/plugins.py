from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Iterable
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from agent0.extensions.mcp import McpServerConfig, load_mcp_config

log = logging.getLogger(__name__)


class Plugin(BaseModel):
    name: str
    description: str = ""
    version: str = "0.0.0"
    enabled: bool = True
    checks: list[str] = Field(default_factory=list)
    root: Path

    @field_validator("checks", mode="before")
    @classmethod
    def _listify(cls, v: object) -> object:
        return [v] if isinstance(v, str) else (v or [])

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def mcp_file(self) -> Path:
        return self.root / "mcp.yaml"


def load_plugin(root: Path) -> Plugin:
    data = yaml.safe_load((root / "plugin.yaml").read_text(encoding="utf-8")) or {}
    if "name" not in data:
        raise ValueError(f"{root}: plugin.yaml needs a name")
    return Plugin.model_validate({**data, "root": root})


class PluginManager:
    """Earlier dirs win on name clashes. `disabled` overrides plugin.yaml without editing files."""

    def __init__(self, dirs: Iterable[Path], disabled: Iterable[str] = ()) -> None:
        self._dirs = [Path(d) for d in dirs]
        self._disabled = set(disabled)
        self._plugins: dict[str, Plugin] | None = None

    def discover(self) -> list[Plugin]:
        found: dict[str, Plugin] = {}
        for root in self._dirs:
            if not root.is_dir():
                continue
            for child in sorted(root.iterdir()):
                if not (child / "plugin.yaml").is_file():
                    continue
                try:
                    plugin = load_plugin(child)
                except (ValueError, OSError, yaml.YAMLError) as exc:
                    log.warning("skipping plugin %s: %s", child, exc)
                    continue
                found.setdefault(plugin.name, plugin)
        self._plugins = found
        return list(found.values())

    def enabled(self) -> list[Plugin]:
        if self._plugins is None:
            self.discover()
        return [p for p in (self._plugins or {}).values() if p.enabled and p.name not in self._disabled]

    def skill_dirs(self) -> list[Path]:
        return [p.skills_dir for p in self.enabled() if p.skills_dir.is_dir()]

    def agent_dirs(self) -> list[Path]:
        return [p.agents_dir for p in self.enabled() if p.agents_dir.is_dir()]

    def mcp_servers(self) -> dict[str, McpServerConfig]:
        merged: dict[str, McpServerConfig] = {}
        for p in self.enabled():
            for name, cfg in load_mcp_config(p.mcp_file).items():
                merged.setdefault(name, cfg)
        return merged

    def check_registrars(self) -> list[Callable[..., object]]:
        out: list[Callable[..., object]] = []
        for p in self.enabled():
            for ref in p.checks:
                module, _, attr = ref.partition(":")
                if not module or not attr:
                    raise ValueError(f"plugin {p.name}: checks entry {ref!r} must be 'module:register'")
                out.append(getattr(importlib.import_module(module), attr))
        return out
