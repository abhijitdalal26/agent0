from __future__ import annotations

from agent0.config import Settings
from agent0.sandbox.base import ExecResult, Sandbox, SandboxProvider
from agent0.sandbox.paths import PathEscapeError


def get_provider(settings: Settings) -> SandboxProvider:
    match settings.sandbox:
        case "local":
            from agent0.sandbox.local import LocalSandboxProvider

            return LocalSandboxProvider(settings)
        case "e2b":
            from agent0.sandbox.e2b import E2BSandboxProvider

            return E2BSandboxProvider(settings)
        case _:
            from agent0.sandbox.docker import DockerSandboxProvider

            return DockerSandboxProvider(settings)


__all__ = ["ExecResult", "PathEscapeError", "Sandbox", "SandboxProvider", "get_provider"]
