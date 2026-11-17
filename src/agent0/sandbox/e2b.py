from __future__ import annotations

from agent0.config import Settings
from agent0.sandbox.base import ExecResult


class E2BSandbox:
    id: str = ""

    async def exec(self, command: str, timeout_s: int = 120, cwd: str | None = None) -> ExecResult:
        raise NotImplementedError("E2B sandbox is planned for phase 3")

    async def read_file(self, path: str) -> bytes:
        raise NotImplementedError

    async def write_file(self, path: str, data: bytes) -> None:
        raise NotImplementedError

    async def list_files(self, path: str = ".") -> list[str]:
        raise NotImplementedError

    async def destroy(self) -> None:
        raise NotImplementedError


class E2BSandboxProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create(self, run_id: str, image: str | None = None) -> E2BSandbox:
        raise NotImplementedError("E2B sandbox is planned for phase 3")
