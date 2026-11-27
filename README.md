# agent0

A general-purpose, multi-model agent harness that **completes tasks and verifies the work**.

- **Any model, any kind**: chat, vision, image generation, voice (TTS), speech-to-text, embeddings. Add a provider as one entry in `config/models.yaml`; the router picks the best available model for each capability, and the judge always comes from a different provider than the worker.
- **Plan → execute → verify → retry**: a task is done only when its checks pass. Cheap deterministic checks run first (command, artifact, HTTP, and real-browser checks via Playwright); an LLM judge runs only when a check needs it.
- **Tamper-evident audit trail**: every run's event log is hash-chained; `GET /runs/{id}/verify` (or the "Verify trail" button in the dashboard) proves no event was altered after the fact.
- **Grounded answers**: agents read connected databases (read-only) and documents, cite `[src:<id>]`, and the `grounded` check verifies every claim.
- **Approvals**: risky tool calls and outward-facing results wait for a human (Telegram buttons, dashboard or terminal).
- **Memory** in Postgres: instructions, past runs, and learned facts that are expired, never deleted.
- **Extensions**: skills (`SKILL.md`, loaded on demand), MCP servers, plugins.
- **Runs locally or in the cloud**: in-process for development, Temporal for durable runs that survive restarts.
- **Dashboard API**: REST + SSE, encrypted API-key storage. Frontend spec: [docs/dashboard-spec.md](docs/dashboard-spec.md).

Architecture: [docs/architecture.md](docs/architecture.md).

## Quick start (local, no Docker)

```bash
uv sync
cp .env.example .env              # add GROQ_API_KEY and GEMINI_API_KEY
uv run agent0 models              # shows which models are ready
uv run agent0 doctor              # checks DB, keys, sandbox and browser checks end-to-end
uv run agent0 demo                # one-command demo: schema + knowledge ingest + example task
uv run agent0 run "Write a Python script primes.py that prints the first 20 primes, with a test" --sandbox local
```

`--sandbox local` runs commands directly on your machine and is for development only. Use Docker for real work.

## Full stack (Postgres + API + Telegram)

```bash
docker compose -f infra/docker-compose.yml up -d     # Postgres + pgvector
uv run agent0 secrets-keygen                          # put the output in AGENT0_SECRET_KEY
uv run agent0 db-init
uv run agent0 serve                                   # API on :8000, Telegram bot if a token is set
```

Set in `.env`:

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY`, `GEMINI_API_KEY` | Providers. These can also be set from the dashboard, where they are stored encrypted |
| `AGENT0_API_KEY` | Bearer token the dashboard uses to call the API |
| `AGENT0_SECRET_KEY` | Fernet key that encrypts API keys stored from the dashboard |
| `AGENT0_TELEGRAM_BOT_TOKEN` | From @BotFather |
| `AGENT0_TELEGRAM_ALLOWED_USERS` | JSON list of your Telegram user ids or @usernames |
| `AGENT0_SANDBOX` | `docker` (default) or `local` |
| `AGENT0_ORCHESTRATOR` | `local` (default) or `temporal` |
| `AGENT0_DAILY_BUDGET_USD` | Optional daily spend cap across all runs |

Schedules (`/schedules` in the dashboard or `POST /schedules`) run prompts on a cron expression — `next_run` is computed and shown before saving.

Browser-based verification checks need the optional extra:

```bash
uv sync --extra browser && uv run playwright install chromium
```

In Telegram: `/task <what to do>`, `/status`, `/stop <run id>`. Approvals arrive as buttons.

## Dashboard

```bash
cd dashboard && pnpm install
cp .env.example .env.local      # AGENT0_API_URL, AGENT0_API_KEY, DASHBOARD_PASSWORD
pnpm dev                        # http://localhost:3000, log in with DASHBOARD_PASSWORD
AGENT0_MOCK=1 DASHBOARD_PASSWORD=dev pnpm dev   # UI only, fake data, no backend
```

The browser only talks to the dashboard's own server. That server attaches the API key, so neither the key nor the backend URL reaches the browser. Provider keys entered on **Settings → Keys** are encrypted in Postgres and only ever shown as `••••last4`.

## Cloud deploy

See [docs/deploy.md](docs/deploy.md). It covers one VM running Postgres, Temporal, the API and worker, plus Caddy for HTTPS, with E2B sandboxes and the dashboard on Vercel.

## Durable runs (Temporal)

```bash
temporal server start-dev                       # or point AGENT0_TEMPORAL_ADDRESS at your server
AGENT0_ORCHESTRATOR=temporal uv run agent0 serve
AGENT0_ORCHESTRATOR=temporal uv run agent0 worker
```

Kill the worker in the middle of a run and start it again: the run continues from the last finished step.

## Demo: compliant ad creative (fictional brand)

```bash
uv run agent0 ingest northwind                            # index the brand docs once
uv run agent0 run --task-file examples/northwind/ad-task.json
```

The run writes 3 ad variants and a hero image using only the facts in `examples/northwind/docs`. It then checks four things:
- banned claims and required disclaimers, with deterministic regex checks
- the image size
- that every product fact is cited from the docs
- brand voice, graded by a judge model

Finally it waits for your approval. Failed checks go back to the agent as feedback for a retry.

## Demo: SQL-grounded analytics

```bash
psql "$AGENT0_DATABASE_URL" -f examples/analytics/seed.sql   # once: 288-order demo dataset
# set AGENT0_SALES_DSN=postgresql://agent0:agent0@127.0.0.1:5434/agent0 in .env
uv run agent0 demo analytics
```

The agent discovers the schema, runs read-only `SELECT`s through the guarded
`query_sql` tool, and must cite every figure as `[src:sql:sales:…]`. The
`grounded` check then verifies each number against the actual query result —
a report with an invented total fails. Knowledge sources may be marked
`optional: true` so a missing DSN skips them instead of blocking startup.

Rate-limited providers are demoted automatically: a profile that returns 429
enters a cooldown (exponential backoff, honors `retry_after`) and the router
ranks it last until it expires, so retries stop hammering dead quota.

## Development

```bash
uv run pytest                 # unit tests, no network or keys
uv run pytest -m integration  # needs Postgres/Docker/Temporal test server
uv run ruff check . && uv run ruff format .
```

See [AGENTS.md](AGENTS.md) for the conventions.
