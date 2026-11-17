from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from pathlib import Path

from psycopg.types.json import Jsonb

from agent0.db.fts import or_tsquery
from agent0.db.pool import PgPool
from agent0.knowledge.base import SourceRecord
from agent0.memory.fusion import rank_by_keywords

DEFAULT_PATTERNS = ("**/*.md", "**/*.txt")
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def chunk_text(text: str, max_chars: int = 1200) -> list[tuple[str, str]]:
    """Split on markdown headings, then pack paragraphs up to max_chars. Returns (heading, chunk) pairs."""
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            sections.append((m.group(2), [line]))
        else:
            sections[-1][1].append(line)

    chunks: list[tuple[str, str]] = []
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        current = ""
        for para in re.split(r"\n\s*\n", body):
            para = para.strip()
            while len(para) > max_chars:
                cut = para.rfind(" ", 0, max_chars)
                cut = cut if cut > max_chars // 2 else max_chars
                if current:
                    chunks.append((heading, current))
                    current = ""
                chunks.append((heading, para[:cut].strip()))
                para = para[cut:].strip()
            if not para:
                continue
            if current and len(current) + len(para) + 2 > max_chars:
                chunks.append((heading, current))
                current = para
            else:
                current = f"{current}\n\n{para}" if current else para
        if current:
            chunks.append((heading, current))
    return chunks


def chunk_id(source: str, file: str, n: int) -> str:
    return f"doc:{source}:{file}#{n}"


def build_records(
    source: str,
    root: Path,
    patterns: Sequence[str] = DEFAULT_PATTERNS,
    max_chars: int = 1200,
) -> dict[str, list[SourceRecord]]:
    """Map relative file path -> its chunks; ids depend only on source, relative path and chunk order."""
    files: dict[str, list[SourceRecord]] = {}
    paths = sorted({p for pat in patterns for p in root.glob(pat) if p.is_file()})
    for path in paths:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        files[rel] = [
            SourceRecord(
                source_id=chunk_id(source, rel, n),
                source=source,
                content=chunk,
                metadata={
                    "file": rel,
                    "heading": heading,
                    "chunk": n,
                    "content_hash": hashlib.sha256(chunk.encode()).hexdigest()[:16],
                },
            )
            for n, (heading, chunk) in enumerate(chunk_text(text, max_chars))
        ]
    return files


class DocsKnowledgeSource:
    kind = "docs"

    def __init__(
        self,
        name: str,
        pool: PgPool,
        root: Path | None = None,
        patterns: Sequence[str] = DEFAULT_PATTERNS,
        max_chars: int = 1200,
    ) -> None:
        self.name = name
        self.pool = pool
        self.root = root
        self.patterns = tuple(patterns)
        self.max_chars = max_chars

    async def ingest(self, root: Path | None = None) -> int:
        root = root or self.root
        if root is None:
            raise ValueError("no root directory to ingest")
        files = build_records(self.name, root, self.patterns, self.max_chars)
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO knowledge_sources (name, kind, config) VALUES (%s, 'docs', %s)"
                " ON CONFLICT (name) DO UPDATE SET config = EXCLUDED.config",
                (self.name, Jsonb({"root": str(root), "patterns": list(self.patterns)})),
            )
            keep = [r.source_id for recs in files.values() for r in recs]
            # Stale chunks (file deleted or shrunk) go; surviving ids are upserted in place.
            await conn.execute(
                "DELETE FROM knowledge_chunks WHERE source = %s AND NOT (id = ANY(%s))", (self.name, keep)
            )
            for recs in files.values():
                for r in recs:
                    await conn.execute(
                        "INSERT INTO knowledge_chunks (id, source, content, metadata) VALUES (%s,%s,%s,%s)"
                        " ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content,"
                        " metadata = EXCLUDED.metadata",
                        (r.source_id, self.name, r.content, Jsonb(r.metadata)),
                    )
        return len(keep)

    async def search(self, query: str, limit: int = 5) -> list[SourceRecord]:
        tsq = or_tsquery(query)
        if not tsq:
            return []
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id AS source_id, source, content, metadata FROM knowledge_chunks"
                " WHERE source = %(s)s AND tsv @@ to_tsquery('english', %(q)s)"
                " ORDER BY ts_rank_cd(tsv, to_tsquery('english', %(q)s)) DESC, id LIMIT %(n)s",
                {"s": self.name, "q": tsq, "n": limit},
            )
            return [SourceRecord.model_validate(r) for r in await cur.fetchall()]

    async def get(self, source_id: str) -> SourceRecord | None:
        async with self.pool.connection() as conn:
            cur = await conn.execute(
                "SELECT id AS source_id, source, content, metadata FROM knowledge_chunks"
                " WHERE id = %s AND source = %s",
                (source_id, self.name),
            )
            row = await cur.fetchone()
            return SourceRecord.model_validate(row) if row else None


class InMemoryDocsSource:
    kind = "docs"

    def __init__(
        self,
        name: str,
        root: Path | None = None,
        patterns: Sequence[str] = DEFAULT_PATTERNS,
        max_chars: int = 1200,
    ) -> None:
        self.name = name
        self.root = root
        self.patterns = tuple(patterns)
        self.max_chars = max_chars
        self.chunks: dict[str, SourceRecord] = {}

    async def ingest(self, root: Path | None = None) -> int:
        root = root or self.root
        if root is None:
            raise ValueError("no root directory to ingest")
        files = build_records(self.name, root, self.patterns, self.max_chars)
        self.chunks = {r.source_id: r for recs in files.values() for r in recs}
        return len(self.chunks)

    async def search(self, query: str, limit: int = 5) -> list[SourceRecord]:
        return rank_by_keywords(query, self.chunks.values(), lambda r: r.content)[:limit]

    async def get(self, source_id: str) -> SourceRecord | None:
        return self.chunks.get(source_id)
