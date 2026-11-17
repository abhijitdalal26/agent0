import sys

import httpx
import pytest
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from agent0.config import Settings
from agent0.core.events import MemoryEventSink
from agent0.core.types import EventType
from agent0.policy import ApprovalRequired, BudgetExceeded, BudgetMeter, PermissionLevel, Policy
from agent0.sandbox.local import LocalSandboxProvider
from agent0.tools import ToolDeps, build_toolset, call_key, truncate

PAGE = (
    "<html><head><title>t</title><style>x{}</style></head>"
    "<body><script>bad()</script><h1>Hello</h1><p>World</p></body></html>"
)


def html_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/redir":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        if request.url.path == "/img":
            return httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")
        return httpx.Response(200, headers={"content-type": "text/html"}, text=PAGE)

    return httpx.MockTransport(handler)


@pytest.fixture
async def env(tmp_path):
    sandbox = await LocalSandboxProvider(Settings(workspace_root=tmp_path)).create("r1")
    sink = MemoryEventSink()
    deps = ToolDeps(run_id="r1", sandbox=sandbox, events=sink, budget=BudgetMeter())
    toolset = build_toolset(web_transport=html_transport())

    async def call(name, **kwargs):
        ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
        return await toolset.tools[name].function(ctx, **kwargs)

    return deps, sink, call


async def test_shell_and_events(env):
    deps, sink, call = env
    out = await call("shell", command="echo hi")
    assert "exit_code: 0" in out and "hi" in out
    assert [e.type for e in sink.events] == [EventType.TOOL_CALL, EventType.TOOL_RESULT]
    assert sink.events[1].payload["ok"] is True
    assert deps.budget.steps == 1


async def test_forbidden_returns_refusal(env):
    _, sink, call = env
    out = await call("shell", command="rm -rf /")
    assert out.startswith("refused")
    assert sink.events[-1].payload["ok"] is False


async def test_needs_approval_then_approved(env):
    deps, _, call = env
    with pytest.raises(ApprovalRequired) as e:
        await call("shell", command="git push origin main")
    assert e.value.tool == "shell" and e.value.tool_args == {"command": "git push origin main"}
    deps.approved.add(call_key("shell", {"command": "git push origin main"}))
    assert "exit_code" in await call("shell", command="git push origin main")


async def test_file_tools(env):
    _, _, call = env
    assert "wrote 5" in await call("write_file", path="d/a.txt", content="hello")
    assert await call("read_file", path="d/a.txt") == "hello"
    assert await call("list_files", path=".") == "d/"
    assert "not found" in await call("read_file", path="nope.txt")


async def test_path_escape_is_refusal(env):
    _, _, call = env
    assert (await call("write_file", path="../x", content="a")).startswith("refused")
    assert (await call("read_file", path="/etc/passwd")).startswith("refused")


async def test_read_file_truncation_and_offset(env):
    _, _, call = env
    await call("write_file", path="big.txt", content="a" * 9000)
    out = await call("read_file", path="big.txt")
    assert len(out) < 4200 and "9000 chars" in out and "offset=4000" in out
    assert "offset" not in await call("read_file", path="big.txt", offset=8000)


async def test_shell_truncation(env):
    _, _, call = env
    out = await call("shell", command=f'"{sys.executable}" -c "print(9000*chr(120))"')
    assert len(out) < 4300 and "omitted" in out


async def test_web_fetch(env):
    _, _, call = env
    out = await call("web_fetch", url="https://example.com/")
    assert "untrusted" in out and "Hello" in out and "World" in out and "bad()" not in out
    assert "non-text" in await call("web_fetch", url="https://example.com/img")
    assert "blocked" in await call("web_fetch", url="http://localhost:8000/")
    assert "blocked" in await call("web_fetch", url="http://169.254.169.254/")
    assert "only http" in await call("web_fetch", url="file:///etc/passwd")
    assert "blocked" in await call("web_fetch", url="https://example.com/redir")


async def test_budget_exhaustion_propagates(env):
    deps, _, call = env
    deps.budget = BudgetMeter(max_steps=1)
    await call("shell", command="echo a")
    with pytest.raises(BudgetExceeded):
        await call("shell", command="echo b")


async def test_read_only_policy(env):
    deps, _, call = env
    deps.policy = Policy(level=PermissionLevel.READ_ONLY)
    with pytest.raises(ApprovalRequired):
        await call("write_file", path="a", content="x")


def test_truncate():
    assert truncate("short") == ("short", False)
    out, cut = truncate("x" * 10000)
    assert cut and "10000" in out and len(out) < 4200


def test_toolset_names():
    assert set(build_toolset().tools) == {"shell", "read_file", "write_file", "list_files", "web_fetch"}
