export type RunStatus =
  | "pending"
  | "planning"
  | "executing"
  | "verifying"
  | "waiting_approval"
  | "succeeded"
  | "failed"
  | "stopped";

export interface Task {
  id: string;
  title: string;
  prompt: string;
  source: "telegram" | "slack" | "api" | "cli" | "schedule";
  agent: string;
  status: RunStatus;
  attempts: number;
  notify_level: "final_only" | "milestones" | "everything";
  budget: {
    max_usd?: number;
    max_steps?: number;
    max_minutes?: number;
  };
  created_at: string; // ISO
  checks_total?: number;
  checks_passed?: number;
  cost_usd?: number;
}

export interface Run {
  id: string;
  task_id: string;
  attempt: number;
  status: RunStatus;
  agent: string;
  model_profile: string;
  current_step?: string; // human-readable e.g. "Running pytest"
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  started_at: string;
  ended_at?: string;
  checks_total: number;
  checks_passed: number;
}

export type CriterionType =
  | "command"
  | "artifact"
  | "http"
  | "browser"
  | "llm_judge"
  | "human";

export interface Criterion {
  id: string;
  description: string;
  type: CriterionType;
  config: Record<string, unknown>;
}

export interface Verdict {
  check_id: string;
  type: CriterionType;
  status: "pending" | "pass" | "fail" | "error";
  evidence: string;
  score?: number;
  cost_usd: number;
}

export type RunEventType =
  | "run.started"
  | "plan.created"
  | "model.call"
  | "tool.call"
  | "tool.result"
  | "skill.loaded"
  | "memory.recalled"
  | "memory.saved"
  | "knowledge.read"
  | "check.result"
  | "approval.requested"
  | "approval.decided"
  | "budget.exceeded"
  | "error"
  | "run.finished";

export interface RunEvent {
  id: string;
  run_id: string;
  seq: number;
  created_at: string;
  type: RunEventType;
  payload: Record<string, unknown>;
}

export interface Approval {
  id: string;
  run_id: string;
  task_title?: string;
  question: string;
  options: string[];
  status: "pending" | "approved" | "rejected";
  decided_by?: string;
  decided_at?: string;
  note?: string;
}

export type Capability =
  | "chat"
  | "vision"
  | "image_gen"
  | "video_gen"
  | "tts"
  | "stt"
  | "embedding";

export interface ModelProfile {
  id: string;
  name: string;
  provider: string;
  model: string;
  capability: Capability;
  tags: string[];
  cost: {
    input_per_mtok?: number;
    output_per_mtok?: number;
    per_image?: number;
    per_video?: number;
    per_1k_chars?: number;
  };
  key_configured: boolean;
  enabled: boolean;
  key_env_var?: string;
  stats?: {
    calls_7d: number;
    pass_rate: number;
    avg_cost: number;
    avg_latency_ms: number;
    error_rate: number;
  };
}

export interface UsageRecord {
  id: string;
  run_id?: string;
  profile: string;
  provider: string;
  model: string;
  capability: Capability;
  input_units: number;
  output_units: number;
  cost_usd: number;
  latency_ms: number;
  ok: boolean;
  created_at: string;
}

export interface Extension {
  id: string;
  kind: "skill" | "mcp" | "plugin";
  name: string;
  description: string;
  enabled: boolean;
  status?: "connected" | "error" | "idle";
  source_path?: string;
  runs_count?: number;
  tools?: string[];
  bundles?: string[];
  config: Record<string, unknown>;
  content_markdown?: string;
}

export interface Artifact {
  id: string;
  run_id: string;
  path: string;
  kind: "image" | "audio" | "text" | "markdown" | "json" | "pdf" | "video" | "other";
  size: number;
  url: string;
  content_preview?: string;
}

export interface ToolPermission {
  name: string;
  permission: "safe" | "needs_approval" | "forbidden";
  description?: string;
}

export interface AgentDefinition {
  id: string;
  name: string;
  description: string;
  instructions: string;
  model_profile: string;
  tool_count: number;
  runs_7d: number;
  success_rate: number;
  avg_cost: number;
  tools: ToolPermission[];
  budgets: {
    max_usd?: number;
    max_steps?: number;
  };
  versions?: { version: number; updated_at: string; author: string }[];
}

export interface MemoryDoc {
  id: string;
  scope: "global" | "agent" | "project";
  scope_id?: string;
  path: string;
  content: string;
  revision: number;
  updated_at: string;
}

export interface Schedule {
  id: string;
  agent: string;
  cron: string;
  cron_readable: string;
  prompt: string;
  enabled: boolean;
  last_run?: string;
  next_run?: string;
}

export interface OverviewStats {
  running_now: number;
  waiting_approval: number;
  succeeded_24h: number;
  failed_24h: number;
  spend_today_usd: number;
}
