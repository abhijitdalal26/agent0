from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.toolsets import PrefixedToolset

from agent0.extensions.mcp import (
    McpRegistry,
    McpServerConfig,
    build_toolset,
    interpolate,
    load_mcp_config,
    parse_mcp_config,
)


def test_interpolate(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOK", "abc")
    monkeypatch.delenv("NOPE", raising=False)
    assert interpolate("Bearer ${TOK}") == "Bearer abc"
    assert interpolate("${NOPE:-dflt}/x") == "dflt/x"
    with pytest.raises(ValueError, match="NOPE"):
        interpolate("${NOPE}")


def test_config_load_and_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOK", "abc")
    f = tmp_path / "mcp.yaml"
    f.write_text(
        "servers:\n"
        "  - {name: web, transport: http, url: 'https://x.test/mcp',\n"
        "     headers: {Authorization: 'Bearer ${TOK}'}}\n"
        "  - {name: fs, transport: stdio, command: npx, args: [srv, '${TOK}'], env: {K: '${TOK}'}}\n",
        encoding="utf-8",
    )
    servers = load_mcp_config(f)
    assert set(servers) == {"web", "fs"}
    assert servers["web"].headers["Authorization"] == "Bearer ${TOK}"
    assert servers["web"].resolved().headers["Authorization"] == "Bearer abc"
    assert servers["fs"].resolved().args == ["srv", "abc"]
    assert load_mcp_config(tmp_path / "none.yaml") == {}


def test_validation():
    with pytest.raises(ValueError):
        parse_mcp_config({"servers": [{"name": "a", "transport": "stdio"}]})
    with pytest.raises(ValueError):
        parse_mcp_config({"servers": [{"name": "a", "transport": "http"}]})


def test_repo_config_parses():
    assert "filesystem" in load_mcp_config(Path(__file__).parents[2] / "config" / "mcp.yaml")


def test_build_toolset_prefixes():
    cfg = McpServerConfig(name="web", transport="http", url="https://x.test/mcp")
    ts = build_toolset(cfg)
    assert isinstance(ts, PrefixedToolset)
    assert isinstance(ts.wrapped, MCPToolset)
    assert f"{ts.prefix}_search" == "mcp__web__search"


async def test_test_connection_lists_prefixed_tools(monkeypatch: pytest.MonkeyPatch):
    async def fake_list_tools(self: MCPToolset) -> list[SimpleNamespace]:
        return [SimpleNamespace(name="add"), SimpleNamespace(name="sub")]

    monkeypatch.setattr(MCPToolset, "list_tools", fake_list_tools)
    cfg = McpServerConfig(name="demo", transport="http", url="http://unused.test/mcp")
    reg = McpRegistry({"demo": cfg})
    assert await reg.test_connection("demo") == ["mcp__demo__add", "mcp__demo__sub"]
    assert reg.toolset("demo") is reg.toolset("demo")
    assert len(reg.toolsets(["demo"])) == 1
    with pytest.raises(KeyError):
        reg.toolset("nope")
