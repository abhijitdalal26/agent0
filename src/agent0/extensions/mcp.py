from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import AbstractToolset, PrefixedToolset

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def interpolate(value: str, env: dict[str, str] | None = None) -> str:
    env = dict(os.environ) if env is None else env

    def sub(m: re.Match[str]) -> str:
        var, default = m.group(1), m.group(2)
        if var in env:
            return env[var]
        if default is not None:
            return default
        raise ValueError(f"environment variable {var} is not set")

    return _ENV_REF.sub(sub, value)


class McpServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    description: str = ""

    @model_validator(mode="after")
    def _check(self) -> McpServerConfig:
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"mcp server {self.name}: stdio needs command")
        if self.transport == "http" and not self.url:
            raise ValueError(f"mcp server {self.name}: http needs url")
        return self

    def resolved(self, env: dict[str, str] | None = None) -> McpServerConfig:
        return self.model_copy(
            update={
                "command": interpolate(self.command, env) if self.command else None,
                "args": [interpolate(a, env) for a in self.args],
                "env": {k: interpolate(v, env) for k, v in self.env.items()},
                "url": interpolate(self.url, env) if self.url else None,
                "headers": {k: interpolate(v, env) for k, v in self.headers.items()},
            }
        )


def parse_mcp_config(data: dict[str, Any]) -> dict[str, McpServerConfig]:
    servers: dict[str, McpServerConfig] = {}
    for entry in data.get("servers") or []:
        cfg = McpServerConfig.model_validate(entry)
        servers[cfg.name] = cfg
    return servers


def load_mcp_config(path: Path) -> dict[str, McpServerConfig]:
    if not path.is_file():
        return {}
    return parse_mcp_config(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def tool_prefix(server: str) -> str:
    # PrefixedToolset joins prefix and tool name with one "_", giving mcp__<server>__<tool>.
    return f"mcp__{server}_"


def build_toolset(cfg: McpServerConfig) -> AbstractToolset[Any]:
    cfg = cfg.resolved()
    inner: MCPToolset[Any]
    if cfg.transport == "stdio":
        from fastmcp.client.transports import StdioTransport

        transport = StdioTransport(command=cfg.command or "", args=cfg.args, env=cfg.env or None)
        inner = MCPToolset(transport, id=cfg.name)
    else:
        inner = MCPToolset(cfg.url or "", id=cfg.name, headers=cfg.headers or None)
    return PrefixedToolset(inner, tool_prefix(cfg.name))


class McpRegistry:
    """Toolsets are built on first request; MCPToolset itself connects on first use."""

    def __init__(
        self,
        servers: dict[str, McpServerConfig] | None = None,
        factory: Callable[[McpServerConfig], AbstractToolset[Any]] = build_toolset,
    ) -> None:
        self.servers: dict[str, McpServerConfig] = dict(servers or {})
        self._factory = factory
        self._toolsets: dict[str, AbstractToolset[Any]] = {}

    @classmethod
    def from_file(cls, path: Path) -> McpRegistry:
        return cls(load_mcp_config(path))

    def merge(self, servers: dict[str, McpServerConfig]) -> None:
        for name, cfg in servers.items():
            self.servers.setdefault(name, cfg)

    def names(self) -> list[str]:
        return sorted(self.servers)

    def toolset(self, name: str) -> AbstractToolset[Any]:
        if name not in self.servers:
            raise KeyError(f"unknown mcp server {name!r}")
        if name not in self._toolsets:
            self._toolsets[name] = self._factory(self.servers[name])
        return self._toolsets[name]

    def toolsets(self, names: list[str]) -> list[AbstractToolset[Any]]:
        return [self.toolset(n) for n in names]

    async def test_connection(self, name: str) -> list[str]:
        ts = self.toolset(name)
        inner = ts.wrapped if isinstance(ts, PrefixedToolset) else ts
        if not isinstance(inner, MCPToolset):
            raise TypeError(f"mcp server {name!r} is not an MCPToolset")
        prefix = tool_prefix(name)
        return [f"{prefix}_{t.name}" for t in await inner.list_tools()]
