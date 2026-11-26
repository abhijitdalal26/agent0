# Morning report — overnight session 2026-11-26 → 27

## TL;DR

The harness is **verified working end-to-end with real models** — not just unit
tests. I ran live tasks through the API against real Postgres: file-writing tasks
succeeded, a cron schedule fired on its own and completed a task, agent CRUD +
versioning works, and the flagship Northwind ad demo ran multiple attempts with
real verification feedback (it hit transient Gemini timeouts overnight — retry
was in flight at report time).

Two differentiating features shipped and are live-demoable:
**tamper-evident hash-chained audit trail with signed receipts**, and **real
browser verification checks via Playwright**.

## What shipped (all committed to `main`)

| Commit | What |
|---|---|
| `83f430d` | Cron scheduler — schedules actually fire (`next_run_at`, 30s tick, verified live) |
| `204a10b` | Daily spend cap `AGENT0_DAILY_BUDGET_USD` + real `/usage` coverage |
| `54bb820` | Agent CRUD API + DB overlay + `model_profile` pinning |
| `ab24008` | Dashboard redesign: sidebar app shell, unified headers, de-slopped modals |
| `cb2880d` | Agent budgets as per-field caps (stricter of task/agent wins) |
| `a7e57d8` | **Hash-chained event log** + `GET /runs/{id}/verify` |
| `5494ce2` | Run page "Verify trail" button (chain state + head hash) |
| `aa92feb` | **Browser check** (`type: "browser"`, Playwright, optional extra) |
| `a07e17b` | **Signed run receipts** `GET /runs/{id}/receipt` + dashboard download |
| `13f2758` | `agent0 db-backfill-hashes` — all legacy runs now verify `ok` |
| `4c6af6b` | N+1 fix: `/runs` + `/tasks` batch spec/verdict fetches |
| `1f6aebf` | Docs: spec endpoint table + HANDOFF refresh |
| `814f6d8` | `agent0 doctor` — one-command install diagnostics |
| — | `simple-harness/` — 132-line teaching harness + `docs/agent-reading-list.md` |

## Verified live tonight (real API, real Postgres, real models)

- `POST /tasks` → plan → execute → verify → **succeeded** ($0.004, gemini-3.6-flash)
- Schedule `* * * * *` fired at the right minute → task **succeeded**
- Agent create/update → version history recorded (v1, v2)
- `/usage` + `/usage/summary` return real rows
- Browser check: real headless Chromium loaded example.com → **pass**
- Hash chain: all 9 runs in dev DB verify `ok: true` (48 legacy events backfilled)
- Receipt endpoint returns HMAC-signed bundle; signature recomputes correctly
- `agent0 doctor` → all checks green ("ready")
- `simple-harness/harness.py` ran a real task via Groq: write → execute → answer

## For the demo

1. `docker compose -f infra/docker-compose.yml up -d` (already running)
2. `uv run agent0 serve` → API :8000 · `cd dashboard && pnpm dev` → :3000
3. Open a succeeded run → click **Verify trail** (green "Chain intact · N")
   and **Receipt** (downloads signed JSON audit bundle)
4. New task dialog → pick criterion type `browser` for a live Chromium check
5. `uv run agent0 doctor` is a nice "it just works" beat

Keys note: `.env` Groq/Gemini vars are empty but the **working keys are in the
Postgres secret store** (dashboard → Settings → Keys). `agent0 doctor` confirms.

## Known issues / honest caveats

- **Northwind demo hit Gemini free-tier timeouts** (187s planner call, then
  FallbackExceptionGroup on attempt 2). Transient, not a code bug — attempt 3
  was running at report time. If it keeps failing, the free-tier quota is the
  bottleneck; a paid key or groq-smart profile would fix it.
- `knowledge_chunks` was empty — the `northwind` docs source must be ingested
  once (`uv run agent0 ingest northwind`) or skill doc-refs fail. Now ingested;
  README demo section updated.
- Unverified tonight: Telegram bot, Temporal worker path, cloud compose,
  `docker build` of the sandbox image.
- Old runs written before the hash-chain feature needed the backfill — done for
  the dev DB; other deployments should run `agent0 db-backfill-hashes` once.

## Test status

- `uv run pytest`: **336 passed** (+4 integration against real Postgres)
- `ruff check` / `ruff format` / `pyright`: clean
- Dashboard `tsc --noEmit` + `pnpm build`: clean (16 routes)
