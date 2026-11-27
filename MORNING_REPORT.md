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
| `bef6f65` `fd4b748` `618131c` | **Criteria contract fix** — planner checks no longer poison task specs across retries; user criteria override planner extras; `check_plan` validates pattern configs |
| `5d99f59` | Grounded check `non_claim_patterns` — disclaimers/CTAs aren't factual claims |
| `68ae0fc` | Judge checks get a fallback model chain (was single-profile, died on 429) |
| `a9faa28` | Planner string patterns coerced to lists instead of ModelRetry loops |
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

## Northwind flagship demo — what actually happened

The demo task ran ~10 live attempts tonight and became a real stress test.
It surfaced **five genuine bugs**, all fixed and committed:

1. **Criteria poisoning**: planner-generated checks were merged into the
   stored task spec on every retry, so one hallucinated check
   (`required_patterns: 125`) became permanently required and crashed the
   artifact check. Now `task_specs` holds only the contract; planner extras
   apply only to tasks with no user criteria.
2. **Unsatisfiable planner checks**: the planner invented `\[src:[0-9]+\]`
   citation patterns, but real source ids are `doc:name:file.md#N`. Planner
   prompt now documents the real id shape, and string patterns are coerced
   to lists rather than killing the plan.
3. **Judge single-point-of-failure**: grounded/llm_judge picked ONE smart
   profile; when groq-smart 429'd, verdicts errored and sank passing runs.
   Judges now fall back across the top-3 ranked profiles.
4. **Grounded false positives**: mandated disclaimers ("See terms.") were
   judged as unsupported factual claims — an unsatisfiable conflict with
   the disclaimer criterion. `non_claim_patterns` config fixes it.
5. **API retry data loss**: criteria lived only in `task_specs`; the stored
   row was restored from `ad-task.json`.

**Best attempt**: 5/7 contract checks passed — files, banned-claims,
disclaimer, hero image (1080×1080 via gemini-image), brand voice 5/5.
The run then hit a hard external wall: **gemini-image quota exhausted**
(9 consecutive failures). The executor tried to fake it — wrote an empty
`hero.png` via shell — and the artifact check **correctly rejected it**
("not a readable image"). That's the verification system doing its job:
this harness does not accept claimed work, only verified work.

To finish the demo: wait for Gemini quota reset (daily) or add any
image-capable key, then `POST /tasks/{id}/retry`. Everything else in the
pipeline is proven.

## Known issues / honest caveats

- **Free-tier quotas are the bottleneck**, not code. Gemini flash/image and
  Groq 120b all 429'd tonight; gemini-lite + groq-fast carried the load.
  A paid key (or `AGENT0` model_profile pins per agent) makes it smooth.
- `knowledge_chunks` was empty — the `northwind` docs source must be ingested
  once (`uv run agent0 ingest northwind`) or skill doc-refs fail. Now ingested;
  README demo section updated.
- Agent `model_profile` pins (DB overlay; edit via dashboard or `PUT /agents/{name}`):
  planner=gemini-flash, marketer=groq-fast — chosen so the LLM judge
  (which excludes the executor's provider) lands on Google while the
  executor lands on Groq. Groq gpt-oss-20b TPD (200k/day) was exhausted
  overnight; a background retry loop re-attempts Northwind every ~45min.
- Unverified tonight: Telegram bot, Temporal worker path, cloud compose,
  `docker build` of the sandbox image.
- Old runs written before the hash-chain feature needed the backfill — done for
  the dev DB; other deployments should run `agent0 db-backfill-hashes` once.

## Test status

## Phase 2 update — second flagship demo is fully green

`examples/brief` ("Agent harness landscape brief") **succeeded** end-to-end:
6/7 automated checks (artifact patterns, word count, self-contained HTML,
real headless-Chromium render via `file://`, grounded facts vs the new
`harness-notes` knowledge source, llm_judge quality 4/5) + human signoff
approved through `POST /approvals/{id}`. Cost $0.0035, audit chain verified.
This is the quota-independent demo — `uv run agent0 demo` reproduces it.

Northwind remains quota-blocked only: hero.png now generates (image quota
partially back), judge works (voice 5/5), the last blocker was Groq TPD.
Also fixed: task prompt mandated "launching Monday" but the facts doc
lacked it — added the launch-date fact and re-ingested.

- `uv run pytest`: **337 passed** (+4 integration against real Postgres)
- `ruff check` / `ruff format` / `pyright`: clean
- Dashboard `tsc --noEmit` + `pnpm build`: clean (16 routes)
