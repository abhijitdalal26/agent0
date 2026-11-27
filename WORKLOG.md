# Work log — continuing session

Running log of what I'm doing, so it's readable in the morning.
(Newest entries at the bottom.)

## Plan

1. **Phase 1** — second flagship demo (`examples/research-brief/`) with no
   image dependency, so a fully-green run lands tonight.
2. **Phase 2** — background retries of the Northwind task for when
   gemini-image quota resets.
3. **Phase 3** — `agent0 setup`/`demo` bootstrap + quickstart docs.
4. **Phase 4** — hardening: tests for tonight's bug fixes, spec gaps.

## Session 2 — Phase 1 in progress

- Built `examples/brief/` — "Agent harness landscape brief" demo task:
  7 contract checks (structure, length via command, self-contained HTML,
  **browser file:// render check**, grounded citations, llm_judge, human
  signoff). New `harness-notes` knowledge source (4 docs, 8 chunks ingested).
- Browser check now supports `config.path` → resolves the workspace artifact
  to a `file://` URL (works under Docker sandbox too via `files.root`).
- `agent0 demo` command: schema + ingest all sources + run example task
  (`--setup-only` verified live).
- Brief task attempts so far: deterministic checks all pass; `renders`
  passes with real Chromium. `facts` (grounded) is the remaining gate —
  executor keeps adding recommendation claims the sources don't state;
  tightened the task prompt to mark advice as opinion.

## Phase 1 COMPLETE — first fully-green flagship run

Run `1ebe12f68b924d90a93cdf8a4ce0088c` (task `529cd81a…`, "Agent harness
landscape brief") **succeeded** at $0.0035:

- structure / length / self-contained-HTML artifact checks: pass
- `renders`: real headless Chromium opened `report.html` via file:// — pass
- `facts` (grounded): 16 claims verified against harness-notes sources — pass
- `quality` (llm_judge): 4/5 — pass
- `signoff` (human): run paused at `waiting_approval`, approved via
  `POST /approvals/{id}` → succeeded
- `/verify` → `ok: true` (23 chained events), `/receipt` signed bundle OK

Also fixed en route: tool OSErrors (bogus paths like citation-ids) now
return error text instead of killing the attempt (`714a4b3`), and a
Windows mojibake in the task prompt.

## Phase 4 progress

- Budget semantics confirmed: agent `budget` is a per-field ceiling
  (`effective_budget` = stricter of task/agent) — HANDOFF flag resolved.
- Windows pipe warning already fixed earlier (`_close_pipes` in local.py).
- **Temporal path verified live**: `temporal server start-dev` +
  `AGENT0_ORCHESTRATOR=temporal agent0 worker` + `serve`; a task dispatched
  got `temporal_workflow_id=agent0-run-…`, the worker executed the
  workflow, hit the expected Groq 429, and Temporal's retry policy kept it
  `executing`. Durable path works end-to-end.
- Integration-test DB isolation confirmed already correct (env-gated).

- `docker build -t agent0:latest .` succeeds; image runs `agent0 --help`
  clean (non-root user, uv-managed venv, healthcheck on /healthz).
- `DEMO.md` added: 3-minute pitch script (verify-trail hook, live task,
  honest-failure beat, receipts, numbers to quote).

## Phase 4 (cont.) — cooldowns + third demo + SQL tool fix

- **Rate-limit cooldowns** (`models/cooldown.py`): every 429 now puts the
  profile into an exponential-backoff cooldown (60s → 30min cap, honors the
  provider's `retry_after`); `Router.rank` sinks cooling profiles so retries
  stop re-picking dead quota. Chat calls via a `WrapperModel`, media calls
  (image/TTS/STT/embed) via `_run`. `/router/preview` shows "cooled down: …".
- **Third demo — SQL grounding** (`examples/analytics/`): deterministic
  288-order sales dataset in `analytics.*`, `optional: true` sql source
  (`AGENT0_SALES_DSN`), Q3 report task whose grounded check verifies every
  number against cited `sql:sales:` records. Verified live: agent queried
  the DB and produced real source_ids.
- **Bug found live**: `query_sql` DB errors (e.g. UndefinedTable) killed the
  attempt instead of reaching the model as feedback — `psycopg.Error` added
  to `_tool_errors_to_text`, plus a test. `query_sql` docstring now says
  Postgres/information_schema.
- API restarted twice to load cooldown + sales source; zombie Temporal test
  run stopped.
- Retry loops running: `/tmp/northwind-retry.log`, `/tmp/analytics-retry.log`.
