from __future__ import annotations

from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from agent0.config import Settings, get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def create_pool(
    settings: Settings | None = None, *, min_size: int = 1, max_size: int = 10
) -> AsyncConnectionPool:
    settings = settings or get_settings()
    pool = AsyncConnectionPool(
        settings.database_url,
        min_size=min_size,
        max_size=max_size,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True)
    return pool


async def close_pool(pool: AsyncConnectionPool) -> None:
    await pool.close()


async def apply_schema(pool: AsyncConnectionPool) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    async with pool.connection() as conn:
        # Concurrent starters (API + worker) would otherwise race on the IF NOT EXISTS DDL.
        await conn.execute("SELECT pg_advisory_xact_lock(727274)")
        await conn.execute(sql)  # type: ignore[arg-type]
