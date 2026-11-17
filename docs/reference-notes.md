# Reference repo survey — what's worth adopting

Synthesis of `_reference/` clones vs `src/agent0`, 2026-11-17. Three explorers covered all repos; `claw-code` excluded per AGENTS.md (unclear provenance — learn nothing from it).

## Verdict per repo

| Repo | What it is | Use for us |
|---|---|---|
| `pydantic-ai` | Our model/agent-loop layer (dev-tree checkout, ahead of release) | Already a dependency. Big find: `durable_exec/` + `pydantic_ai_harness` capabilities exist in this checkout — verify installed version before adopting |
| `openai-agents-python` | OpenAI's agent SDK | Patterns only: guardrails, handoffs/`as_tool`, session protocol, approvals. We skipped it as a dep (OpenAI-centric) |
| `claude-agent-sdk-python` | Thin wrapper spawning Claude Code CLI | Phase-4 worker type — see below |
| `mem0` | Memory library | Ideas only (we rejected the dep: telemetry, SQLite). Borrow: session context for extraction, hash dedup, memory audit history |
| `graphiti` | Temporal knowledge graph (Neo4j/FalkorDB/Neptune) | Ideas only — no Postgres backend. Borrow: bi-temporal edge semantics, future-tense normalization, window-overlap invalidation |
| `hindsight` | Memory server, **Postgres-only** | Best architectural match. Borrow: `text_signals` FTS enrichment, interleave fusion, proof_count, consolidation job |
| `rakazo` | Self-hosted "AI teammates" platform (TS, Hono+Prisma) | Ideas only. Borrow: markdown memory docs w/ revisions + byte-budgeted prompt injection, taint tracking, effect idempotency, `withoutBlankFields` |

## Top adopt candidates (prioritized)

### 1. Per-operation durability for Temporal runs — BIGGEST WIN
Today `orchestrator/temporal.py` runs a whole agent attempt as ONE `maximum_attempts=1` activity — a worker crash re-runs the entire attempt and burns tokens. The pydantic-ai checkout has `durable_exec/temporal/` (`TemporalDurability` capability) making each model request/tool call its own checkpointed activity, with non-retryable error classification (`ModelQuotaExceeded`, `ModelRequestTimeout`…) and heartbeat policy. Not drop-in — requires restructuring `RunWorkflow`/`Engine` so agent loops run inside the workflow — but `drive()` and `Engine` step methods are already well-shaped for it. **First check whether the pinned `pydantic-ai-slim` version ships `durable_exec`.**

### 2. Claude Code as a worker (Phase 4, per architecture §74)
`claude-agent-sdk-python` maps cleanly onto our loop:
- `query()`/`ClaudeSDKClient` per execute attempt, `cwd` = sandbox workspace
- `permission_mode="dontAsk"` + `can_use_tool` callback → our `Policy.decide` + existing `WAITING_APPROVAL` flow (`Allow` supports `updated_input` — can rewrite args)
- `create_sdk_mcp_server` exposes our knowledge/memory tools in-process to the worker → it can emit `[src:id]` citations our `grounded` check already verifies
- `ResultMessage.total_cost_usd`/`usage` → `UsageMeter`; `session_id` on the run row
- `resume_session_at` + Postgres `SessionStore` (reference impl in `examples/session_stores/postgres_session_store.py`) → durable, resumable, auditable worker transcripts; resume-with-dropped-failed-turn fits our retry-with-feedback loop perfectly

### 3. Memory upgrades (all Postgres-only, from hindsight/mem0/graphiti)
- **`text_signals`-style enriched tsvector** — hindsight stores entity names + normalized date strings alongside fact text for BM25. One generated column on `facts`, immediate recall gain.
- **Interleave fusion for dedup candidates** — hindsight's `interleave_fusion` (round-robin across retrieval arms) keeps near-duplicates that RRF buries. Use it ONLY in `extract.py`'s candidate-recall path, keep RRF for user-facing recall. ~40 lines.
- **`repeats` verdict → increment a counter** on the target fact (mini `proof_count`) + small log-normalized ranking boost. Cheap dedup signal we currently discard.
- **Temporal verdict semantics** (graphiti-lite) — let `changes`/`ends` carry optional event-time `valid_to` + future flag; apply deterministic future-tense clamp and window-overlap check before expiring, instead of unconditional `valid_to=now()`.
- **Session context for extraction** (mem0) — feed last ~10 messages into the extraction call so `changes`/`ends` targets resolve against what was just said.
- Deferred: full entity resolution, consolidation job/observation tier, cross-encoder reranker.

### 4. Markdown memory documents (the rakazo borrow the docs promised)
`MarkdownMemoryStore`: path-scoped markdown docs, `MEMORY.md` index, `expectedRevision` optimistic concurrency, 4KB/doc cap where a full doc returns current entries so the agent consolidates instead of losing notes, and a **byte-budgeted prompt renderer that reports what was omitted**. Complements the facts table — good for agent instructions/preferences that shouldn't be fuzzy-recalled. `editMemory` does targeted old_text edits (unique match required).

### 5. Tool/policy upgrades (pydantic-ai + rakazo)
- **`UsageLimits` full surface** — we only pass `request_limit`; add `cost_limit`, `tool_calls_limit`, token limits, `per_request_input_tokens_limit` — free in-loop enforcement (`steps.py:231`).
- **Wrapper toolset pattern** — pydantic-ai's `ApprovalRequiredToolset`/`DeferredLoadingToolset`/`ToolOutputLimits` (banded truncate→summarize→spill-to-file + `read_tool_result` read-back) as composable wrappers instead of per-tool checks; deferred loading matters once MCP/skill count grows.
- **Taint tracking + effect idempotency** (rakazo `run-trust.ts`/`run-effects.ts`) — mark runs tainted on outside-content reads; claim `(run, tool, args-hash)` so retried approvals don't double-send. Plus `withoutBlankFields` normalization for tool args.
- **History-side tool-output trimming** (OpenAI `ToolOutputTrimmer`) — we truncate at production; long runs still accumulate large outputs in history.

### 6. Evals (greenfield — `evals/` is empty)
`pydantic_evals` Dataset/Case YAML format + agentic evaluators (`ToolCorrectness`, `TrajectoryMatch`, `ArgumentCorrectness` over span trees — map our `EventType` stream to spans), `MaxToolCalls`/`MaxModelRequests` ↔ `Budget.max_steps`, optional `@evaluate` online decorator for sampling production runs.

### 7. Sub-agents / handoffs — biggest functional gap
agent0 has planner→executor→verifier fixed pipeline; nothing composes agents at runtime. OpenAI's `Agent.as_tool` (agent-as-tool, caller stays in control) is the cleaner fit than handoffs; pydantic-ai-harness `sub_agents` capability is a reference impl. Enables specialist delegation (research/analysis workers) — natural Phase 4 alongside the Claude worker.

## Explicitly not worth copying
- Rakazo's Pages/RPC/UI stack, Graphile queue (we have Temporal), Pi runtime (we use Pydantic AI), naive substring memory search (our FTS+vector RRF is better)
- mem0's entity store (spaCy NER + SQLite history) — heavy, wrong infra
- graphiti's Neo4j dependency — mechanisms only
- LangGraph/CrewAI/AutoGen/LiteLLM — already rejected in architecture doc
- OpenAI `RunState` serialize-and-resume approvals — our Temporal signal + re-execute-with-approved-keys is simpler and already durable
