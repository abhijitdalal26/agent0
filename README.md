# agent0

A general-purpose, multi-model agent harness that **completes tasks and verifies the work**.

- **Any model, any kind**: chat, vision, image generation, voice (TTS), speech-to-text, embeddings. Add a provider as one entry in `config/models.yaml`; the router picks the best available model for each capability, and the judge always comes from a different provider than the worker.
- **Plan → execute → verify → retry**: a task is done only when its checks pass. Cheap deterministic checks run first; an LLM judge runs only when a check needs it.
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

In Telegram: `/task <what to do>`, `/status`, `/stop <run id>`. Approvals arrive as buttons.

## Durable runs (Temporal)

```bash
temporal server start-dev                       # or point AGENT0_TEMPORAL_ADDRESS at your server
AGENT0_ORCHESTRATOR=temporal uv run agent0 serve
AGENT0_ORCHESTRATOR=temporal uv run agent0 worker
```

Kill the worker in the middle of a run and start it again: the run continues from the last finished step.

## Demo: compliant ad creative (fictional brand)

```bash
uv run agent0 run --task-file examples/northwind/ad-task.json
```

The run writes 3 ad variants and a hero image using only the facts in `examples/northwind/docs`. It then checks four things:
- banned claims and required disclaimers, with deterministic regex checks
- the image size
- that every product fact is cited from the docs
- brand voice, graded by a judge model

Finally it waits for your approval. Failed checks go back to the agent as feedback for a retry.

## Development

```bash
uv run pytest                 # unit tests, no network or keys
uv run pytest -m integration  # needs Postgres/Docker/Temporal test server
uv run ruff check . && uv run ruff format .
```

See [AGENTS.md](AGENTS.md) for the conventions.
