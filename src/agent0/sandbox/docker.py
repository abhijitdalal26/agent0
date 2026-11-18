from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import docker
from docker.errors import ImageNotFound, NotFound

from agent0.config import Settings
from agent0.sandbox.base import ExecResult
from agent0.sandbox.paths import WorkspaceFiles

log = logging.getLogger(__name__)

CONTAINER_WORKSPACE = "/workspace"
LOCAL_IMAGE = "agent0-sandbox:latest"
FALLBACK_IMAGE = "python:3.13-slim"
_TIMEOUT_EXIT_CODES = {124, 137}


class DockerSandbox:
    def __init__(self, container: Any, files: WorkspaceFiles) -> None:
        self._container = container
        self.files = files
        self.id = container.id

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult:
        workdir = CONTAINER_WORKSPACE
        if cwd and cwd != ".":
            rel = self.files.resolve(cwd).relative_to(self.files.root).as_posix()
            if rel != ".":
                workdir = f"{CONTAINER_WORKSPACE}/{rel}"
        argv = ["timeout", "-s", "KILL", str(timeout_s), "sh", "-c", command]

        def run() -> tuple[int, bytes | None, bytes | None]:
            res = self._container.exec_run(argv, workdir=workdir, demux=True)
            out, err = res.output if res.output else (None, None)
            return res.exit_code, out, err

        try:
            code, out, err = await asyncio.wait_for(asyncio.to_thread(run), timeout_s + 15)
        except TimeoutError:
            return ExecResult(exit_code=-1, stdout="", stderr=f"timed out after {timeout_s}s", timed_out=True)
        timed_out = code in _TIMEOUT_EXIT_CODES
        stderr = (err or b"").decode(errors="replace")
        if timed_out and not stderr:
            stderr = f"timed out after {timeout_s}s"
        return ExecResult(
            exit_code=code, stdout=(out or b"").decode(errors="replace"), stderr=stderr, timed_out=timed_out
        )

    async def read_file(self, path: str) -> bytes:
        return await asyncio.to_thread(self.files.read, path)

    async def write_file(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self.files.write, path, data)

    async def list_files(self, path: str = ".") -> list[str]:
        return await asyncio.to_thread(self.files.list, path)

    async def destroy(self) -> None:
        def remove() -> None:
            try:
                self._container.remove(force=True)
            except NotFound:
                pass

        await asyncio.to_thread(remove)


class DockerSandboxProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        memory: str = "1g",
        cpus: float = 1.0,
        pids_limit: int = 256,
        network: bool = True,
    ) -> None:
        self.settings = settings
        self._client = client
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit
        self.network = network

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    async def create(self, run_id: str, image: str | None = None) -> DockerSandbox:
        image = image or self.settings.sandbox_image
        host_dir = self.settings.workspace_root / run_id
        files = WorkspaceFiles(host_dir, virtual_root=CONTAINER_WORKSPACE)

        def start() -> Any:
            name = image
            try:
                self.client.images.get(name)
            except ImageNotFound:
                if name == LOCAL_IMAGE:
                    log.warning("%s not built (infra/sandbox.Dockerfile); using %s", name, FALLBACK_IMAGE)
                    name = FALLBACK_IMAGE
                    with contextlib.suppress(ImageNotFound):
                        self.client.images.get(name)
                        return run(name)
                self.client.images.pull(name)
            return run(name)

        def run(name: str) -> Any:
            return self.client.containers.run(
                name,
                command=["sleep", "infinity"],
                name=f"agent0-{run_id}",
                detach=True,
                working_dir=CONTAINER_WORKSPACE,
                volumes={str(files.root): {"bind": CONTAINER_WORKSPACE, "mode": "rw"}},
                mem_limit=self.memory,
                nano_cpus=int(self.cpus * 1e9),
                pids_limit=self.pids_limit,
                network_mode="bridge" if self.network else "none",
                privileged=False,
                security_opt=["no-new-privileges"],
                labels={"agent0.run_id": run_id},
            )

        container = await asyncio.to_thread(start)
        return DockerSandbox(container, files)
