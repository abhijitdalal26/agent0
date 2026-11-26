# Handoff — 2026-11-17

Read this first after a restart, then `AGENTS.md` and `docs/architecture.md`.

## What agent0 is

A general multi-model agent harness: plan → execute → verify → retry, Postgres memory, approvals, Telegram, dashboard. It is for an internship application: a 20–60 min single-take video of building with AI, plus a CV. The deadline is **Sat 2026-11-28**. The demo uses the fictional brand "Northwind Health", so don't put the real company name in the repo. Repo: https://github.com/abhijitdalal26/agent0 (public).

## State: verified end-to-end against real models (2026-11-26 night session)

- `uv run pytest`: 335 passed (+ integration). Ruff, pyright, dashboard `tsc`/`pnpm build` clean.
- **Real Groq/Gemini calls verified**: the keys are not in `.env` but ARE in the Postgres secret store (added via Dashboard → Settings → Keys earlier). Live runs succeeded: file-writing task, cron-scheduled task, and a browser-check task.
- New since the last handoff:
  - Agent CRUD API (`GET/POST/PUT /agents`, `/agents/{name}/versions`) with DB overlay + `model_profile` pinning.
  - Cron `Scheduler` — schedules actually fire (`next_run_at` column, `agent0 serve` runs it).
  - Daily spend cap via `AGENT0_DAILY_BUDGET_USD`.
  - **Tamper-evident audit trail**: every event is hash-chained (`prev_hash`/`hash`); `GET /runs/{id}/verify` recomputes it; `GET /runs/{id}/receipt` returns an HMAC-signed audit bundle; dashboard run page has "Verify trail" + "Receipt" buttons. `agent0 db-backfill-hashes` chained pre-existing rows — all dev runs verify `ok`.
  - **Browser check** (`type: "browser"`): real headless Chromium via Playwright (optional extra `uv sync --extra browser` + `playwright install chromium`). On Windows it runs on a dedicated thread because the server's SelectorEventLoop can't host Playwright's pipe transport.
  - Dashboard redesign: sidebar `AppShell`, unified `PageHeader`, de-slopped modals.
- Still unverified: Telegram, Temporal worker path, cloud compose, `docker build` of the image.

## Environment facts (Windows)

- Docker Postgres runs on **port 5434** because native Postgres services already use 5432 and 5433. Use `127.0.0.1`, not `localhost`: `localhost` causes psycopg_pool timeouts.
- psycopg async needs the SelectorEventLoop. The CLI's `_run_async` and `serve` handle this, and so does `tests/conftest.py`. That loop can't spawn subprocesses, so `LocalSandbox` runs `Popen` in a thread.
- The user's own servers run on ports 3000 and 8000. Don't kill them; test on 3100/8100.
- Low RAM: background builds/servers get killed. Don't restart heavy processes unless asked.

## Secrets and config locations (never paste values in chat)

- `.env` (git-ignored) holds:
  - `GROQ_API_KEY` and `GEMINI_API_KEY`, which are **empty in `.env` — the working keys live in the Postgres secret store** (dashboard → Settings → Keys). `resolve_secret` falls through env → secret store.
  - `AGENT0_API_KEY`, `AGENT0_SECRET_KEY` and `AGENT0_DATABASE_URL`
  - Telegram token and allowed users, not set yet
- `dashboard/.env.local` (git-ignored) holds `AGENT0_API_URL=http://127.0.0.1:8000`, `AGENT0_API_KEY`, `DASHBOARD_PASSWORD` (the login) and `DASHBOARD_SESSION_SECRET`. The old file is `.env.local.bak`.
- Provider keys can also be added through Dashboard → Settings → Keys, which stores them Fernet-encrypted in Postgres.

## How to run

```bash
docker compose -f infra/docker-compose.yml up -d
uv run agent0 db-init
uv run agent0 models                      # profiles should say "ready" once keys are set
uv run agent0 run "Write primes.py that prints the first 20 primes, with a test"
uv run agent0 run --task-file examples/northwind/ad-task.json   # the demo
uv run agent0 serve                       # API :8000 (+ Telegram if token set)
cd dashboard && pnpm dev                  # :3000, log in with DASHBOARD_PASSWORD
AGENT0_MOCK=1 DASHBOARD_PASSWORD=dev pnpm dev   # UI only, fake data
```

## Next steps (priority order)

1. The user adds the Groq and Gemini keys, then runs `agent0 models`.
2. Do a live smoke run (primes), then the Northwind demo. Fix whatever breaks with the real providers: model ids in `config/models.yaml`, tool calling and image generation.
3. Telegram smoke test: `/task`, the approval buttons and `/status`.
4. Click through the dashboard against the live API during a real run (SSE timeline, approvals, usage).
5. `docker build -t agent0 .` when RAM allows.
6. Optionally do a cloud deploy following `docs/deploy.md`.
7. Rehearse the video flow.

## Known gaps / debt

- Agent edit endpoints return 501. There is no sandbox file browser and no browser check type.
- Temporal durability is per attempt, not per model/tool call. `docs/reference-notes.md` lists the options.
- Temporal connect has no TLS, so Temporal Cloud isn't supported.
- Integration tests write to the main DB. They should use a separate test DB.
- `agents/executor/agent.md` sets `budget.max_steps: 40`, which overrides the task's `max_steps`. Confirm that's intended.
- Windows prints a cosmetic unclosed-pipe warning in `tests/tools/test_tools.py::test_shell_and_events`.

## Conventions (from the user)

- Few comments, and only where needed.
- Don't over-engineer, and don't waste tokens.
- Commit and push after each significant piece of work, using explicit paths and never `git add -A`.
- Give subagents a model that fits their task.
- Never copy code from `_reference/claw-code`.
