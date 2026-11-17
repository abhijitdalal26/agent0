from enum import Enum
from types import SimpleNamespace

import pytest

from agent0.config import Settings
from agent0.sandbox import PathEscapeError
from agent0.sandbox.e2b import E2BSandboxProvider


class FT(Enum):
    FILE = "file"
    DIR = "dir"


class CommandExitException(Exception):
    def __init__(self, exit_code, stdout="", stderr=""):
        self.exit_code, self.stdout, self.stderr = exit_code, stdout, stderr


class TimeoutException(Exception):
    pass


ERRORS = SimpleNamespace(CommandExitException=CommandExitException, TimeoutException=TimeoutException)


class FakeFiles:
    def __init__(self):
        self.store: dict[str, bytes] = {}

    async def write(self, path, data):
        self.store[path] = data if isinstance(data, bytes) else data.encode()

    async def read(self, path, format="text"):
        return bytearray(self.store[path])

    async def list(self, path, depth=1):
        prefix = path.rstrip("/") + "/"
        out = {}
        for p in self.store:
            if not p.startswith(prefix):
                continue
            parts = p[len(prefix) :].split("/")
            if depth == 1:
                name = parts[0]
                kind = FT.FILE if len(parts) == 1 else FT.DIR
                out[p if kind is FT.FILE else prefix + name] = SimpleNamespace(
                    name=name, type=kind, path=prefix + name
                )
            else:
                out[p] = SimpleNamespace(name=parts[-1], type=FT.FILE, path=p)
        return list(out.values())


class FakeCommands:
    def __init__(self):
        self.calls = []
        self.behavior = lambda cmd: SimpleNamespace(exit_code=0, stdout="ok\n", stderr="")

    async def run(self, cmd, cwd=None, timeout=None, **kw):  # noqa: ASYNC109
        self.calls.append((cmd, cwd, timeout))
        return self.behavior(cmd)


class FakeSandbox:
    created: list["FakeSandbox"] = []

    def __init__(self):
        self.sandbox_id = "sbx-1"
        self.files = FakeFiles()
        self.commands = FakeCommands()
        self.killed = False

    @classmethod
    async def create(cls, **kwargs):
        sb = cls()
        sb.kwargs = kwargs
        cls.created.append(sb)
        return sb

    async def kill(self):
        self.killed = True


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "e2b_test")
    monkeypatch.delenv("E2B_TEMPLATE", raising=False)
    FakeSandbox.created.clear()


def provider(tmp_path):
    return E2BSandboxProvider(
        Settings(workspace_root=tmp_path), sdk=FakeSandbox, errors=ERRORS, lifetime_s=600
    )


async def test_create_passes_key_timeout_and_requires_key(tmp_path, monkeypatch):
    sb = await provider(tmp_path).create("r1", "python:3.13-slim")
    kw = FakeSandbox.created[0].kwargs
    assert kw["api_key"] == "e2b_test" and kw["timeout"] == 600 and kw["template"] is None
    assert sb.id == "sbx-1"
    monkeypatch.delenv("E2B_API_KEY")
    with pytest.raises(RuntimeError, match="E2B_API_KEY"):
        await provider(tmp_path).create("r2")


async def test_exec_maps_results(tmp_path):
    sb = await provider(tmp_path).create("r1")
    cmds = FakeSandbox.created[0].commands
    r = await sb.exec("echo", timeout_s=5)
    assert r.ok and r.stdout == "ok\n"
    assert cmds.calls[-1] == ("echo", "/workspace", 5)
    await sb.exec("ls", cwd="sub")
    assert cmds.calls[-1][1] == "/workspace/sub"

    def fail(cmd):
        raise CommandExitException(2, "", "boom")

    cmds.behavior = fail
    r = await sb.exec("false")
    assert (r.exit_code, r.stderr, r.timed_out) == (2, "boom", False)

    def slow(cmd):
        raise TimeoutException()

    cmds.behavior = slow
    assert (await sb.exec("sleep 9", timeout_s=1)).timed_out
    with pytest.raises(PathEscapeError):
        await sb.exec("ls", cwd="/etc")


async def test_file_ops_and_confinement(tmp_path):
    sb = await provider(tmp_path).create("r1")
    await sb.write_file("a/b.txt", b"hi")
    assert FakeSandbox.created[0].files.store["/workspace/a/b.txt"] == b"hi"
    assert await sb.read_file("/workspace/a/b.txt") == b"hi"
    await sb.write_file("/workspace/top.txt", b"x")
    assert await sb.list_files(".") == ["a/", "top.txt"]
    for bad in ("/etc/passwd", "../x", "/workspace/../etc"):
        with pytest.raises(PathEscapeError):
            await sb.read_file(bad)


async def test_destroy_mirrors_then_kills(tmp_path):
    sb = await provider(tmp_path).create("r1")
    fake = FakeSandbox.created[0]
    await sb.write_file("out/report.html", b"<p>")
    await sb.write_file("node_modules/x/index.js", b"skip")
    await sb.destroy()
    assert (tmp_path / "r1" / "out" / "report.html").read_bytes() == b"<p>"
    assert not (tmp_path / "r1" / "node_modules").exists()
    assert fake.killed
    await sb.destroy()


async def test_destroy_kills_even_if_mirror_fails(tmp_path):
    sb = await provider(tmp_path).create("r1")
    fake = FakeSandbox.created[0]

    async def boom(*a, **k):
        raise OSError("net")

    fake.files.list = boom
    await sb.destroy()
    assert fake.killed


async def test_create_hydrates_from_host_workspace(tmp_path):
    (tmp_path / "r1" / "d").mkdir(parents=True)
    (tmp_path / "r1" / "d" / "f.py").write_bytes(b"print(1)")
    await provider(tmp_path).create("r1")
    assert FakeSandbox.created[0].files.store["/workspace/d/f.py"] == b"print(1)"
