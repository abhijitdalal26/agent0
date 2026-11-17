from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
from pathlib import Path

from agent0.config import Settings
from agent0.sandbox.base import ExecResult
from agent0.sandbox.paths import WorkspaceFiles

_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def _clean_env() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("AGENT0_") and not any(m in k.upper() for m in _SECRET_MARKERS)
    }


class LocalSandbox:
    """Runs commands on the host. Only the file API is confined; shell commands are not isolated."""

    def __init__(self, run_id: str, root: Path) -> None:
        self.id = f"local-{run_id}"
        self.files = WorkspaceFiles(root)
        self.workspace = self.files.root

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult:
        # A thread instead of asyncio subprocesses: on Windows psycopg forces the selector loop,
        # which cannot spawn subprocesses.
        return await asyncio.to_thread(self._exec, command, timeout_s, self.files.resolve(cwd or "."))

    def _exec(self, command: str, timeout_s: int, workdir: Path) -> ExecResult:
        posix = sys.platform != "win32"
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=workdir,
            env=_clean_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=posix,
        )
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self._kill(proc, posix)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.communicate(timeout=5)
            return ExecResult(exit_code=-1, stdout="", stderr=f"timed out after {timeout_s}s", timed_out=True)
        return ExecResult(
            exit_code=proc.returncode if proc.returncode is not None else -1,
            stdout=out.decode(errors="replace"),
            stderr=err.decode(errors="replace"),
        )

    @staticmethod
    def _kill(proc: subprocess.Popen[bytes], posix: bool) -> None:
        # killpg/SIGKILL are POSIX-only per typeshed; getattr keeps pyright quiet.
        killpg = getattr(os, "killpg", None)
        with contextlib.suppress(ProcessLookupError):
            if posix and killpg is not None:
                killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            elif sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            else:
                proc.kill()

    async def read_file(self, path: str) -> bytes:
        return await asyncio.to_thread(self.files.read, path)

    async def write_file(self, path: str, data: bytes) -> None:
        await asyncio.to_thread(self.files.write, path, data)

    async def list_files(self, path: str = ".") -> list[str]:
        return await asyncio.to_thread(self.files.list, path)

    async def destroy(self) -> None:
        return None


class LocalSandboxProvider:
    def __init__(self, settings: Settings) -> None:
        self.root = settings.workspace_root

    async def create(self, run_id: str, image: str | None = None) -> LocalSandbox:
        return LocalSandbox(run_id, self.root / run_id)
