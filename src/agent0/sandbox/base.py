from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ExecResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class Sandbox(Protocol):
    id: str

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult: ...
    async def read_file(self, path: str) -> bytes: ...
    async def write_file(self, path: str, data: bytes) -> None: ...
    async def list_files(self, path: str = ".") -> list[str]: ...
    async def destroy(self) -> None: ...


class SandboxProvider(Protocol):
    async def create(self, run_id: str, image: str | None = None) -> Sandbox: ...
