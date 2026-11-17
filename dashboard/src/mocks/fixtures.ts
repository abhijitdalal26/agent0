import type {
  Task,
  Run,
  Criterion,
  Verdict,
  RunEvent,
  Approval,
  ModelProfile,
  UsageRecord,
  Extension,
  Artifact,
  AgentDefinition,
  MemoryDoc,
  Schedule,
  OverviewStats,
} from "@/types";

export const MOCK_OVERVIEW_STATS: OverviewStats = {
  running_now: 2,
  waiting_approval: 1,
  succeeded_24h: 38,
  failed_24h: 2,
  spend_today_usd: 1.4826,
};

export const MOCK_APPROVALS: Approval[] = [
  {
    id: "app-981",
    run_id: "run-301",
    task_title: "Update daily inventory sync & reorder triggers",
    question: "Authorize supplier purchase order for SKU-8821 ($4,250.00 from Acme Med Supply)?",
    options: ["Approve purchase", "Reject"],
    status: "pending",
  },
  {
    id: "app-842",
    run_id: "run-102",
    task_title: "Make 3 Instagram ad variants for our oral weight-loss program, launch Monday",
    question: "Approve publishing 3 creative variants to Meta Ad Manager staging campaign?",
    options: ["Approve", "Reject"],
    status: "approved",
    decided_by: "@operator (Telegram)",
    decided_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    note: "Variants pass all medical claims checks. Copy looks punchy.",
  },
  {
    id: "app-719",
    run_id: "run-501",
    task_title: "Execute automated database index compaction",
    question: "Run CONCURRENTLY REINDEX on primary database table 'events' (5.2GB)?",
    options: ["Approve", "Reject"],
    status: "rejected",
    decided_by: "@operator (Dashboard)",
    decided_at: new Date(Date.now() - 3600000 * 14).toISOString(),
    note: "Peak traffic window; schedule during weekend maintenance.",
  },
];

export const MOCK_TASKS: Task[] = [
  {
    id: "task-102",
    title: "Make 3 Instagram ad variants for our oral weight-loss program, launch Monday",
    prompt:
      "Make 3 Instagram ad variants for our oral weight-loss program, launch Monday. Include compliant disclaimers, high-res visual assets, and pass brand voice grading.",
    source: "telegram",
    agent: "creative-pack",
    status: "succeeded",
    attempts: 2,
    notify_level: "everything",
    budget: { max_usd: 1.5, max_steps: 30, max_minutes: 15 },
    created_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    checks_total: 5,
    checks_passed: 5,
    cost_usd: 0.0342,
  },
  {
    id: "task-205",
    title: "Compute CAC by channel last month from certified metrics",
    prompt:
      "Query our read-only database to calculate Customer Acquisition Cost (CAC) by channel for the prior calendar month. Use only certified metrics and cross-check SQL.",
    source: "cli",
    agent: "analytics-agent",
    status: "executing",
    attempts: 1,
    notify_level: "milestones",
    budget: { max_usd: 0.5, max_steps: 15 },
    created_at: new Date(Date.now() - 1000 * 240).toISOString(),
    checks_total: 3,
    checks_passed: 1,
    cost_usd: 0.0084,
  },
  {
    id: "task-301",
    title: "Update daily inventory sync & reorder triggers",
    prompt:
      "Fetch stock levels across our distribution hubs. When stock falls below safety stock threshold, draft purchase order and await human approval.",
    source: "schedule",
    agent: "ops-agent",
    status: "waiting_approval",
    attempts: 1,
    notify_level: "milestones",
    budget: { max_usd: 0.2, max_steps: 20 },
    created_at: new Date(Date.now() - 1000 * 600).toISOString(),
    checks_total: 2,
    checks_passed: 1,
    cost_usd: 0.012,
  },
  {
    id: "task-404",
    title: "Generate weekly executive health summary",
    prompt:
      "Scan platform alerts, agent pass rates, and compute weekly model cost aggregates. Prepare Markdown summary for Monday standup.",
    source: "api",
    agent: "planner",
    status: "planning",
    attempts: 1,
    notify_level: "final_only",
    budget: { max_usd: 0.25, max_steps: 10 },
    created_at: new Date(Date.now() - 1000 * 45).toISOString(),
    checks_total: 2,
    checks_passed: 0,
    cost_usd: 0.0015,
  },
  {
    id: "task-501",
    title: "Refactor database migrations for pgvector cosine indexing",
    prompt:
      "Generate SQL migration for HNSW cosine vector index on facts table and run unit tests in sandbox.",
    source: "cli",
    agent: "executor",
    status: "failed",
    attempts: 2,
    notify_level: "everything",
    budget: { max_usd: 0.5, max_steps: 25 },
    created_at: new Date(Date.now() - 3600000 * 5).toISOString(),
    checks_total: 4,
    checks_passed: 2,
    cost_usd: 0.045,
  },
  {
    id: "task-602",
    title: "Verify SSL certificates across staging domains",
    prompt: "Scan staging cluster ingress hosts and verify cert expiry is > 30 days.",
    source: "schedule",
    agent: "ops-agent",
    status: "stopped",
    attempts: 1,
    notify_level: "final_only",
    budget: { max_usd: 0.1, max_steps: 10 },
    created_at: new Date(Date.now() - 3600000 * 18).toISOString(),
    checks_total: 1,
    checks_passed: 1,
    cost_usd: 0.0004,
  },
];

export const MOCK_RUNS: Record<string, Run> = {
  "run-102": {
    id: "run-102",
    task_id: "task-102",
    attempt: 2,
    status: "succeeded",
    agent: "creative-pack",
    model_profile: "groq-llama-3.3-70b",
    current_step: "Task completed. All 5 verification checks passed.",
    tokens_in: 3420,
    tokens_out: 1400,
    cost_usd: 0.0342,
    started_at: new Date(Date.now() - 3600000 * 2).toISOString(),
    ended_at: new Date(Date.now() - 3600000 * 2 + 1000 * 94).toISOString(),
    checks_total: 5,
    checks_passed: 5,
  },
  "run-102-att1": {
    id: "run-102-att1",
    task_id: "task-102",
    attempt: 1,
    status: "failed",
    agent: "creative-pack",
    model_profile: "groq-llama-3.3-70b",
    current_step: "Failed verification check: Banned claims check detected 'guaranteed'",
    tokens_in: 2150,
    tokens_out: 950,
    cost_usd: 0.021,
    started_at: new Date(Date.now() - 3600000 * 2 - 1000 * 120).toISOString(),
    ended_at: new Date(Date.now() - 3600000 * 2 - 1000 * 20).toISOString(),
    checks_total: 5,
    checks_passed: 3,
  },
  "run-205": {
    id: "run-205",
    task_id: "task-205",
    attempt: 1,
    status: "executing",
    agent: "analytics-agent",
    model_profile: "gemini-2.5-flash",
    current_step: "Executing certified SQL query on replica database (step 4 of 6)",
    tokens_in: 1100,
    tokens_out: 320,
    cost_usd: 0.0084,
    started_at: new Date(Date.now() - 1000 * 240).toISOString(),
    checks_total: 3,
    checks_passed: 1,
  },
  "run-301": {
    id: "run-301",
    task_id: "task-301",
    attempt: 1,
    status: "waiting_approval",
    agent: "ops-agent",
    model_profile: "groq-llama-3.3-70b",
    current_step: "Awaiting approval: supplier purchase order authorization",
    tokens_in: 1650,
    tokens_out: 450,
    cost_usd: 0.012,
    started_at: new Date(Date.now() - 1000 * 600).toISOString(),
    checks_total: 2,
    checks_passed: 1,
  },
  "run-404": {
    id: "run-404",
    task_id: "task-404",
    attempt: 1,
    status: "planning",
    agent: "planner",
    model_profile: "gemini-2.5-flash",
    current_step: "Formulating TaskSpec & acceptance checks",
    tokens_in: 350,
    tokens_out: 100,
    cost_usd: 0.0015,
    started_at: new Date(Date.now() - 1000 * 45).toISOString(),
    checks_total: 2,
    checks_passed: 0,
  },
};

export const MOCK_CRITERIA_VERDICTS: Record<
  string,
  { criteria: Criterion[]; verdicts: Verdict[] }
> = {
  "run-102": {
    criteria: [
      {
        id: "c-1",
        description: "Generate exactly 3 distinct creative headline/copy variants under 125 chars",
        type: "artifact",
        config: { target: "variants.json", schema: "VariantsArray", count: 3 },
      },
      {
        id: "c-2",
        description: "Produce 1080x1080 square image assets for each variant in sandbox",
        type: "command",
        config: { command: "python verify_images.py --dim 1080x1080" },
      },
      {
        id: "c-3",
        description: "Zero banned claims (FTC/FDA: no 'guaranteed', no explicit lbs promises without asterisk)",
        type: "command",
        config: { command: "python check_banned_claims.py" },
      },
      {
        id: "c-4",
        description: "LLM Judge on independent provider: brand voice & clinical compliance >= 4.0/5.0",
        type: "llm_judge",
        config: { judge_profile: "gemini-1.5-pro", min_score: 4.0 },
      },
      {
        id: "c-5",
        description: "Human operator review & publishing approval",
        type: "human",
        config: { channel: "telegram" },
      },
    ],
    verdicts: [
      {
        check_id: "c-1",
        type: "artifact",
        status: "pass",
        evidence: "3 variants created in artifacts/variants.json. Character lengths: 104, 118, 97.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-2",
        type: "command",
        status: "pass",
        evidence: "verify_images.py exit 0: 3 assets verified at 1080x1080 RGBA PNG.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-3",
        type: "command",
        status: "pass",
        evidence: "check_banned_claims.py exit 0: 0 violations found. Disclaimer verified: 'Consult physician. Results may vary.'",
        cost_usd: 0.0,
      },
      {
        check_id: "c-4",
        type: "llm_judge",
        status: "pass",
        score: 4.8,
        evidence: "Gemini 1.5 Pro judged brand voice 4.8 / 5.0. 'Medically grounded, positive tone, transparent disclaimer placement.'",
        cost_usd: 0.0024,
      },
      {
        check_id: "c-5",
        type: "human",
        status: "pass",
        evidence: "Approved by @operator via Telegram at 14:32 UTC. Note: 'Variants pass all medical claims checks.'",
        cost_usd: 0.0,
      },
    ],
  },
  "run-102-att1": {
    criteria: [
      {
        id: "c-1",
        description: "Generate exactly 3 distinct creative headline/copy variants under 125 chars",
        type: "artifact",
        config: { target: "variants.json" },
      },
      {
        id: "c-2",
        description: "Produce 1080x1080 square image assets for each variant in sandbox",
        type: "command",
        config: { command: "python verify_images.py --dim 1080x1080" },
      },
      {
        id: "c-3",
        description: "Zero banned claims (FTC/FDA: no 'guaranteed')",
        type: "command",
        config: { command: "python check_banned_claims.py" },
      },
      {
        id: "c-4",
        description: "LLM Judge on independent provider: brand voice & clinical compliance >= 4.0/5.0",
        type: "llm_judge",
        config: { judge_profile: "gemini-1.5-pro", min_score: 4.0 },
      },
      {
        id: "c-5",
        description: "Human operator review & publishing approval",
        type: "human",
        config: { channel: "telegram" },
      },
    ],
    verdicts: [
      {
        check_id: "c-1",
        type: "artifact",
        status: "pass",
        evidence: "3 variants created in artifacts/variants.json.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-2",
        type: "command",
        status: "pass",
        evidence: "verify_images.py exit 0: 3 assets verified.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-3",
        type: "command",
        status: "fail",
        evidence: "check_banned_claims.py exit 1: Variant 2 contains banned term 'lose 30 lbs guaranteed'. FTC rule violation.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-4",
        type: "llm_judge",
        status: "pending",
        evidence: "Check halted due to prior deterministic failure.",
        cost_usd: 0.0,
      },
      {
        check_id: "c-5",
        type: "human",
        status: "pending",
        evidence: "Pending retry.",
        cost_usd: 0.0,
      },
    ],
  },
};

export const MOCK_RUN_EVENTS: Record<string, RunEvent[]> = {
  "run-102": [
    {
      id: "ev-1",
      run_id: "run-102",
      seq: 1,
      created_at: new Date(Date.now() - 94000).toISOString(),
      type: "run.started",
      payload: {
        task_id: "task-102",
        attempt: 2,
        agent: "creative-pack",
        previous_attempt_failure: "Variant 2 contained banned claim 'lose 30 lbs guaranteed'",
      },
    },
    {
      id: "ev-2",
      run_id: "run-102",
      seq: 2,
      created_at: new Date(Date.now() - 92000).toISOString(),
      type: "plan.created",
      payload: {
        goal: "Revise Variant 2 copy to remove guarantee; regenerate images and run compliance checks",
        steps: [
          "Load brand guardrails and FDA disclaimers",
          "Rewrite Variant 2 headline into compliant health benefit proposition",
          "Verify character counts and disclaimer footer",
          "Generate 1080x1080 image for revised variant",
          "Run deterministic compliance test suite",
          "Submit for LLM Judge scoring",
          "Request operator sign-off",
        ],
        criteria_count: 5,
      },
    },
    {
      id: "ev-3",
      run_id: "run-102",
      seq: 3,
      created_at: new Date(Date.now() - 88000).toISOString(),
      type: "memory.recalled",
      payload: {
        scope: "global",
        path: "compliance/fda_ftc_rules.md",
        facts: ["Weight-loss claims require 'results may vary' disclaimer", "Compounded products must not claim FDA-approved status"],
      },
    },
    {
      id: "ev-4",
      run_id: "run-102",
      seq: 4,
      created_at: new Date(Date.now() - 85000).toISOString(),
      type: "skill.loaded",
      payload: {
        skill_name: "creative-pack",
        description: "Ad copywriting with medical disclaimers and multi-variant image generation",
      },
    },
    {
      id: "ev-5",
      run_id: "run-102",
      seq: 5,
      created_at: new Date(Date.now() - 79000).toISOString(),
      type: "model.call",
      payload: {
        provider: "Groq",
        model: "llama-3.3-70b-versatile",
        tokens_in: 1250,
        tokens_out: 420,
        cost_usd: 0.00042,
        latency_ms: 412,
        messages_preview: "User: Rewrite variant 2 to eliminate 'guaranteed' and incorporate mandatory footer.",
      },
    },
    {
      id: "ev-6",
      run_id: "run-102",
      seq: 6,
      created_at: new Date(Date.now() - 76000).toISOString(),
      type: "tool.call",
      payload: {
        tool: "sandbox_write_file",
        args: {
          path: "variants.json",
          content_preview: '{"variant_2": {"headline": "Clinically-supported weight care tailored to you", "disclaimer": "*Results vary. Doctor consultation required."}}',
        },
      },
    },
    {
      id: "ev-7",
      run_id: "run-102",
      seq: 7,
      created_at: new Date(Date.now() - 74000).toISOString(),
      type: "tool.result",
      payload: {
        tool: "sandbox_write_file",
        output: "Wrote 384 bytes to /workspace/variants.json",
      },
    },
    {
      id: "ev-8",
      run_id: "run-102",
      seq: 8,
      created_at: new Date(Date.now() - 65000).toISOString(),
      type: "tool.call",
      payload: {
        tool: "generate_image",
        args: {
          prompt: "Professional modern medical wellness aesthetic, serene natural lighting, premium packaging mockup 1080x1080",
          model: "imagen-3.0",
        },
      },
    },
    {
      id: "ev-9",
      run_id: "run-102",
      seq: 9,
      created_at: new Date(Date.now() - 50000).toISOString(),
      type: "tool.result",
      payload: {
        tool: "generate_image",
        output: "Saved /workspace/artifacts/ad_variant_2.png (1080x1080, 842KB)",
      },
    },
    {
      id: "ev-10",
      run_id: "run-102",
      seq: 10,
      created_at: new Date(Date.now() - 42000).toISOString(),
      type: "tool.call",
      payload: {
        tool: "sandbox_exec",
        args: { command: "python check_banned_claims.py && python verify_images.py" },
      },
    },
    {
      id: "ev-11",
      run_id: "run-102",
      seq: 11,
      created_at: new Date(Date.now() - 38000).toISOString(),
      type: "tool.result",
      payload: {
        tool: "sandbox_exec",
        output: "All 3 variants passed claims check. 3 images verified at 1080x1080. Exit code 0.",
      },
    },
    {
      id: "ev-12",
      run_id: "run-102",
      seq: 12,
      created_at: new Date(Date.now() - 30000).toISOString(),
      type: "check.result",
      payload: {
        check_id: "c-3",
        status: "pass",
        evidence: "Deterministic banned-claims test passed with 0 warnings.",
      },
    },
    {
      id: "ev-13",
      run_id: "run-102",
      seq: 13,
      created_at: new Date(Date.now() - 25000).toISOString(),
      type: "model.call",
      payload: {
        provider: "Google",
        model: "gemini-1.5-pro",
        capability: "llm_judge",
        cost_usd: 0.0024,
        latency_ms: 1280,
        judge_verdict: "Score 4.8/5.0. Meets medical accuracy, tone, and formatting constraints.",
      },
    },
    {
      id: "ev-14",
      run_id: "run-102",
      seq: 14,
      created_at: new Date(Date.now() - 20000).toISOString(),
      type: "check.result",
      payload: {
        check_id: "c-4",
        status: "pass",
        score: 4.8,
        evidence: "LLM Judge passed (4.8 >= 4.0 threshold).",
      },
    },
    {
      id: "ev-15",
      run_id: "run-102",
      seq: 15,
      created_at: new Date(Date.now() - 15000).toISOString(),
      type: "approval.requested",
      payload: {
        approval_id: "app-842",
        question: "Approve publishing 3 creative variants to Meta Ad Manager staging campaign?",
      },
    },
    {
      id: "ev-16",
      run_id: "run-102",
      seq: 16,
      created_at: new Date(Date.now() - 8000).toISOString(),
      type: "approval.decided",
      payload: {
        approval_id: "app-842",
        decision: "approved",
        decided_by: "@operator (Telegram)",
      },
    },
    {
      id: "ev-17",
      run_id: "run-102",
      seq: 17,
      created_at: new Date(Date.now() - 5000).toISOString(),
      type: "memory.saved",
      payload: {
        scope: "project",
        content: "Campaign Q4 oral weight-loss variants 1-3 approved and archived.",
      },
    },
    {
      id: "ev-18",
      run_id: "run-102",
      seq: 18,
      created_at: new Date(Date.now() - 2000).toISOString(),
      type: "run.finished",
      payload: {
        status: "succeeded",
        checks_passed: 5,
        checks_total: 5,
        total_cost_usd: 0.0342,
        total_duration_sec: 92,
      },
    },
  ],
};

export const MOCK_ARTIFACTS: Record<string, Artifact[]> = {
  "run-102": [
    {
      id: "art-1",
      run_id: "run-102",
      path: "artifacts/ad_variant_1.png",
      kind: "image",
      size: 894210,
      url: "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=1080&h=1080&fit=crop",
      content_preview: "1080x1080 PNG image",
    },
    {
      id: "art-2",
      run_id: "run-102",
      path: "artifacts/ad_variant_2.png",
      kind: "image",
      size: 914020,
      url: "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1080&h=1080&fit=crop",
      content_preview: "1080x1080 PNG image",
    },
    {
      id: "art-3",
      run_id: "run-102",
      path: "artifacts/ad_copy_matrix.md",
      kind: "markdown",
      size: 2450,
      url: "#",
      content_preview: `# Q4 Oral Weight-Loss Ad Copy Matrix

## Variant 1: Science-Backed Lifestyle
- **Headline**: Personalized Weight Care Designed by Doctors
- **Body**: Sustainable weight management with ongoing clinical support. Check your eligibility in 3 minutes.
- **Disclaimer**: *Prescription products require online consultation. Results may vary.*

## Variant 2: Daily Habit Focus
- **Headline**: Real Support for Real Weight Goals
- **Body**: Modern, evidence-based medication paired with registered dietitian coaching.
- **Disclaimer**: *Consult physician. Independent results vary by individual.*

## Variant 3: Simplicity & Transparency
- **Headline**: Transparent Care. Zero Hidden Fees.
- **Body**: Complete oral treatment plans delivered directly to your door with doctor follow-ups included.
- **Disclaimer**: *See safety info and program details online.*
`,
    },
    {
      id: "art-4",
      run_id: "run-102",
      path: "artifacts/campaign_spec.json",
      kind: "json",
      size: 1420,
      url: "#",
      content_preview: `{
  "campaign_name": "Q4_Oral_Weight_Loss_Staging",
  "objective": "CONVERSIONS",
  "target_audience": "US_25_55_Health_Wellness",
  "budget_daily_usd": 150.00,
  "creative_count": 3,
  "disclaimer_verified": true,
  "ftc_compliant": true
}`,
    },
    {
      id: "art-5",
      run_id: "run-102",
      path: "artifacts/audio_voiceover_preview.mp3",
      kind: "audio",
      size: 1420500,
      url: "https://actions.google.com/sounds/v1/water/rain_heavy.ogg",
      content_preview: "Groq TTS Orpheus Preview (28s, 44.1kHz)",
    },
  ],
};

export const MOCK_AGENTS: AgentDefinition[] = [
  {
    id: "planner",
    name: "planner",
    description: "Turns high-level user tasks into decomposed step plans and deterministic acceptance criteria.",
    instructions: `# Planner Agent

You are the Planner agent in Agent0. Your purpose is to convert incoming user goals into:
1. Clear, non-overlapping sequential steps.
2. An upfront list of acceptance criteria (typed checks) created BEFORE any work starts.
3. Strict verification standards: favor deterministic command/artifact checks before any LLM judge call.
`,
    model_profile: "gemini-2.5-flash",
    tool_count: 4,
    runs_7d: 142,
    success_rate: 98.6,
    avg_cost: 0.0021,
    tools: [
      { name: "read_knowledge", permission: "safe", description: "Access connected docs and specs" },
      { name: "recall_memory", permission: "safe", description: "Recall historical facts & past runs" },
      { name: "inspect_workspace", permission: "safe", description: "List files in repo" },
      { name: "ask_clarification", permission: "safe", description: "Ask operator questions" },
    ],
    budgets: { max_usd: 0.1, max_steps: 8 },
    versions: [
      { version: 3, updated_at: "2026-11-16T12:00:00Z", author: "admin" },
      { version: 2, updated_at: "2026-11-10T09:30:00Z", author: "admin" },
      { version: 1, updated_at: "2026-11-01T15:20:00Z", author: "admin" },
    ],
  },
  {
    id: "executor",
    name: "executor",
    description: "General execution agent that runs tools inside Docker/E2B sandboxes.",
    instructions: `# Executor Agent

You execute tasks in the sandboxed runtime.
- Never write credentials into files or code.
- Always check return codes of shell commands.
- Report specific outputs concisely to save context tokens.
`,
    model_profile: "groq-llama-3.3-70b",
    tool_count: 8,
    runs_7d: 310,
    success_rate: 94.2,
    avg_cost: 0.0185,
    tools: [
      { name: "sandbox_exec", permission: "safe", description: "Run bash commands in sandbox" },
      { name: "sandbox_read_file", permission: "safe", description: "Read sandbox files" },
      { name: "sandbox_write_file", permission: "safe", description: "Write files in sandbox" },
      { name: "web_fetch", permission: "safe", description: "HTTP GET web pages" },
      { name: "browser_playwright", permission: "safe", description: "Automate browser actions" },
      { name: "send_email", permission: "needs_approval", description: "Send outbound emails" },
      { name: "deploy_service", permission: "needs_approval", description: "Push to staging or prod" },
      { name: "destructive_rm", permission: "forbidden", description: "Permanent deletion" },
    ],
    budgets: { max_usd: 1.0, max_steps: 30 },
  },
  {
    id: "verifier",
    name: "verifier",
    description: "Evaluates acceptance criteria independently from the executor; grades rubrics using secondary models.",
    instructions: `# Verifier Agent

You evaluate whether a run succeeded.
- Run deterministic checks first (command exit codes, artifact presence).
- When an LLM judge is required, you must always evaluate on an independent model provider.
- Output structured Verdict objects with clear failure evidence.
`,
    model_profile: "gemini-1.5-pro",
    tool_count: 5,
    runs_7d: 215,
    success_rate: 99.1,
    avg_cost: 0.0035,
    tools: [
      { name: "run_check_command", permission: "safe", description: "Execute test suites" },
      { name: "check_artifact_schema", permission: "safe", description: "Validate JSON/Pydantic schemas" },
      { name: "check_image_spec", permission: "safe", description: "Verify dimensions & color profiles" },
      { name: "llm_rubric_eval", permission: "safe", description: "Run multi-point judge rubric" },
      { name: "request_human_approval", permission: "safe", description: "Route approval to Telegram/UI" },
    ],
    budgets: { max_usd: 0.25, max_steps: 10 },
  },
  {
    id: "creative-pack",
    name: "creative-pack",
    description: "Generates multi-variant marketing collateral, copy, and graphics strictly following healthcare compliance.",
    instructions: `# Creative Pack Agent

Specialized pack for ad creation with regulatory compliance (FTC/FDA).
- Enforce mandatory disclaimers.
- Produce 1080x1080 image assets.
- Generate variants in parallel.
`,
    model_profile: "groq-llama-3.3-70b",
    tool_count: 6,
    runs_7d: 88,
    success_rate: 96.5,
    avg_cost: 0.031,
    tools: [
      { name: "generate_copy_variants", permission: "safe", description: "Generate structured ad copy" },
      { name: "generate_image", permission: "safe", description: "Generate photorealistic assets" },
      { name: "check_banned_claims", permission: "safe", description: "Scan text for banned FTC/FDA claims" },
      { name: "publish_campaign_staging", permission: "needs_approval", description: "Upload to staging ad manager" },
    ],
    budgets: { max_usd: 1.5, max_steps: 25 },
  },
];

export const MOCK_MODEL_PROFILES: ModelProfile[] = [
  {
    id: "groq-llama-3.3-70b",
    name: "Groq Llama 3.3 70B",
    provider: "Groq",
    model: "llama-3.3-70b-versatile",
    capability: "chat",
    tags: ["fast", "cheap", "smart"],
    cost: { input_per_mtok: 0.59, output_per_mtok: 0.79 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 1420, pass_rate: 97.4, avg_cost: 0.00062, avg_latency_ms: 380, error_rate: 0.2 },
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    provider: "Google",
    model: "gemini-2.5-flash",
    capability: "chat",
    tags: ["fast", "smart", "multimodal"],
    cost: { input_per_mtok: 0.35, output_per_mtok: 1.05 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 2150, pass_rate: 98.9, avg_cost: 0.00085, avg_latency_ms: 450, error_rate: 0.1 },
  },
  {
    id: "gemini-1.5-pro",
    name: "Gemini 1.5 Pro (Judge)",
    provider: "Google",
    model: "gemini-1.5-pro",
    capability: "chat",
    tags: ["smart", "high-reasoning"],
    cost: { input_per_mtok: 1.25, output_per_mtok: 5.0 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 410, pass_rate: 99.5, avg_cost: 0.0042, avg_latency_ms: 1120, error_rate: 0.0 },
  },
  {
    id: "gemini-vision-2.5",
    name: "Gemini 2.5 Vision",
    provider: "Google",
    model: "gemini-2.5-flash",
    capability: "vision",
    tags: ["multimodal", "fast"],
    cost: { input_per_mtok: 0.35, output_per_mtok: 1.05 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 280, pass_rate: 98.2, avg_cost: 0.0012, avg_latency_ms: 620, error_rate: 0.4 },
  },
  {
    id: "imagen-3.0",
    name: "Google Imagen 3.0",
    provider: "Google",
    model: "imagen-3.0-generate-002",
    capability: "image_gen",
    tags: ["photorealistic", "commercial-ready"],
    cost: { per_image: 0.03 },
    key_configured: true,
    enabled: true,
    key_env_var: "GEMINI_API_KEY",
    stats: { calls_7d: 112, pass_rate: 96.4, avg_cost: 0.03, avg_latency_ms: 3800, error_rate: 1.1 },
  },
  {
    id: "veo-2",
    name: "Google Veo 2 (Video Gen)",
    provider: "Google",
    model: "veo-2.0-generate-001",
    capability: "video_gen",
    tags: ["cinematic", "high-definition"],
    cost: { per_video: 0.35 },
    key_configured: true,
    enabled: true,
    key_env_var: "GEMINI_API_KEY",
    stats: { calls_7d: 34, pass_rate: 94.1, avg_cost: 0.35, avg_latency_ms: 14200, error_rate: 2.9 },
  },
  {
    id: "runway-gen3",
    name: "Runway Gen-3 Alpha",
    provider: "Runway",
    model: "gen3a_turbo",
    capability: "video_gen",
    tags: ["fast", "stylized"],
    cost: { per_video: 0.25 },
    key_configured: true,
    enabled: true,
    key_env_var: "RUNWAY_API_KEY",
    stats: { calls_7d: 28, pass_rate: 96.4, avg_cost: 0.25, avg_latency_ms: 8900, error_rate: 1.8 },
  },
  {
    id: "elevenlabs-v2",
    name: "ElevenLabs Multilingual v2",
    provider: "ElevenLabs",
    model: "eleven_multilingual_v2",
    capability: "tts",
    tags: ["hyper-realistic", "emotive"],
    cost: { per_1k_chars: 0.003 },
    key_configured: true,
    enabled: true,
    key_env_var: "ELEVENLABS_API_KEY",
    stats: { calls_7d: 82, pass_rate: 98.8, avg_cost: 0.0028, avg_latency_ms: 650, error_rate: 0.0 },
  },
  {
    id: "groq-whisper",
    name: "Groq Whisper Large v3",
    provider: "Groq",
    model: "whisper-large-v3",
    capability: "stt",
    tags: ["fast", "cheap"],
    cost: { per_1k_chars: 0.0001 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 95, pass_rate: 99.0, avg_cost: 0.0002, avg_latency_ms: 220, error_rate: 0.0 },
  },
  {
    id: "groq-tts",
    name: "Groq Orpheus TTS",
    provider: "Groq",
    model: "orpheus-tts-1",
    capability: "tts",
    tags: ["natural", "fast"],
    cost: { per_1k_chars: 0.0015 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 64, pass_rate: 98.4, avg_cost: 0.0018, avg_latency_ms: 410, error_rate: 0.0 },
  },
  {
    id: "gemini-embedding-004",
    name: "Gemini Text Embedding 004",
    provider: "Google",
    model: "text-embedding-004",
    capability: "embedding",
    tags: ["dense", "cheap"],
    cost: { input_per_mtok: 0.08 },
    key_configured: true,
    enabled: true,
    stats: { calls_7d: 3400, pass_rate: 100.0, avg_cost: 0.00008, avg_latency_ms: 140, error_rate: 0.0 },
  },
];

export const MOCK_USAGE_RECORDS: UsageRecord[] = [
  {
    id: "usg-101",
    run_id: "run-102",
    profile: "groq-llama-3.3-70b",
    provider: "Groq",
    model: "llama-3.3-70b-versatile",
    capability: "chat",
    input_units: 1250,
    output_units: 420,
    cost_usd: 0.00042,
    latency_ms: 412,
    ok: true,
    created_at: new Date(Date.now() - 79000).toISOString(),
  },
  {
    id: "usg-102",
    run_id: "run-102",
    profile: "gemini-1.5-pro",
    provider: "Google",
    model: "gemini-1.5-pro",
    capability: "chat",
    input_units: 1620,
    output_units: 380,
    cost_usd: 0.0024,
    latency_ms: 1280,
    ok: true,
    created_at: new Date(Date.now() - 25000).toISOString(),
  },
  {
    id: "usg-103",
    run_id: "run-102",
    profile: "imagen-3.0",
    provider: "Google",
    model: "imagen-3.0-generate-002",
    capability: "image_gen",
    input_units: 1,
    output_units: 1,
    cost_usd: 0.03,
    latency_ms: 3800,
    ok: true,
    created_at: new Date(Date.now() - 50000).toISOString(),
  },
  {
    id: "usg-104",
    run_id: "run-205",
    profile: "gemini-2.5-flash",
    provider: "Google",
    model: "gemini-2.5-flash",
    capability: "chat",
    input_units: 3200,
    output_units: 820,
    cost_usd: 0.00198,
    latency_ms: 480,
    ok: true,
    created_at: new Date(Date.now() - 150000).toISOString(),
  },
  {
    id: "usg-105",
    run_id: "run-301",
    profile: "groq-llama-3.3-70b",
    provider: "Groq",
    model: "llama-3.3-70b-versatile",
    capability: "chat",
    input_units: 1800,
    output_units: 600,
    cost_usd: 0.00058,
    latency_ms: 395,
    ok: true,
    created_at: new Date(Date.now() - 500000).toISOString(),
  },
];

export const MOCK_EXTENSIONS: Extension[] = [
  {
    id: "ext-skill-creative",
    kind: "skill",
    name: "creative-pack",
    description: "Marketing copy generation, FTC/FDA compliance checking, and multi-format ad generation.",
    enabled: true,
    source_path: "skills/creative-pack/SKILL.md",
    runs_count: 88,
    config: { max_variants: 5 },
    content_markdown: `# Creative Pack Skill
Generates high-performing, regulatory-compliant copy and image assets.
## Features
- Banned claim scanning against FDA and FTC rules
- Auto-insertion of medical disclaimer footers
- Aspect ratio conformance verification
`,
  },
  {
    id: "ext-mcp-postgres",
    kind: "mcp",
    name: "postgres-replica",
    description: "Read-only connection to production database replica for certified analytics metrics.",
    enabled: true,
    status: "connected",
    tools: ["sql_query", "list_tables", "describe_schema"],
    config: { host: "db-replica.internal", port: 5432, ssl: true },
  },
  {
    id: "ext-mcp-github",
    kind: "mcp",
    name: "github-enterprise",
    description: "GitHub MCP server for pull request reviews, repository inspection, and CI triggers.",
    enabled: true,
    status: "connected",
    tools: ["get_file", "search_code", "create_pull_request", "list_commits"],
    config: { org: "agent0-org" },
  },
  {
    id: "ext-plugin-analytics",
    kind: "plugin",
    name: "analytics-pack",
    description: "Complete analytical plugin bundle: SQL tools, metric definitions, and verification rubrics.",
    enabled: true,
    bundles: ["Agent: analytics-agent", "Skill: sql-certified-metrics", "MCP: postgres-replica"],
    config: { enforce_certified_metrics: true },
  },
];

export const MOCK_MEMORY_DOCS: MemoryDoc[] = [
  {
    id: "mem-1",
    scope: "global",
    path: "compliance/ftc_fda_guidelines.md",
    content: `# FTC & FDA Advertising Compliance Rules

1. **No Absolute Guarantees**: Never use the words "guaranteed", "100% cure", or "effortless weight loss".
2. **Mandatory Disclaimer**: Every weight care product advertisement must feature: *"Consult your physician. Results may vary."*
3. **Compounded Medication Restrictions**: Under 503A/503B rules, compounded medications cannot claim "FDA Approved" status.
`,
    revision: 4,
    updated_at: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
  {
    id: "mem-2",
    scope: "agent",
    scope_id: "creative-pack",
    path: "brand_voice.md",
    content: `# Northwind Health — Brand Voice & Tone

- **Empowering, not shameful**: Focus on vitality, long-term metabolic health, and personal agency.
- **Clinically grounded**: Reference board-certified clinicians and registered dietitians.
- **Tone adjectives**: Warm, transparent, measured, optimistic.
`,
    revision: 2,
    updated_at: new Date(Date.now() - 3600000 * 72).toISOString(),
  },
  {
    id: "mem-3",
    scope: "project",
    path: "certified_metrics.md",
    content: `# Certified Analytics Metrics

- **CAC**: (Total Marketing Ad Spend + Agency Fees) / New First-Time Subscriptions.
- **LTV 90d**: Cumulative gross margin collected per customer through day 90.
- **ROAS**: Attributed conversion revenue / platform ad spend.
`,
    revision: 5,
    updated_at: new Date(Date.now() - 3600000 * 24).toISOString(),
  },
];

export const MOCK_SCHEDULES: Schedule[] = [
  {
    id: "sch-1",
    agent: "ops-agent",
    cron: "0 8 * * *",
    cron_readable: "Every day at 08:00 UTC",
    prompt: "Sync distribution center inventory, check stock safety thresholds, and draft purchase orders.",
    enabled: true,
    last_run: new Date(Date.now() - 3600000 * 8).toISOString(),
    next_run: new Date(Date.now() + 3600000 * 16).toISOString(),
  },
  {
    id: "sch-2",
    agent: "analytics-agent",
    cron: "0 9 * * 1",
    cron_readable: "Every Monday at 09:00 UTC",
    prompt: "Calculate weekly CAC, LTV, and churn per channel and post executive digest to Slack #leadership.",
    enabled: true,
    last_run: new Date(Date.now() - 3600000 * 24 * 3).toISOString(),
    next_run: new Date(Date.now() + 3600000 * 24 * 4).toISOString(),
  },
  {
    id: "sch-3",
    agent: "executor",
    cron: "*/30 * * * *",
    cron_readable: "Every 30 minutes",
    prompt: "Scan external provider endpoints and verify webhook delivery latency is under 500ms.",
    enabled: false,
    last_run: new Date(Date.now() - 3600000 * 36).toISOString(),
  },
];
