from __future__ import annotations

from typing import TYPE_CHECKING

from agent0.core.events import event_hash

if TYPE_CHECKING:
    from agent0.db.pool import PgPool


async def backfill_event_hashes(pool: PgPool) -> dict[str, int]:
    """Chain events written before the hash columns existed.

    Runs are processed under the same advisory lock EventRepo.append uses, so a live
    server can keep appending while this runs. Returns counts of runs/events touched.
    """
    async with pool.connection() as conn:
        cur = await conn.execute("SELECT DISTINCT run_id FROM events WHERE hash IS NULL")
        run_ids = [r["run_id"] for r in await cur.fetchall()]

    chained_events = 0
    for run_id in run_ids:
        async with pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (run_id,))
            cur = await conn.execute(
                "SELECT id, seq, type, payload, created_at FROM events"
                " WHERE run_id = %s ORDER BY seq",
                (run_id,),
            )
            rows = await cur.fetchall()
            prev: str | None = None
            for r in rows:
                digest = event_hash(
                    run_id, r["seq"], r["type"], r["payload"], r["created_at"], prev
                )
                await conn.execute(
                    "UPDATE events SET hash = %s, prev_hash = %s WHERE id = %s",
                    (digest, prev, r["id"]),
                )
                prev = digest
            chained_events += len(rows)
    return {"runs": len(run_ids), "events": chained_events}
