# Harness Dashboard — Frontend Spec

For the agent building the frontend. The backend (FastAPI) is built separately; this file is the contract between them. Architecture context: `architecture.md`.

## 1. Purpose

One place to see and steer every agent: what is running now, what each run did step by step, whether its work passed verification, what it cost, and what needs a human decision.

Primary user: the operator (single user in v1, design so a small team works later). Used on desktop mostly, **must work on phone** (approvals happen on the go).

## 2. Stack

- Next.js (App Router) + TypeScript, Tailwind + shadcn/ui, deployed on Vercel.
- Data: REST from `NEXT_PUBLIC_API_URL`; live updates via **SSE** (`EventSource`).
- Auth v1: bearer API key stored server-side (Next.js route handlers proxy to the API; the key never reaches the browser). Replaceable with Supabase Auth later.
- Mock mode: when `NEXT_PUBLIC_MOCK=1`, serve fixtures from `/mocks` matching the shapes in §6 so the UI can be built before the backend exists.

## 3. Pages

### 3.1 Overview `/`
- Stat row: running now · waiting for approval · succeeded (24h) · failed (24h) · spend today (USD).
- **Needs you** list (top, prominent): pending approvals with inline Approve / Reject.
- Live runs: card per running run → agent, task title, current state, current step text, elapsed time, cost so far, progress (attempt n of max).
- Recent finished runs (last 20) with status badge and verification result.

### 3.2 Tasks `/tasks`
- Table: title, agent, source (telegram/api/cli/schedule), status, attempts, verification (✓ n/n checks), cost, created.
- Filters: status, agent, source, date. Search by title.
- **New task** button → dialog: prompt (textarea), agent (select), notify level, budget overrides (max USD, max steps), optional acceptance criteria editor (list of checks; type + config). Submit → `POST /tasks`, then go to run page.

### 3.3 Run detail `/runs/[id]` — the most important page
- Header: task title, agent, model profile, status, attempt selector (attempt 1, 2, 3…), totals (tokens, cost, duration), actions: **Stop**, **Retry**, **Open sandbox files**.
- Left/main: **Timeline** of `events`, streamed live. Each event type renders differently:
  - `plan.created` → goal + steps + acceptance criteria list
  - `model.call` → model, tokens, cost, latency; expandable to show messages
  - `tool.call` / `tool.result` → tool name, args (collapsed JSON), result (truncated, expandable)
  - `check.result` → pass/fail chip + evidence
  - `approval.requested` → inline approve/reject
  - `error`, `budget.exceeded` → red callout
- Right panel (stacks under on mobile): **Verification report**: each criterion with status (pending/pass/fail), type icon, evidence, judge score. Then **Artifacts**: produced files with preview (image, text, markdown, JSON) and download.
- Auto-scroll to newest event, with a "jump to latest" button when the user has scrolled up.

### 3.4 Approvals `/approvals`
- Pending first, then history. Each: question, run link, options, who decided, when.

### 3.5 Agents `/agents` and `/agents/[name]`
- List: name, model profile, tool count, runs (7d), success rate, avg cost.
- Detail: instructions (markdown view + edit), model profile select, tools with permission level (safe / needs approval / forbidden), budgets. Save → `PUT /agents/{name}` (creates a new version; show version history).

### 3.6 Models & providers `/models`
- Grouped by **capability** tabs: Chat · Vision · Image · Voice (TTS) · Speech-to-text · Embeddings.
- Each profile row: name, provider (logo-free text badge), model, tags (cheap/fast/smart), cost, key status (configured / missing; **never show key values**), enabled toggle.
- Router preview: pick a capability + preference → shows which profile the router would choose and why.
- Per-profile stats: calls, pass rate, avg cost, avg latency, error rate (7d).
- Add/edit profile form (provider, model, capability, tags, cost, key env var name).

### 3.6b Usage `/usage`
- Spend over time (stacked by provider), calls by capability, top runs by cost, error rate by provider.
- Filters: date range, provider, capability, agent.
- Table of individual calls (from `usage`), linking to their run.

### 3.6c Activity `/activity`
- One live, global feed of every event across all runs (model calls, tool calls, checks, approvals, errors), filterable by type/agent/run. This is the "what is everything doing right now" view.

### 3.6d Extensions `/extensions`
- Tabs: **Skills** (name, description, source path, used-in-runs count, enabled) · **MCP servers** (name, transport, connection status, tool list, attached agents) · **Plugins** (name, what it bundles, enabled).
- Skill detail shows the `SKILL.md` rendered. MCP detail shows tools and a "test connection" button.

### 3.7 Memory `/memory`
- List of learned **facts** (filter by scope: global / agent / project; toggle "show expired"). Each: content, source (run or document id, linked), valid from, current/expired badge.
- Search box (`GET /memory/search?q=`).
- Edit a fact (`PUT /memory/{id}` with `{content}`): the old fact is expired and a new one supersedes it.
- Forget (`DELETE /memory/{id}`): expires it (never hard-deleted).
- History (`GET /memory/{id}/revisions`): the chain of versions.
- Agent instructions (the "instructions" memory tier) are edited on the Agents page.

### 3.8 Schedules `/schedules`
- Recurring tasks: agent, cron (with human-readable "every Monday 9:00"), prompt, enabled toggle, last/next run.

### 3.9 Settings `/settings`
- Channels: Telegram/Slack connection status, default notify level.
- Global budgets (daily USD cap).

### 3.10 API keys `/settings/keys`
- One row per key the registry needs (e.g. `GROQ_API_KEY`, `GEMINI_API_KEY`, `AGENT0_TELEGRAM_BOT_TOKEN`): name, which providers/capabilities use it, status (`configured` with `••••last4` and updated time / `missing` / `from environment`).
- **Set / replace**: password-type input, submit → `PUT /secrets/{name}`. The field clears immediately after submit; the value is never displayed again, never stored in browser state, localStorage or logs.
- **Test**: `POST /secrets/{name}/test` → shows ok / error message.
- **Remove**: `DELETE /secrets/{name}` with a confirm step.
- Keys set via server environment show as "from environment" and are read-only here.

Security rules for the frontend:
- All API calls go through Next.js server route handlers that attach the `AGENT0_API_KEY` bearer token server-side. The browser never sees that token or any provider key.
- The dashboard itself requires login (v1: a single password via env `DASHBOARD_PASSWORD`, httpOnly secure session cookie; replaceable with Supabase Auth). No page, including `/settings/keys`, renders without a session.
- Secret values are only ever in the request body of `PUT /secrets/{name}` over HTTPS.

## 4. Design guidance

- Calm, dense, operator-tool feel (think Linear / Vercel dashboard), not marketing.
- Light and dark mode.
- Status colours used consistently everywhere: running = blue, waiting approval = amber, succeeded = green, failed = red, stopped = grey.
- Monospace for ids, JSON, logs, commands. Costs always `$0.0000` precision under $1, `$0.00` above.
- Relative times ("3m ago") with absolute time on hover.
- Every list has an empty state that says what to do next ("No tasks yet — send /task in Telegram or click New task").
- Mobile: overview + approvals + run detail must be fully usable at 375px width.

## 5. API contract

Base: `/api/v1`. JSON. Errors: `{ "error": { "code": "string", "message": "string" } }`. Lists are paginated with `?limit=&cursor=` → `{ "items": [...], "next_cursor": "string|null" }`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/stats/overview` | Stat row numbers |
| GET | `/tasks` | List (filters: `status, agent, source, q, from, to`) |
| POST | `/tasks` | Create task → `{ task, run }` |
| GET | `/tasks/{id}` | Task + its runs |
| GET | `/runs?status=running` | Live/recent runs |
| GET | `/runs/{id}` | Run + spec + verdicts + artifacts |
| GET | `/runs/{id}/events?after_seq=` | Event history |
| GET | `/runs/{id}/stream` | **SSE** stream of new events (`event: <type>`, `data: <Event JSON>`; supports `Last-Event-ID` = seq) |
| POST | `/runs/{id}/stop` | Stop run |
| POST | `/tasks/{id}/retry` | New attempt |
| GET | `/runs/{id}/artifacts/{artifact_id}` | Download/preview artifact |
| GET | `/approvals?status=pending` | Approvals |
| POST | `/approvals/{id}` | `{ "decision": "approve"\|"reject", "note"?: string }` |
| GET/POST | `/agents`, GET/PUT `/agents/{name}`, GET `/agents/{name}/versions` | Agents |
| GET/POST | `/model-profiles`, PUT/DELETE `/model-profiles/{id}` | Model profiles (`?capability=`) |
| GET | `/router/preview?capability=&prefer=` | Which profile the router picks + reason |
| GET | `/usage?from=&to=&provider=&capability=&agent=` | Individual model calls |
| GET | `/usage/summary?from=&to=&group_by=provider\|capability\|agent\|day` | Aggregates for charts |
| GET | `/events?type=&agent=&run_id=` | Global activity feed history (live via `/stream`) |
| GET | `/extensions?kind=skill\|mcp\|plugin`, GET/PUT `/extensions/{id}` | Skills, MCP servers, plugins |
| POST | `/extensions/{id}/test` | Test an MCP connection |
| GET | `/secrets` | `[{ name, last4, configured, source: "store"\|"env"\|null, updated_at }]`, never values |
| PUT | `/secrets/{name}` | `{ "value": string }` → stored encrypted (204) |
| DELETE | `/secrets/{name}` | Remove stored key (204) |
| POST | `/secrets/{name}/test` | `{ ok: boolean, message: string }` |
| GET | `/memory?scope=&scope_id=&include_expired=`, GET `/memory/search?q=` | Facts list/search |
| GET/PUT/DELETE | `/memory/{id}`, GET `/memory/{id}/revisions` | Fact (PUT `{content}` supersedes; DELETE expires) |
| GET/POST | `/schedules`, PUT/DELETE `/schedules/{id}` | Schedules |
| GET | `/stream` | **SSE** global stream: every new event across runs (powers Overview + Activity) |

## 6. Core shapes

```ts
type RunStatus = "pending" | "planning" | "executing" | "verifying"
  | "waiting_approval" | "succeeded" | "failed" | "stopped";

interface Task {
  id: string; title: string; prompt: string;
  source: "telegram" | "slack" | "api" | "cli" | "schedule";
  agent: string; status: RunStatus; attempts: number;
  notify_level: "final_only" | "milestones" | "everything";
  budget: { max_usd?: number; max_steps?: number; max_minutes?: number };
  created_at: string; // ISO
}

interface Run {
  id: string; task_id: string; attempt: number; status: RunStatus;
  agent: string; model_profile: string;
  current_step?: string;            // human-readable "Running pytest"
  tokens_in: number; tokens_out: number; cost_usd: number;
  started_at: string; ended_at?: string;
  checks_total: number; checks_passed: number;
}

interface Criterion {
  id: string; description: string;
  type: "command" | "artifact" | "http" | "browser" | "llm_judge" | "human";
  config: Record<string, unknown>;
}

interface Verdict {
  check_id: string; type: Criterion["type"];
  status: "pending" | "pass" | "fail" | "error";
  evidence: string; score?: number; cost_usd: number;
}

interface RunEvent {
  id: string; run_id: string; seq: number; created_at: string;
  type: "run.started" | "plan.created" | "model.call" | "tool.call" | "tool.result"
      | "skill.loaded" | "memory.recalled" | "memory.saved" | "knowledge.read"
      | "check.result" | "approval.requested" | "approval.decided"
      | "budget.exceeded" | "error" | "run.finished";
  payload: Record<string, unknown>;
}

interface Approval {
  id: string; run_id: string; question: string; options: string[];
  status: "pending" | "approved" | "rejected";
  decided_by?: string; decided_at?: string; note?: string;
}

type Capability = "chat" | "vision" | "image_gen" | "tts" | "stt" | "embedding";

interface ModelProfile {
  id: string; name: string; provider: string; model: string;
  capability: Capability; tags: string[];
  cost: { input_per_mtok?: number; output_per_mtok?: number; per_image?: number; per_1k_chars?: number };
  key_configured: boolean; enabled: boolean;
}

interface UsageRecord {
  id: string; run_id?: string; profile: string; provider: string; model: string;
  capability: Capability; input_units: number; output_units: number;
  cost_usd: number; latency_ms: number; ok: boolean; created_at: string;
}

interface Extension {
  id: string; kind: "skill" | "mcp" | "plugin"; name: string; description: string;
  enabled: boolean; status?: "connected" | "error" | "idle";
  config: Record<string, unknown>;
}

interface MemoryFact {
  id: string; scope: "global" | "agent" | "project"; scope_id?: string;
  content: string; source_id?: string; valid_from: string; valid_to?: string;
  superseded_by?: string; current: boolean;
}

interface Artifact {
  id: string; run_id: string; path: string;
  kind: "image" | "audio" | "text" | "markdown" | "json" | "pdf" | "video" | "other";
  size: number; url: string;
}
```

## 7. Acceptance checklist for the frontend

- [ ] All pages work in mock mode with fixtures covering every `RunStatus` and every event type.
- [ ] Run detail streams events live and recovers after network drop (reconnect with `Last-Event-ID`).
- [ ] Approve/Reject works from Overview, Approvals and Run detail, and the UI updates without reload.
- [ ] No API key or secret ever appears in browser network requests or bundles.
- [ ] Overview, Approvals, Run detail usable at 375px.
- [ ] Light + dark mode.
- [ ] Image and audio artifacts preview inline (audio player for TTS output).
- [ ] Usage page totals match the sum of `usage` rows for the same filters.
