from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from agent0.db.pool import PgPool
from agent0.knowledge.base import KnowledgeSource
from agent0.knowledge.docs import DocsKnowledgeSource, InMemoryDocsSource
from agent0.knowledge.sql import SqlKnowledgeSource


class KnowledgeConfigError(ValueError):
    pass


def load_sources(
    path: Path | str = "config/knowledge.yaml",
    pool: PgPool | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, KnowledgeSource]:
    """Build sources from YAML. DSNs come from env vars named in the file, never from the file itself.
    Without a pool, docs sources are in-memory (CLI and tests)."""
    path = Path(path)
    if not path.exists():
        return {}
    env = env if env is not None else dict(os.environ)
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent
    sources: dict[str, KnowledgeSource] = {}
    for entry in raw.get("sources") or []:
        name, kind = entry.get("name"), entry.get("kind")
        if not name or name in sources:
            raise KnowledgeConfigError(f"source needs a unique name: {entry!r}")
        if kind == "sql":
            dsn = env.get(entry.get("dsn_env", ""))
            if not dsn:
                raise KnowledgeConfigError(f"source {name!r}: env var {entry.get('dsn_env')!r} is not set")
            sources[name] = SqlKnowledgeSource(
                name,
                dsn,
                timeout_ms=entry.get("timeout_ms", 5000),
                max_rows=entry.get("max_rows", 50),
            )
        elif kind == "docs":
            root = Path(entry.get("path", ""))
            root = root if root.is_absolute() else base.parent / root
            patterns = entry.get("patterns") or ("**/*.md", "**/*.txt")
            if pool is not None:
                sources[name] = DocsKnowledgeSource(name, pool, root, patterns)
            else:
                sources[name] = InMemoryDocsSource(name, root, patterns)
        else:
            raise KnowledgeConfigError(f"source {name!r}: unknown kind {kind!r}")
    return sources
