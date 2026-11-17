import sys

import pytest

from agent0.config import Settings
from agent0.sandbox import PathEscapeError, get_provider
from agent0.sandbox.docker import DockerSandboxProvider
from agent0.sandbox.e2b import E2BSandboxProvider
from agent0.sandbox.local import LocalSandboxProvider


@pytest.fixture
async def sb(tmp_path):
    provider = LocalSandboxProvider(Settings(workspace_root=tmp_path))
    return await provider.create("run1")


async def test_exec_and_exit_code(sb):
    r = await sb.exec("echo hello")
    assert r.ok and "hello" in r.stdout
    assert (await sb.exec("exit 3")).exit_code == 3


async def test_exec_timeout(sb):
    r = await sb.exec(f'"{sys.executable}" -c "import time; time.sleep(30)"', timeout_s=1)
    assert r.timed_out and not r.ok


async def test_exec_runs_in_workspace_and_hides_secrets(sb, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "s3cret")
    await sb.write_file("a.txt", b"x")
    cmd = f'"{sys.executable}" -c "import os; print(os.listdir(), os.environ.get(\'MY_API_KEY\'))"'
    r = await sb.exec(cmd)
    assert "a.txt" in r.stdout and "s3cret" not in r.stdout


async def test_file_roundtrip_and_list(sb):
    await sb.write_file("sub/dir/f.txt", b"data")
    assert await sb.read_file("sub/dir/f.txt") == b"data"
    await sb.write_file("top.txt", b"1")
    assert await sb.list_files(".") == ["sub/", "top.txt"]


@pytest.mark.parametrize("path", ["../x", "../../etc/passwd", "a/../../x", "/etc/passwd", "C:\\Windows\\x"])
async def test_path_confinement(sb, path):
    with pytest.raises(PathEscapeError):
        await sb.write_file(path, b"x")
    with pytest.raises(PathEscapeError):
        await sb.read_file(path)


async def test_symlink_escape(sb, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = sb.workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(PathEscapeError):
        await sb.write_file("link/x", b"x")


async def test_cwd_confined(sb):
    with pytest.raises(PathEscapeError):
        await sb.exec("echo hi", cwd="..")


def test_get_provider(tmp_path):
    assert isinstance(get_provider(Settings(sandbox="local", workspace_root=tmp_path)), LocalSandboxProvider)
    assert isinstance(
        get_provider(Settings(sandbox="docker", workspace_root=tmp_path)), DockerSandboxProvider
    )
    assert isinstance(get_provider(Settings(sandbox="e2b")), E2BSandboxProvider)


async def test_e2b_stub():
    with pytest.raises(NotImplementedError):
        await E2BSandboxProvider(Settings()).create("r")
