from __future__ import annotations

import asyncio
import logging
import os
import posixpath
from pathlib import PurePosixPath
from typing import Any

from agent0.config import Settings
from agent0.sandbox.base import ExecResult
from agent0.sandbox.paths import PathEscapeError, WorkspaceFiles

log = logging.getLogger(__name__)

CONTAINER_WORKSPACE = "/workspace"
DEFAULT_LIFETIME_S = 1800
MAX_MIRROR_DEPTH = 16
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".cache"}


def _virtual(path: str) -> str:
    p = path.replace("\\", "/")
    if not p.startswith("/"):
        p = f"{CONTAINER_WORKSPACE}/{p}"
    p = posixpath.normpath(p)
    if p != CONTAINER_WORKSPACE and not p.startswith(CONTAINER_WORKSPACE + "/"):
        raise PathEscapeError(f"path escapes the workspace: {path}")
    return p


def _kind(entry: Any) -> Any:
    return getattr(entry.type, "value", entry.type)


class E2BSandbox:
    """One E2B microVM. Files live in the VM; `destroy` mirrors them to the host workspace first."""

    def __init__(self, sdk_sandbox: Any, files: WorkspaceFiles, sdk_errors: Any) -> None:
        self._sb = sdk_sandbox
        self.files = files
        self._errors = sdk_errors
        self.id = sdk_sandbox.sandbox_id
        self._destroyed = False

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult:
        workdir = _virtual(cwd) if cwd and cwd != "." else CONTAINER_WORKSPACE
        try:
            res = await asyncio.wait_for(
                self._sb.commands.run(command, cwd=workdir, timeout=timeout_s), timeout_s + 15
            )
        except self._errors.CommandExitException as exc:
            return ExecResult(exit_code=exc.exit_code, stdout=exc.stdout or "", stderr=exc.stderr or "")
        except (self._errors.TimeoutException, TimeoutError):
            return ExecResult(exit_code=-1, stdout="", stderr=f"timed out after {timeout_s}s", timed_out=True)
        return ExecResult(exit_code=res.exit_code, stdout=res.stdout or "", stderr=res.stderr or "")

    async def read_file(self, path: str) -> bytes:
        return bytes(await self._sb.files.read(_virtual(path), format="bytes"))

    async def write_file(self, path: str, data: bytes) -> None:
        await self._sb.files.write(_virtual(path), data)

    async def list_files(self, path: str = ".") -> list[str]:
        entries = await self._sb.files.list(_virtual(path))
        names = [(_kind(e) == "dir", e.name) for e in entries]
        return [n + "/" if is_dir else n for is_dir, n in sorted(names, key=lambda t: (not t[0], t[1]))]

    async def hydrate(self) -> int:
        """Upload files already in the host workspace (earlier attempts, verify) into the new VM."""
        count = 0
        for host in sorted(p for p in self.files.root.rglob("*") if p.is_file()):
            rel = host.relative_to(self.files.root).as_posix()
            await self._sb.files.write(f"{CONTAINER_WORKSPACE}/{rel}", host.read_bytes())
            count += 1
        return count

    async def mirror(self) -> int:
        entries = await self._sb.files.list(CONTAINER_WORKSPACE, depth=MAX_MIRROR_DEPTH)
        count = 0
        for entry in entries:
            if _kind(entry) != "file":
                continue
            rel = PurePosixPath(entry.path).relative_to(CONTAINER_WORKSPACE)
            if _SKIP_DIRS.intersection(rel.parts):
                continue
            try:
                data = bytes(await self._sb.files.read(entry.path, format="bytes"))
                await asyncio.to_thread(self.files.write, rel.as_posix(), data)
                count += 1
            except PathEscapeError:
                log.warning("skipping artifact outside workspace: %s", entry.path)
        return count

    async def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        try:
            await self.mirror()
        except Exception:
            log.exception("could not mirror E2B workspace for %s", self.id)
        finally:
            await self._sb.kill()


class E2BSandboxProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        sdk: Any | None = None,
        errors: Any | None = None,
        lifetime_s: int | None = None,
    ) -> None:
        self.settings = settings
        self._sdk = sdk
        self._errors = errors
        self.lifetime_s = lifetime_s or int(os.environ.get("E2B_SANDBOX_TIMEOUT", DEFAULT_LIFETIME_S))

    def _load(self) -> tuple[Any, Any]:
        if self._sdk is None:
            import e2b

            self._sdk, self._errors = e2b.AsyncSandbox, e2b
        return self._sdk, self._errors

    async def create(self, run_id: str, image: str | None = None) -> E2BSandbox:
        # `image` is a Docker image name for the docker provider; E2B uses templates (E2B_TEMPLATE).
        api_key = os.environ.get("E2B_API_KEY")
        if not api_key:
            raise RuntimeError("E2B_API_KEY is not set")
        sdk, errors = self._load()
        sb = await sdk.create(
            template=os.environ.get("E2B_TEMPLATE") or None,
            timeout=self.lifetime_s,
            metadata={"agent0_run_id": run_id},
            api_key=api_key,
        )
        files = WorkspaceFiles(self.settings.workspace_root / run_id, virtual_root=CONTAINER_WORKSPACE)
        sandbox = E2BSandbox(sb, files, errors)
        try:
            await sandbox.hydrate()
        except BaseException:
            await sb.kill()
            raise
        return sandbox
