from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import psycopg
from psycopg.rows import dict_row

from agent0.knowledge.base import SourceRecord

Executor = Callable[[str, Sequence[Any]], Awaitable[list[dict[str, Any]]]]

_FORBIDDEN_WORDS = frozenset(
    """insert update delete drop alter create truncate grant revoke copy call do execute prepare deallocate
    merge vacuum reindex cluster refresh listen notify unlisten set reset lock begin commit
    rollback savepoint declare fetch discard into
    pg_sleep pg_read_file pg_read_binary_file pg_ls_dir pg_stat_file pg_terminate_backend pg_cancel_backend
    pg_reload_conf set_config lo_import lo_export lo_unlink dblink dblink_exec nextval setval
    pg_advisory_lock pg_advisory_xact_lock pg_notify query_to_xml""".split()
)
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


class SqlGuardError(ValueError):
    pass


def _strip_literals(sql: str) -> str:
    """Blank out '...' strings and "..." identifiers; reject constructs whose quoting rules are tricky."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in "'\"":
            prev = sql[i - 1] if i else " "
            if ch == "'" and (prev in "eEuU&" and (i < 2 or not re.match(r"\w", sql[i - 2]))):
                raise SqlGuardError("escape-prefixed string literals are not allowed")
            j = i + 1
            while True:
                if j >= n:
                    raise SqlGuardError("unterminated quoted string")
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:
                        j += 2
                        continue
                    break
                j += 1
            out.append(" " + ch + ch + " ")
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def validate_select(sql: str) -> str:
    """Return the statement unchanged if it is a single read-only SELECT/WITH, else raise SqlGuardError."""
    if not isinstance(sql, str) or not sql.strip():
        raise SqlGuardError("empty statement")
    if "\x00" in sql or "\\" in sql:
        raise SqlGuardError("control or backslash characters are not allowed")
    skeleton = _strip_literals(sql)
    if "--" in skeleton or "/*" in skeleton or "*/" in skeleton:
        raise SqlGuardError("comments are not allowed")
    if re.search(r"\$[A-Za-z_0-9]*\$", skeleton):
        raise SqlGuardError("dollar-quoted strings are not allowed")
    body = skeleton.strip()
    if body.endswith(";"):
        body = body[:-1].rstrip()
    if ";" in body:
        raise SqlGuardError("multiple statements are not allowed")
    words = [w.lower() for w in _WORD.findall(body)]
    if not words or words[0] not in ("select", "with"):
        raise SqlGuardError("only SELECT or WITH statements are allowed")
    bad = sorted(set(words) & _FORBIDDEN_WORDS)
    if bad:
        raise SqlGuardError(f"forbidden keyword(s): {', '.join(bad)}")
    return sql


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def record_id(name: str, sql: str, params: Sequence[Any], row: dict[str, Any]) -> str:
    material = json.dumps([sql, _jsonable(list(params)), _jsonable(row)], sort_keys=True, ensure_ascii=True)
    return f"sql:{name}:{hashlib.sha256(material.encode()).hexdigest()[:16]}"


class SqlKnowledgeSource:
    kind = "sql"

    def __init__(
        self,
        name: str,
        dsn: str | None = None,
        *,
        timeout_ms: int = 5000,
        max_rows: int = 50,
        executor: Executor | None = None,
        cache_size: int = 2000,
    ) -> None:
        if dsn is None and executor is None:
            raise ValueError("dsn or executor required")
        self.name = name
        self.dsn = dsn
        self.timeout_ms = int(timeout_ms)
        self.max_rows = max_rows
        self._executor = executor or self._run_pg
        self._cache: OrderedDict[str, SourceRecord] = OrderedDict()
        self._cache_size = cache_size

    async def _run_pg(self, sql: str, params: Sequence[Any]) -> list[dict[str, Any]]:
        async with await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row) as conn:  # type: ignore[arg-type]
            await conn.set_read_only(True)
            async with conn.transaction():
                await conn.execute(f"SET LOCAL statement_timeout = {self.timeout_ms}")  # type: ignore
                cur = await conn.execute(sql, params or None)  # type: ignore[arg-type]
                return await cur.fetchmany(self.max_rows)  # type: ignore[return-value]

    async def query(self, sql: str, params: Sequence[Any] = ()) -> list[SourceRecord]:
        validate_select(sql)
        rows = await self._executor(sql, params)
        records = []
        for row in rows[: self.max_rows]:
            clean = _jsonable(row)
            record = SourceRecord(
                source_id=record_id(self.name, sql, params, clean),
                source=self.name,
                content=json.dumps(clean, sort_keys=True, ensure_ascii=False),
                metadata={"sql": sql, "params": _jsonable(list(params)), "row": clean},
            )
            self._remember(record)
            records.append(record)
        return records

    def _remember(self, record: SourceRecord) -> None:
        self._cache[record.source_id] = record
        self._cache.move_to_end(record.source_id)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def search(self, query: str, limit: int = 5) -> list[SourceRecord]:
        return (await self.query(query))[:limit]

    async def get(self, source_id: str) -> SourceRecord | None:
        """Only records returned earlier by this instance; use `rerun` to re-check one against live data."""
        return self._cache.get(source_id)

    async def rerun(self, record: SourceRecord) -> SourceRecord | None:
        sql = record.metadata.get("sql")
        if not isinstance(sql, str):
            return None
        for fresh in await self.query(sql, record.metadata.get("params") or []):
            if fresh.source_id == record.source_id:
                return fresh
        return None
