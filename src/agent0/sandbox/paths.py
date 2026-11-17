from __future__ import annotations

from pathlib import Path


class PathEscapeError(ValueError):
    pass


class WorkspaceFiles:
    """File access confined to a host directory; `virtual_root` is how the sandbox spells that directory."""

    def __init__(self, root: Path, virtual_root: str | None = None) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.virtual_root = virtual_root

    def resolve(self, path: str) -> Path:
        p = path.replace("\\", "/")
        vr = self.virtual_root
        if vr and (p == vr or p.startswith(vr.rstrip("/") + "/")):
            p = p[len(vr) :].lstrip("/") or "."
        candidate = Path(p)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.root):
            raise PathEscapeError(f"path escapes the workspace: {path}")
        return resolved

    def read(self, path: str) -> bytes:
        return self.resolve(path).read_bytes()

    def write(self, path: str, data: bytes) -> None:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def list(self, path: str = ".") -> list[str]:
        target = self.resolve(path)
        entries = sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        return [e.name + "/" if e.is_dir() else e.name for e in entries]
