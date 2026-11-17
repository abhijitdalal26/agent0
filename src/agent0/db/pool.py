from __future__ import annotations

from pathlib import Path

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from agent0.config import Settings, get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

PgPool = AsyncConnectionPool[AsyncConnection[DictRow]]


async def create_pool(settings: Settings | None = None, *, min_size: int = 1, max_size: int = 10) -> PgPool:
    settings = settings or get_settings()
    # row_factory is invisible to the pool's generics; the explicit specialization pins the row type.
    pool = AsyncConnectionPool[AsyncConnection[DictRow]](
        settings.database_url,
        min_size=min_size,
        max_size=max_size,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True)
    return pool


async def close_pool(pool: PgPool) -> None:
    await pool.close()


async def apply_schema(pool: PgPool) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.connection() as conn:
        # Concurrent starters (API + worker) would otherwise race on the IF NOT EXISTS DDL.
        await conn.execute("SELECT pg_advisory_xact_lock(727274)")
        await conn.execute(sql)  # type: ignore[arg-type]
