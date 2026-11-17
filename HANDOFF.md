# Session handoff — 2026-11-17 (Devin)

State of the environment and what was done while waiting. Read AGENTS.md and docs/architecture.md first.

## Environment status

- `uv sync` — done, venv healthy (106 packages resolved).
- `uv run pytest` — **295 passed, 4 skipped** (unit tests, no network/keys needed).
- `uv run ruff check .` — clean.
- `uv run pyright` — **0 errors** (was 125; all fixed this session — see below).
- `.env` exists but `GROQ_API_KEY` and `GEMINI_API_KEY` are **empty placeholders** — real keys needed before any live `agent0 run` / `agent0 models` shows profiles as ready (cli.py loads `.env` via dotenv; `uv run agent0 models` currently shows every profile "missing").

## Blocked: Docker / Postgres

- Docker Desktop 4.x is installed (`C:\Program Files\Docker`) but **cannot start the engine**: it is configured for the WSL2 backend (`EngineTypeWindows: wsl2` in `%APPDATA%\Docker\settings-store.json`) and **WSL is not installed**.
- OS is **Windows 11 Home** — the Hyper-V backend is not available, so WSL2 is the only option.
- To unblock (needs admin + reboot, user action):
  1. In an elevated PowerShell: `wsl --install`
  2. Reboot, then launch Docker Desktop once so it finishes setup.
  3. `docker compose -f infra/docker-compose.yml up -d` (compose file is ready; pulls `pgvector/pgvector:pg17`, mounts `src/agent0/db/schema.sql`).
- Until then, everything that needs Postgres (`agent0 db-init`, memory facts, `serve` with DB) is unavailable. The local/no-Docker quick start in README still works (`--sandbox local`, `uv run agent0 run ...`).

## Work done this session

- Fixed pyright errors in `src/agent0/sandbox/local.py` (`os.killpg` / `signal.SIGKILL` are POSIX-only symbols; made the kill path platform-safe without changing runtime behavior). Verify: `uv run pytest tests/sandbox/test_local.py -q` and `uv run pyright src/agent0/sandbox/local.py`.
- Fixed ~109 pyright errors in `src/agent0/orchestrator/temporal.py`: `_SHORT`/`_MODEL` kwargs dicts needed `dict[str, Any]` annotations so `workflow.execute_activity(..., **kwargs)` overload resolution works.
- **Real bug fixed** in `src/agent0/orchestrator/steps.py`: `BudgetMeter(budget=budget)` passed a `budget=` kwarg that `BudgetMeter` (a `Budget` subclass) doesn't have — pydantic silently ignored it, so every run used the default budget (max_usd=1.0, max_steps=40, max_minutes=30) regardless of task/agent budget. Now `BudgetMeter(**budget.model_dump())`.
- Added regression test `test_task_budget_reaches_budget_meter` in `tests/orchestrator/test_engine_e2e.py` proving task budget fields reach the meter. Note: `agents/executor/agent.md` sets `budget: {max_steps: 40}` which overrides the task's `max_steps` via `AgentDef.effective_budget` — by design, but worth confirming that's intended (a task cannot lower max_steps below the agent's value).
- Pyright debt fully cleaned: `db/pool.py` now exposes a `PgPool = AsyncConnectionPool[AsyncConnection[DictRow]]` alias so `dict_row` results type correctly (this fixed the TupleRow-vs-dict errors in `db/repos.py`, `memory/pg.py`, `secrets/store.py`, `knowledge/`); `models/media.py` uses `import google.genai as genai` (the `from google import genai` form fails — `google` is a namespace package); `api/errors.py` accepts `Mapping` headers; `serve.py` close() None-checks the channel; `cli.py` prompt fallback.

## Dashboard status

- `dashboard/` is a Next.js 15 + React 19 + Tailwind app, already scaffolded with all spec pages (`activity`, `agents`, `approvals`, `extensions`, `memory`, `models`, `runs/[id]`, `schedules`, `settings`, `tasks`, `usage`) plus an `/api/proxy/[...path]` route and `src/lib/api.ts` client.
- `dashboard/.env.local` has `NEXT_PUBLIC_MOCK=1` — the UI runs entirely on `src/mocks/fixtures.ts` until the flag is removed.
- Verified this session: `pnpm exec tsc --noEmit` clean, `pnpm build` succeeds (14 routes).

## Telegram bot status

- `src/agent0/channels/telegram.py` is feature-complete: `/task`, `/status`, `/stop`, approval inline-keyboard callbacks, photo/audio/document attachments, user allowlist, HTML formatting. Wired in `serve.py` (`status_handler`, `stop_handler`, `wire_notifications`). Unit tests in `tests/channels/test_telegram.py` pass.
- To activate: set `AGENT0_TELEGRAM_BOT_TOKEN` (from @BotFather) and `AGENT0_TELEGRAM_ALLOWED_USERS` (JSON list of ids or @usernames) in `.env`, then `uv run agent0 serve`. Requires Postgres (see below) for runs/approvals persistence.

## Remaining work (in priority order)

1. **Commit pending changes** — 15 modified files + this file, all verified green. Nothing is committed yet.
2. **User-side unblock** (see Docker section): WSL install → reboot → Docker Desktop → compose up → `agent0 secrets-keygen` → `agent0 db-init`.
3. **Keys**: put real `GROQ_API_KEY` / `GEMINI_API_KEY` in `.env`, then `uv run agent0 models` should show profiles ready.
4. **End-to-end smoke test**: `uv run agent0 run "..." --sandbox docker`, then the Northwind demo `uv run agent0 run --task-file examples/northwind/ad-task.json` — exercises the budget fix, verify loop, and approvals.
5. **Telegram smoke test** with a real bot token once Postgres is up.
6. **Dashboard against live API**: remove `NEXT_PUBLIC_MOCK=1` from `dashboard/.env.local`, run `pnpm dev`, click through every page vs `docs/dashboard-spec.md`, fix any wiring gaps (SSE live updates in `api/sse.py`, endpoints in `lib/api.ts` missing server-side, etc.).
7. **Confirm budget semantics**: `agents/executor/agent.md` sets `budget: {max_steps: 40}` which overrides a task's `max_steps` via `AgentDef.effective_budget` — decide if that's intended or if task budgets should be able to tighten agent budgets.

## Known debt for next session

- `tests/tools/test_tools.py::test_shell_and_events` emits a PytestUnraisableExceptionWarning about an unclosed Proactor pipe transport on Windows — cosmetic, but could be cleaned up.
