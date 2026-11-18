import shutil
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent0.config import Settings
from agent0.sandbox import PathEscapeError
from agent0.sandbox.docker import DockerSandboxProvider


async def test_container_options(tmp_path):
    client = MagicMock()
    provider = DockerSandboxProvider(Settings(workspace_root=tmp_path), client=client, network=False)
    sb = await provider.create("r1")
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["privileged"] is False
    assert kwargs["network_mode"] == "none"
    assert kwargs["mem_limit"] == "1g"
    assert kwargs["volumes"][str((tmp_path / "r1").resolve())]["bind"] == "/workspace"
    await sb.write_file("/workspace/a.txt", b"x")
    assert (tmp_path / "r1" / "a.txt").read_bytes() == b"x"
    with pytest.raises(PathEscapeError):
        await sb.read_file("/etc/passwd")


async def test_unbuilt_local_image_falls_back(tmp_path):
    from docker.errors import ImageNotFound

    def get(name):
        if "agent0" in name:
            raise ImageNotFound(name)

    client = MagicMock()
    client.images.get.side_effect = get
    provider = DockerSandboxProvider(Settings(workspace_root=tmp_path), client=client)
    await provider.create("r1")
    assert client.containers.run.call_args.args[0] == "python:3.13-slim"
    client.images.pull.assert_not_called()


async def test_exec_mapping(tmp_path):
    client = MagicMock()
    provider = DockerSandboxProvider(Settings(workspace_root=tmp_path), client=client)
    sb = await provider.create("r1")
    sb._container.exec_run.return_value = SimpleNamespace(exit_code=137, output=(None, None))
    r = await sb.exec("sleep 9", timeout_s=1)
    assert r.timed_out
    sb._container.exec_run.return_value = SimpleNamespace(exit_code=0, output=(b"hi\n", b""))
    assert (await sb.exec("echo hi")).stdout == "hi\n"


@pytest.mark.integration
async def test_real_docker(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("docker not installed")
    provider = DockerSandboxProvider(Settings(workspace_root=tmp_path))
    sb = await provider.create("itest")
    try:
        r = await sb.exec("echo hi && pwd")
        assert r.ok and "hi" in r.stdout and "/workspace" in r.stdout
        await sb.write_file("a.txt", b"data")
        assert (await sb.exec("cat a.txt")).stdout == "data"
        await sb.exec("echo made > b.txt")
        assert await sb.read_file("b.txt") == b"made\n"
        assert (await sb.exec("sleep 10", timeout_s=1)).timed_out
    finally:
        await sb.destroy()
