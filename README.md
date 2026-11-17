# agent0

A general-purpose, multi-model agent harness that **completes tasks and verifies the work**.

- Any model, any provider: switch per task, automatic fallback.
- Plan → execute → verify → retry. A task is done only when its checks pass.
- Grounded answers: agents read connected databases and documents, cite sources, and the verifier checks every claim.
- Runs locally or in the cloud. Send tasks and get results over Telegram.
- Durable runs (Temporal), full audit log, budgets and permission levels per tool.

Status: **design phase**. No code yet.

- Architecture & stack: [docs/architecture.md](docs/architecture.md)
- Dashboard spec (frontend contract): [docs/dashboard-spec.md](docs/dashboard-spec.md)

Stack: Python 3.13 · Pydantic AI · Temporal · Postgres + pgvector · FastAPI · Docker / E2B sandboxes · Langfuse · Telegram.
