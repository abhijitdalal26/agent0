# Harness — Architecture & Tech Stack

Status: draft for review · 2026-11-17

## 1. What we are building

A general-purpose agent harness that:

1. Runs any model from any provider (bring your own API key, switch per task, fall back automatically).
2. **Completes** a task *and* **verifies** it — the run is not "done" until checks pass.
3. Runs locally (CLI) and in the cloud (laptop closed), with the same code.
4. Talks to you on the channels you already use (Telegram first, Slack/Discord/email later): send tasks, get progress, approve risky steps, receive results.
5. Exposes everything to a dashboard (spec in `dashboard-spec.md`; built separately).

Target users: us first, then any small team that needs long-running agents for creative, analytics or ops work.

Design rule: **don't over-engineer, don't waste tokens.** Free deterministic code first; an LLM call only where it earns its cost.

Non-goals for v1: multi-tenant SaaS billing, voice, desktop/mobile apps, a visual workflow builder.

## 1a. Product focus: who this is shaped for

The sharpest use case is a fast-growing, regulated business such as a telehealth company: small team, heavy agent use, and **regulated claims** (HIPAA, FTC health-claims rules, required disclaimers). Such teams typically run three agent families:

| Workload | Our "pack" (built on the general harness) | What verification means there |
|---|---|---|
| Creative pipelines (write/generate/edit/review ads) | `creative` pack | Banned-claims rules, required disclaimers, length/dimension specs, brand rubric judged by a second model, human sign-off |
| Trusted analytics (answers from certified metrics) | `analytics` pack | Answer must come from a certified metric definition; SQL re-run and numbers cross-checked; no invented figures |
| Ops automation (long-running recurring work) | `ops` pack + schedules | Run completes on schedule, output matches template, anomalies flagged |

Why such companies build their own harness instead of buying one: compliance rules must be enforced in code rather than in prompts, outputs need audit trails, and cost per run matters at volume.

The core stays general. A **pack** is just agents + tools + check types + rubrics in a folder, so other domains (e-commerce, legal, SaaS growth) are new packs, not forks.

**Demo rule:** fictional brand + synthetic data only. Never a real company's name, branding or real patient data.

## 2. The three parts of any harness, and what owns each

| Part | What it is | Who provides it |
|---|---|---|
| **Model** | The LLM call: messages in, text/tool calls out | Pydantic AI model layer (many providers) |
| **Loop** | model → tool call → observe → repeat, plus budgets, retries, verification | Pydantic AI agent loop + **our** orchestrator/verifier on top, made durable by Temporal |
| **Memory** | Context for every run: instructions, task history, learned facts, workspace files | **Ours**, stored in Postgres |

We use libraries for the plumbing and write the parts that are the product: orchestration, verification, memory, policy.

## 3. From the reading list: what we use, what we skip

Criteria: actively maintained by a serious org, stable API, multi-provider, and it doesn't lock us into one vendor's models.

### Use

| Tool | Role in our system | Why we trust it |
|---|---|---|
| **Pydantic AI** (+ `pydantic_graph`, `pydantic_evals`) | Model layer + agent loop + tools + MCP client + structured output + evals | Built by the Pydantic team; ships provider adapters for OpenAI, Anthropic, Google, Bedrock, Groq, Mistral, xAI, OpenRouter, Ollama, Cohere and more, plus a `FallbackModel`. It has **built-in durable-execution integrations for Temporal, DBOS and Prefect** (verified in `pydantic_ai_slim/pydantic_ai/durable_exec/`) and emits OpenTelemetry. Commits land daily. |
| **Temporal** (Python SDK) | Durable runs: survive crashes and deploys, retries, timers, waiting days for a human approval | The industry standard for durable workflows, used for agent workloads at OpenAI, Replit and others. Pydantic AI integrates with it directly. Locally it's a single binary (`temporal server start-dev`), no Docker needed. |
| **Model Context Protocol** (official Python SDK + `modelcontextprotocol/servers`) | Plug in external tools (GitHub, Drive, Slack, DBs…) without writing each one | The open standard every major vendor supports. Pydantic AI speaks it natively. |
| **Langfuse** | Traces, cost per run, prompt versions, eval datasets | Open source (MIT), self-hostable, OpenTelemetry-native, so Pydantic AI traces flow in with no custom code. Free cloud tier to start. |
| **Playwright** | Browser tool (screenshots, page checks, web verification) | Microsoft-maintained and the standard for browser automation. Also a verifier: "does the page actually render?" |
| **Inspect AI** | Later: heavier agent benchmarks and red-teaming | UK AISI-maintained. Use once `pydantic_evals` isn't enough. |

### Skip (and why)

| Tool | Reason |
|---|---|
| LangGraph / LangChain | Heavy abstractions, frequent breaking changes, and it overlaps Pydantic AI + Temporal. Worth reading the docs for ideas (graphs, checkpoints). |
| CrewAI | Role-play abstraction hides the loop; hard to control verification and context precisely. |
| Microsoft Agent Framework / AutoGen | In transition (AutoGen merged into Agent Framework); .NET-first focus. |
| OpenAI Agents SDK | Good design, but OpenAI-centric. Reading its `examples/` for patterns (handoffs, guardrails) is worthwhile. |
| LiteLLM | Redundant: Pydantic AI already abstracts providers. Add the proxy later only if we need central key management/rate limits across many users. |
| MetaGPT, SWE-agent, Browser Use | Study material, not dependencies. SWE-bench is useful later as an eval set for coding tasks. |
| Arize Phoenix | Good, but pick one tracing tool. Langfuse covers it. |

### Special case: Claude Agent SDK / Codex CLI as *workers*

These wrap full coding agents (Claude Code, Codex). They aren't our loop, but they make excellent **pluggable workers** for coding tasks: our orchestrator can hand a coding sub-task to a Claude Code worker, then run **our** verifier on the result. Planned for Phase 4 as an optional worker type.

### Not on the list but needed

| Tool | Role |
|---|---|
| **Python 3.13 + uv** | Language and package/env manager (fast, lockfile, used by Pydantic AI itself) |
| **FastAPI** | HTTP API for dashboard + webhooks; SSE for live run streams |
| **Postgres** (Supabase in cloud) | Single source of truth: tasks, runs, events, memory, verdicts. Supabase gives us managed Postgres + `pgvector` + auth + realtime for the dashboard. Locally: plain Postgres in Docker. |
| **E2B** | Cloud sandboxes (Firecracker microVMs, open source) for running agent code safely. Docker containers locally. Same interface. |
| **aiogram** | Telegram bot (async, well maintained). Telegram first because it's free and needs no workspace admin. `slack-bolt` later. |
| **Ruff + pytest + pyright** | Lint, tests, types |
| **Docker Compose** | Local infra (Postgres) now; whole-stack deploy in Phase 3 |

## 4. System diagram

```
            ┌──────────── Channels ────────────┐      ┌──── Dashboard (Next.js) ───┐
            │ Telegram · Slack · Email · CLI   │      │ tasks · live runs · costs  │
            └───────────────┬──────────────────┘      └─────────────┬──────────────┘
                            │ webhooks / messages                   │ REST + SSE
                            ▼                                       ▼
                  ┌─────────────────────────── API (FastAPI) ──────────────────────────┐
                  │ create task · approve/reject · stream events · manage agents/keys  │
                  └───────────────┬────────────────────────────────────┬───────────────┘
                                  │ start workflow                     │ read/write
                                  ▼                                    ▼
                  ┌──────────── Temporal ────────────┐       ┌──────── Postgres ────────┐
                  │ durable RunWorkflow per task     │       │ tasks · runs · events    │
                  └───────────────┬──────────────────┘       │ memory_docs · verdicts   │
                                  │ activities               │ agents · model_profiles  │
                                  ▼                          └──────────▲───────────────┘
   ┌──────────────────────────── Worker ─────────────────────────────┐  │
   │  Orchestrator ──► Planner ──► Executor agent(s) ──► Verifier   │──┘
   │        ▲                         │   (Pydantic AI loop)  │      │
   │        └──── retry with failure feedback ◄───────────────┘      │
   │  Memory loader · Policy/guardrails · Budget meter · Notifier    │
   └────────────┬───────────────────────────┬────────────────────────┘
                ▼                           ▼
     Model providers (any)          Sandbox (Docker / E2B) + MCP servers + Playwright
                                    ──► traces to Langfuse (OTel)
```

## 5. Components

Each is a Python package under `harness/` with one job and a narrow interface.

### 5.1 `models` — model profiles
- A **model profile** = provider + model id + settings + optional fallbacks, stored in DB, e.g. `fast = openrouter:…`, `smart = anthropic:…`, `judge = google:…`.
- Agents reference profiles, not raw model ids, so swapping models is a config change.
- Keys come from env/secret store, never from DB plaintext.
- Thin wrapper over Pydantic AI `Model` / `FallbackModel`.

### 5.2 `agents` — agent definitions
- An agent = name, instructions (markdown, AGENTS.md style), model profile, toolset, budgets, permission policy.
- Defined as files in `agents/<name>/agent.md` with frontmatter (portable, versionable) and synced to DB.
- Built-in agents: `planner`, `executor`, `verifier`. Users add their own.

### 5.3 `orchestrator` — the run lifecycle (Temporal workflow)

```
PENDING → PLANNING → EXECUTING → VERIFYING ─pass─► SUCCEEDED
                         ▲            │
                         └──fail (attempt < max)
                                      │fail (attempts exhausted) ─► FAILED
                 any state ──needs approval──► WAITING_APPROVAL ──► resumes
                 any state ──budget hit / cancel──► STOPPED
```

1. **Plan:** the planner turns the task into a `TaskSpec`: goal, steps, and **acceptance criteria written before any work** (each criterion is a check, §5.4).
2. **Execute:** the executor agent runs the Pydantic AI loop in the sandbox. Every model call and tool call is a Temporal activity, so a crash resumes from the last step and doesn't start over.
3. **Verify:** run the checks. Pass → done. Fail → feed the *specific* failure evidence back to the executor (Reflexion pattern) and retry, up to `max_attempts`.
4. **Report:** final result + verification report to the channel and dashboard.

Sub-agents (Phase 4): the orchestrator can fan out independent steps to parallel executors with isolated context, then merge (Anthropic multi-agent research pattern).

### 5.4 `verify` — the verifier (core differentiator)

**When verification runs: at three moments only, never after every step.**

| Moment | What happens | Cost |
|---|---|---|
| **Reading data** from a knowledge source (DB query, document search) | The tool stamps every returned row/passage with a `source_id` and logs it. No LLM. | Free |
| **End of task** (once per attempt) | Run the acceptance checks below. Deterministic checks always; one batched LLM-judge call only if a criterion needs it (e.g. "claims are backed by sources", "brand voice"). | 0–1 cheap model calls |
| **Before a risky action** (send email, publish, pay, write to a DB) | Human approval via Telegram/dashboard. | Free |

Failed final check → retry with the failure evidence, **max 2 retries**, then report failure. Each task declares its checks up front, so simple tasks with only `command`/`artifact` checks never pay for a judge.

Acceptance criteria are typed checks. Cheapest and most objective run first:

| Check type | Example | How |
|---|---|---|
| `command` | `pytest` exits 0, `npm run build` succeeds | Run in sandbox, check exit code + capture output |
| `artifact` | `report.pdf` exists, JSON matches schema, image is 1080×1080 | File inspection / Pydantic schema |
| `http` / `browser` | Page returns 200, element visible, screenshot | httpx / Playwright |
| `grounded` | "Every fact in the answer comes from the data" | Code: cited `source_id`s exist and are in scope, numbers match a re-run of the SQL. Then one judge call labels each claim supported / unsupported / contradicted against its cited text. "Not in the data" counts as a pass |
| `llm_judge` | "Ad copy follows brand rules" | Rubric graded by a **different model** from the executor, structured verdict output |
| `human` | "Approve before sending to client" | Telegram/dashboard approval, Temporal waits |

Verdict shape (stored per check):
```json
{ "check_id": "c2", "type": "command", "status": "fail",
  "evidence": "3 tests failed: test_login …", "score": null, "cost_usd": 0.0 }
```

Rules: a task with zero deterministic checks gets a warning. The judge never sees the executor's self-assessment, only the artifacts and the rubric. Verifier code is unit-tested against known good/bad outputs.

### 5.5 `memory` — context layer

Our own, small, inside our Postgres. No memory library as a dependency (Mem0 sends telemetry by default and splits state into SQLite; Graphiti needs Neo4j; Hindsight is a whole separate server). We copy their best **ideas**: Hindsight's update verdicts, Graphiti's "valid from/to + source" on every fact, Rakazo's portable markdown docs.

| Tier | What it is | Lifetime | How it reaches the model | Cost |
|---|---|---|---|---|
| **Instructions** | `AGENTS.md`-style markdown per agent/project | Permanent, versioned | Always in the prompt | Free |
| **Working** | Current run's messages + tool results | One run | Pydantic AI history. Near the context limit: rule-based compaction (keep the last N messages, summarise older ones by rule, never split a tool call from its result). An LLM summary only if that isn't enough | Free usually |
| **Episodic** | One summary row per finished run (task, outcome, what failed) | Permanent | Top 3 similar past runs injected at plan time | Free (search) |
| **Facts** | Learned facts and preferences ("brand never says 'cure'") | Permanent, never hard-deleted | Top-k relevant facts injected at plan time; `remember` tool for explicit saves | 1 cheap call per run |

**Write path (once, at the end of a run):** one call to a cheap model extracts 0–5 new facts and compares each with the 5 most similar existing ones, labelling it `new | repeats | changes | ends` (Hindsight's idea). Code applies it: insert, skip, or expire the old fact (`valid_to = now`, `superseded_by = new id`) and insert the new one. Every fact keeps the `source_id` of the run or document it came from.

**Read path (once, at plan time):** Postgres full-text search over facts and run summaries, plus `pgvector` similarity once we add embeddings, merged and capped at a small token budget.

Deliberately left out of v1: knowledge graphs, background consolidation jobs, rerankers. Add only if evals show retrieval is the bottleneck.

**Knowledge sources** (ground truth, separate from memory): connected SQL databases (read-only user), indexed documents (each passage has a stable id), MCP servers. Agents read them through tools that return `source_id`s; this is what the `grounded` check verifies against.

### 5.6 `tools` + `sandbox`
- `Sandbox` interface: `exec(cmd)`, `read/write file`, `upload/download`, `snapshot`, `destroy`. Implementations: `DockerSandbox` (local), `E2BSandbox` (cloud), `LocalSandbox` (dev only, explicit opt-in).
- Built-in tools: shell, files, web fetch, browser (Playwright), memory, `ask_human`.
- MCP servers attachable per agent.
- Tools follow Anthropic's "writing tools for agents" advice: few, well-named tools with token-efficient outputs that are truncated with a pointer to the full result.

### 5.7 `policy` — guardrails & budgets
- **Budgets** per run: max steps, tokens, USD, wall time. Enforced in the loop; hitting one moves the run to `STOPPED` with a report.
- **Permissions**: each tool is tagged `safe | needs_approval | forbidden` per agent (e.g. `send_email` needs approval, `rm -rf /` forbidden).
- **Prompt-injection hygiene** (OWASP LLM Top 10): tool/web content is marked untrusted, never treated as instructions; secrets are never placed in prompts; network egress allowlist in sandboxes.
- Healthcare-style deployments (e.g. telehealth): PHI stays out of traces by default (redaction hook before Langfuse export); audit log of every action in `events`.

### 5.8 `channels` — notifications & control
- `Channel` interface: `send(message)`, `send_approval(request) → decision`, inbound `on_message → create task`.
- Telegram first: `/task <text>`, `/status`, `/stop <id>`, inline Approve/Reject buttons.
- Notification levels per task: `final_only | milestones | everything`.

### 5.9 `api` — FastAPI
Serves the dashboard and channel webhooks. Full endpoint list in `dashboard-spec.md` §5. Live updates via SSE from the `events` table (Supabase Realtime is an alternative for the dashboard).

### 5.10 `evals`
- `pydantic_evals` datasets: fixed tasks with expected outcomes, run on every change to prompts/models/verifier.
- Report: pass rate, cost, latency per model profile, so "should we switch to model X?" gets answered with numbers.

## 6. Data model (Postgres)

```
agents(id, name, instructions_md, model_profile_id, tools jsonb, policy jsonb, version)
model_profiles(id, name, provider, model, settings jsonb, fallbacks jsonb)
tasks(id, title, prompt, source[telegram|api|cli|schedule], agent_id, status,
      notify_level, budget jsonb, created_by, created_at)
runs(id, task_id, attempt, status, temporal_workflow_id, sandbox_id,
     tokens_in, tokens_out, cost_usd, started_at, ended_at)
task_specs(task_id, goal, steps jsonb, criteria jsonb)          -- from planner
events(id, run_id, seq, type, payload jsonb, created_at)         -- append-only log
verdicts(id, run_id, check_id, type, status, evidence, score, cost_usd)
approvals(id, run_id, question, options jsonb, decision, decided_by, decided_at)
memory_docs(id, scope[global|agent|project], scope_id, path, content, revision)   -- instructions tier
facts(id, scope, scope_id, content, source_id, valid_from, valid_to, superseded_by,
      tsv, embedding vector null)                                 -- facts tier
run_summaries(run_id, summary, outcome, tsv, embedding vector null) -- episodic tier
knowledge_sources(id, kind[sql|docs|mcp], name, config jsonb)      -- read-only ground truth
artifacts(id, run_id, path, kind, size, storage_url)
schedules(id, agent_id, cron, prompt, enabled)                  -- recurring ops work
```

`events` is the backbone: dashboard timeline, channel updates, audit log and debugging all read from it. Types: `run.started, plan.created, model.call, tool.call, tool.result, check.result, approval.requested, approval.decided, run.finished, budget.exceeded, error`.

## 7. Local vs cloud

Same code, different adapters via env (`HARNESS_ENV=local|cloud`):

| Concern | Local | Cloud |
|---|---|---|
| Entry | `harness run "…"` CLI + API on localhost | API behind HTTPS domain |
| Durable runtime | `temporal server start-dev` | Temporal (self-hosted container on the VM, or Temporal Cloud) |
| DB | Postgres in Docker | Supabase Postgres |
| Sandbox | Docker containers | E2B |
| Traces | Langfuse cloud (free) | same |
| Deploy | — | One VM (Hetzner/DigitalOcean) or Railway running `api` + `worker` (+ temporal) via Docker Compose. Dashboard on Vercel. |

## 8. Docker: now or later?

**Install Docker Desktop now. Don't containerise our app yet.**
- Now (Phase 1–2): Docker only runs Postgres and the agent sandbox. An agent running shell commands directly on your laptop is the single biggest risk, so sandbox from the first time the agent can execute code.
- Later (Phase 3): write `Dockerfile`s for `api` and `worker` + a `docker-compose.yml` when we deploy to the cloud.

## 9. Build phases

| Phase | Deliverable | "Done" means |
|---|---|---|
| **0. Setup** | Repo, uv, ruff, pytest, Postgres in Docker, `.env`, AGENTS.md | `uv run pytest` green |
| **1. Local core** | Model profiles, executor agent, Docker sandbox, verifier (`command`, `artifact`, `llm_judge`), CLI `harness run` | CLI completes "build a script that does X", runs checks, retries on failure, prints the report |
| **2. Durable + API** | Temporal workflow, events table, FastAPI + SSE, planner agent, budgets, memory tiers | Kill the worker mid-run → restart → run resumes. Dashboard API endpoints return real data |
| **3. Cloud + channels** | Docker images, VM deploy, Supabase, E2B, Telegram bot with approvals | Send `/task` from phone with laptop closed → get result + verdict in Telegram |
| **4. Scale & quality** | Langfuse, eval suite, sub-agents, schedules, Claude Code/Codex worker, Slack | Eval report compares 3 model profiles on 10 tasks |

The application video fits after Phase 3: the end-to-end demo below, plus building one real piece live (e.g. a new check type) with sub-agents.

### Flagship demo (end to end, recorded)

Fictional telehealth brand "Northwind Health", synthetic data.

1. From Telegram: `/task Make 3 Instagram ad variants for our oral weight-loss program, launch Monday.`
2. **Planner** writes the TaskSpec + acceptance criteria: 3 variants; ≤125-char primary text; 1080×1080 image; no banned claims ("guaranteed", "FDA-approved" for compounded products, specific lbs promises without "results may vary"); required safety disclaimer present; brand-voice rubric ≥ 4/5.
3. **Copywriter** and **image** agents produce variants in the sandbox.
4. **Verifier:** deterministic compliance rules → image dimension check → LLM judge on a different model. One variant fails ("lose 30 lbs guaranteed") → feedback → rewrite → pass.
5. **Human gate:** Telegram shows the 3 variants with Approve/Reject.
6. **Report:** an HTML report artifact with variants, the verification table, cost, and trace link, posted back to Telegram and visible on the dashboard.

Second demo (analytics): "What was CAC by channel last month?" → agent queries synthetic Postgres through a certified-metrics layer → verifier re-runs the SQL and checks the metric is certified → chart + answer.

### Building with sub-agents

Once Phase 0 fixes the interfaces (`Sandbox`, `Check`, `Channel`, `MemoryStore`, event schema), independent modules are built in parallel by sub-agents, each in its own git worktree with its own tests. The lead agent (orchestrator) reviews and merges them. Parallel-safe groups: {sandbox, verify checks} · {memory, db} · {channels/telegram} · {api}. Orchestrator + Temporal workflow is built by the lead, since it touches everything.

## 10. Repo layout

```
harness/
  AGENTS.md                 # instructions for coding agents working on this repo
  pyproject.toml  uv.lock
  docs/architecture.md  docs/dashboard-spec.md
  agents/                   # agent definitions (markdown + frontmatter)
    planner/agent.md  executor/agent.md  verifier/agent.md
  src/harness/
    models/  agents/  orchestrator/  verify/  memory/
    tools/  sandbox/  policy/  channels/  api/  evals/
    db/ (schema, migrations)  cli.py  config.py
  tests/
  infra/ docker-compose.yml  (Phase 3: Dockerfile.api, Dockerfile.worker)
  _reference/               # cloned repos for study, git-ignored
```

## 11. Decisions

Decided:
- **Python 3.13** backend. Go/Rust only later, for an isolated piece with a measured need.
- Stack as in §3: Pydantic AI, Temporal, Postgres/Supabase + pgvector, Docker/E2B sandboxes, Langfuse, FastAPI, Telegram.
- **Own memory on Postgres** (§5.5), borrowing ideas from Hindsight and Graphiti.
- **Verification at three moments only** (§5.4).
- **Local first, then cloud.**

Still open:
1. Model API keys available (need two providers: worker ≠ judge, plus image generation for the creative demo).
2. Cloud host: small VM vs Railway (decide at Phase 3).

Reference code: ideas may be studied from other projects, but no code or prompt text is copied from any repository of unclear provenance.
