# Demo script — agent0

A 3-minute tour for a technical audience. Everything below runs against the
local stack; no slides needed.

## 0. Setup (once)

```bash
docker compose -f infra/docker-compose.yml up -d
uv sync
uv run agent0 demo --setup-only     # schema + ingest northwind + harness-notes
uv run agent0 serve --port 8100     # API
cd dashboard && pnpm dev            # UI on :3000
```

## 1. The hook — "it doesn't trust itself"

Open the dashboard → **Runs** → the succeeded "Agent harness landscape
brief" run. Point out:

- The task went plan → execute → verify → **human approval** → succeeded.
- 7 checks: artifact structure, word count, self-contained HTML, a **real
  headless-Chromium render** of `report.html`, grounded facts checked
  against source docs, an LLM quality judge, and a human signoff.
- Click **Verify trail**: every event is hash-chained; the chain recomputes
  clean. Click **Receipt**: a signed audit bundle you could hand to an
  auditor. *No other agent harness ships a tamper-evident run receipt.*

## 2. Live task — watch it think

Dashboard → **Tasks** → new task:

> "Research the three most-cited agent harness papers in our knowledge base
> and write `survey.md` with a comparison table and citations."

Hit run, then open the run page: the SSE timeline streams plan steps, tool
calls (`knowledge_search`, `read_file`, `write_file`), token/cost meter, and
check verdicts as they land.

## 3. The failure that proves the point

Show a failed Northwind attempt (or trigger one): the executor once wrote an
empty `hero.png` when the image API was quota-limited. The artifact check
rejected it — **"not a readable image"** — and the run failed honestly
instead of claiming success. Verification is not a vibe; it's checks.

## 4. The receipts

- `GET /runs/{id}/verify` → `{"ok": true, ...}` — recomputes the hash chain.
- `GET /runs/{id}/receipt` → HMAC-signed bundle (run, spec, verdicts, events).
- `agent0 demo` reproduces the flagship run in one command.

## Numbers to quote

- Flagship brief run: **$0.0035**, ~4 minutes, 7/7 checks.
- 337 unit tests, ruff + pyright clean, dashboard typecheck clean.
- Planner/executor/judge on separate model providers; the judge can never be
  the same model that wrote the work.
