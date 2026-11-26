// Typed client for the agent0 API (spec section 5). Every call goes through apiFetch (lib/http.ts)
// and therefore the server-side proxy; mock mode is handled by the proxy, not here.
// Functions keep the shapes the pages were built against and adapt the backend wire format
// (paginated envelopes, null-for-missing, renamed fields) at this boundary.
import type {
  AgentDefinition,
  Approval,
  Artifact,
  Criterion,
  EventFilters,
  Extension,
  ExtensionTestResult,
  MemoryDoc,
  MemoryFact,
  ModelProfile,
  OverviewStats,
  Paginated,
  RouterPreview,
  Run,
  RunEvent,
  RunVerify,
  Schedule,
  ScheduleInput,
  SecretItem,
  SecretTestResult,
  Task,
  ToolPermission,
  UsageFilters,
  UsageGroupBy,
  UsageRecord,
  UsageSummary,
  Verdict,
} from "@/types";
import { ApiError, apiFetch, proxyUrl } from "./http";

// ---------------------------------------------------------------- helpers

type Raw = Record<string, any>;

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== "all") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

const enc = encodeURIComponent;
const post = (body?: unknown): RequestInit => ({ method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = (body: unknown): RequestInit => ({ method: "PUT", body: JSON.stringify(body) });

/** Fetch every page of a list endpoint (follows next_cursor). Bounded to avoid runaway loops. */
async function listAll<T = Raw>(path: string, params: Record<string, string | number | boolean | undefined> = {}, maxPages = 20): Promise<T[]> {
  const out: T[] = [];
  let cursor: string | undefined;
  for (let i = 0; i < maxPages; i++) {
    const res = await apiFetch<Paginated<T>>(`${path}${qs({ limit: 200, ...params, cursor })}`);
    out.push(...res.items);
    if (!res.next_cursor) break;
    cursor = res.next_cursor;
  }
  return out;
}

const orUndef = <T,>(v: T | null | undefined): T | undefined => (v === null ? undefined : v);

function mapRun(r: Raw): Run {
  return { ...(r as Run), current_step: orUndef(r.current_step), ended_at: orUndef(r.ended_at) };
}

function mapTask(t: Raw): Task {
  const latest = t.latest_run ? mapRun(t.latest_run) : null;
  return {
    ...(t as Task),
    latest_run: latest,
    checks_total: latest?.checks_total,
    checks_passed: latest?.checks_passed,
    cost_usd: latest?.cost_usd,
  };
}

function mapApproval(a: Raw): Approval {
  return {
    ...(a as Approval),
    decided_by: orUndef(a.decided_by),
    decided_at: orUndef(a.decided_at),
    note: orUndef(a.note),
  };
}

function mapVerdict(v: Raw): Verdict {
  return { ...(v as Verdict), score: orUndef(v.score) };
}

function mapArtifact(a: Raw): Artifact {
  // Backend urls are /api/v1/...; the browser must reach them via the proxy.
  const url = typeof a.url === "string" ? proxyUrl(a.url.replace(/^\/api\/v1\//, "")) : a.url;
  return { ...(a as Artifact), url };
}

function mapProfile(p: Raw): ModelProfile {
  return { ...(p as ModelProfile), key_env_var: p.key_env_var ?? p.key_env ?? undefined };
}

const PERMISSIONS = new Set(["safe", "needs_approval", "forbidden"]);

function mapAgent(a: Raw): AgentDefinition {
  const policy: Raw = a.policy ?? {};
  const tools: ToolPermission[] = (a.tools ?? []).map((t: string | ToolPermission) => {
    if (typeof t !== "string") return t;
    const p = policy[t];
    return { name: t, permission: (PERMISSIONS.has(p) ? p : "safe") as ToolPermission["permission"] };
  });
  const rate = typeof a.success_rate === "number" ? a.success_rate : null;
  return {
    id: a.id ?? a.name,
    name: a.name,
    description: a.description ?? "",
    instructions: a.instructions ?? "",
    model_profile: a.model_profile ?? "",
    tool_count: a.tool_count ?? tools.length,
    runs_7d: a.runs_7d ?? 0,
    // Backend reports a 0..1 fraction (or null with no finished runs); the UI shows a percentage.
    success_rate: rate === null ? 0 : Math.round(rate * 1000) / 10,
    avg_cost: a.avg_cost ?? a.avg_cost_usd ?? 0,
    tools,
    budgets: a.budgets ?? a.budget ?? {},
    versions: a.versions,
  };
}

function mapExtension(e: Raw): Extension {
  const cfg: Raw = e.config ?? {};
  return {
    ...(e as Extension),
    source_path: e.source_path ?? cfg.path,
    runs_count: e.runs_count ?? cfg.runs_count,
    tools: e.tools ?? cfg.tools,
    bundles: e.bundles ?? cfg.bundles,
    content_markdown: e.content_markdown ?? cfg.content_markdown,
  };
}

function cronReadable(cron: string): string {
  const [min, hour, dom, mon, dow] = cron.trim().split(/\s+/);
  if (cron.trim().split(/\s+/).length !== 5) return cron;
  const pad = (n: string) => n.padStart(2, "0");
  const time = /^\d+$/.test(min) && /^\d+$/.test(hour) ? `${pad(hour)}:${pad(min)} UTC` : null;
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  if (time && dom === "*" && mon === "*" && dow === "*") return `Every day at ${time}`;
  if (time && dom === "*" && mon === "*" && /^[0-6]$/.test(dow)) return `Every ${days[Number(dow)]} at ${time}`;
  if (min.startsWith("*/") && hour === "*") return `Every ${min.slice(2)} minutes`;
  return cron;
}

function mapSchedule(s: Raw): Schedule {
  return {
    id: s.id,
    agent: s.agent,
    cron: s.cron,
    cron_readable: s.cron_readable ?? cronReadable(s.cron),
    prompt: s.prompt,
    enabled: !!s.enabled,
    last_run: s.last_run ?? orUndef(s.last_run_at),
    next_run: orUndef(s.next_run),
  };
}

// ---------------------------------------------------------------- stats

export async function getOverviewStats(): Promise<OverviewStats> {
  const s = await apiFetch<Raw>("/stats/overview");
  return {
    running_now: s.running_now ?? s.running ?? 0,
    waiting_approval: s.waiting_approval ?? 0,
    succeeded_24h: s.succeeded_24h ?? 0,
    failed_24h: s.failed_24h ?? 0,
    spend_today_usd: s.spend_today_usd ?? 0,
  };
}

// ---------------------------------------------------------------- tasks

export async function getTasks(filters?: {
  status?: string;
  agent?: string;
  source?: string;
  q?: string;
  from?: string;
  to?: string;
}): Promise<Task[]> {
  const items = await listAll("/tasks", { ...filters });
  return items.map(mapTask);
}

export async function getTask(id: string): Promise<{ task: Task; runs: Run[] } | null> {
  try {
    const res = await apiFetch<Raw>(`/tasks/${enc(id)}`);
    return { task: mapTask(res.task), runs: (res.runs ?? []).map(mapRun) };
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function createTask(payload: {
  title?: string;
  prompt: string;
  agent: string;
  notify_level: "final_only" | "milestones" | "everything";
  budget?: { max_usd?: number; max_steps?: number; max_minutes?: number };
  criteria?: Record<string, unknown>[];
}): Promise<{ task: Task; run: Run }> {
  const res = await apiFetch<Raw>("/tasks", post(payload));
  return { task: mapTask(res.task), run: mapRun(res.run) };
}

export async function retryTask(taskId: string): Promise<{ task: Task; run: Run }> {
  const res = await apiFetch<Raw>(`/tasks/${enc(taskId)}/retry`, post());
  const detail = await getTask(taskId);
  return { task: detail!.task, run: mapRun(res.run) };
}

// ---------------------------------------------------------------- runs

export async function getRuns(filters?: { status?: string; task_id?: string }): Promise<Run[]> {
  return (await listAll("/runs", { ...filters })).map(mapRun);
}

const LIVE = new Set(["planning", "executing", "verifying", "waiting_approval"]);

export async function getLiveRuns(): Promise<Run[]> {
  // The backend filters by a single status, so fetch recent runs and keep the live ones.
  const res = await apiFetch<Paginated<Raw>>(`/runs${qs({ limit: 200 })}`);
  return res.items.map(mapRun).filter((r) => LIVE.has(r.status));
}

async function getRunDetail(id: string): Promise<Raw | null> {
  try {
    return await apiFetch<Raw>(`/runs/${enc(id)}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function getRun(id: string): Promise<Run | null> {
  const d = await getRunDetail(id);
  return d ? mapRun(d.run) : null;
}

export async function getRunCriteriaAndVerdicts(runId: string): Promise<{
  criteria: Criterion[];
  verdicts: Verdict[];
}> {
  const d = await getRunDetail(runId);
  return {
    criteria: (d?.spec?.criteria ?? []) as Criterion[],
    verdicts: (d?.verdicts ?? []).map(mapVerdict),
  };
}

export async function getRunArtifacts(runId: string): Promise<Artifact[]> {
  const d = await getRunDetail(runId);
  return (d?.artifacts ?? []).map(mapArtifact);
}

export async function getRunEvents(runId: string, afterSeq = 0): Promise<RunEvent[]> {
  const out: RunEvent[] = [];
  let after = afterSeq;
  for (let i = 0; i < 20; i++) {
    const res = await apiFetch<Paginated<RunEvent>>(`/runs/${enc(runId)}/events${qs({ after_seq: after, limit: 500 })}`);
    out.push(...res.items);
    if (!res.next_cursor) break;
    after = Number(res.next_cursor);
  }
  return out;
}

export async function getRunVerify(runId: string): Promise<RunVerify> {
  return apiFetch<RunVerify>(`/runs/${enc(runId)}/verify`);
}

export async function getRunReceipt(runId: string): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(`/runs/${enc(runId)}/receipt`);
}

export async function stopRun(runId: string): Promise<{ success: boolean }> {
  await apiFetch(`/runs/${enc(runId)}/stop`, post());
  return { success: true };
}

/** Global activity feed history (live updates: useEventStream("/stream")). */
export async function getEvents(filters?: EventFilters): Promise<RunEvent[]> {
  const res = await apiFetch<Paginated<RunEvent>>(`/events${qs({ limit: 100, ...filters })}`);
  return res.items;
}

// ---------------------------------------------------------------- approvals

export async function getApprovals(status?: "pending" | "approved" | "rejected"): Promise<Approval[]> {
  return (await listAll("/approvals", { status })).map(mapApproval);
}

export async function decideApproval(id: string, decision: "approve" | "reject", note?: string): Promise<Approval> {
  return mapApproval(await apiFetch<Raw>(`/approvals/${enc(id)}`, post({ decision, note })));
}

// ---------------------------------------------------------------- agents

export async function getAgents(): Promise<AgentDefinition[]> {
  return (await listAll("/agents")).map(mapAgent);
}

export async function getAgent(name: string): Promise<AgentDefinition | null> {
  try {
    const [raw, versions] = await Promise.all([
      apiFetch<Raw>(`/agents/${enc(name)}`),
      apiFetch<Paginated<Raw>>(`/agents/${enc(name)}/versions`).catch(() => null),
    ]);
    const agent = mapAgent(raw);
    if (versions && !agent.versions) {
      agent.versions = versions.items.map((v) => ({
        version: v.version,
        updated_at: v.updated_at ?? "",
        author: v.author ?? v.source ?? "",
      }));
    }
    return agent;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export async function updateAgent(name: string, payload: Partial<AgentDefinition>): Promise<AgentDefinition> {
  return mapAgent(await apiFetch<Raw>(`/agents/${enc(name)}`, put(payload)));
}

export async function createAgent(payload: Partial<AgentDefinition> & { name: string }): Promise<AgentDefinition> {
  return mapAgent(await apiFetch<Raw>("/agents", post(payload)));
}

// ---------------------------------------------------------------- models, router, usage

export async function getModelProfiles(capability?: string): Promise<ModelProfile[]> {
  return (await listAll("/model-profiles", { capability })).map(mapProfile);
}

export async function createModelProfile(payload: Partial<ModelProfile> & { name: string }): Promise<ModelProfile> {
  return mapProfile(await apiFetch<Raw>("/model-profiles", post(payload)));
}

export async function updateModelProfile(id: string, payload: Partial<ModelProfile>): Promise<ModelProfile> {
  return mapProfile(await apiFetch<Raw>(`/model-profiles/${enc(id)}`, put(payload)));
}

export async function deleteModelProfile(id: string): Promise<void> {
  await apiFetch<void>(`/model-profiles/${enc(id)}`, { method: "DELETE" });
}

export async function getRouterPreview(
  capability: string,
  prefer: "cheap" | "fast" | "smart",
): Promise<{ profile: ModelProfile; reason: string }> {
  const res = await apiFetch<Raw>(`/router/preview${qs({ capability, prefer })}`);
  // `profile` is null when no enabled profile has a key; kept in the type for callers that handle it.
  return { profile: res.profile ? mapProfile(res.profile) : (null as unknown as ModelProfile), reason: res.reason };
}

/** Same call as getRouterPreview but with the honest nullable return type. */
export async function previewRoute(capability: string, prefer: "cheap" | "fast" | "smart"): Promise<RouterPreview> {
  const res = await getRouterPreview(capability, prefer);
  return { profile: res.profile ?? null, reason: res.reason };
}

export async function getUsageRecords(filters?: UsageFilters): Promise<UsageRecord[]> {
  return listAll<UsageRecord>("/usage", { ...filters });
}

export async function getUsageSummary(filters?: UsageFilters & { group_by?: UsageGroupBy }): Promise<UsageSummary> {
  const { agent, capability, provider, ...rest } = filters ?? {};
  void agent; void capability; void provider; // the summary endpoint only filters by date range
  return apiFetch<UsageSummary>(`/usage/summary${qs({ group_by: "provider", ...rest })}`);
}

// ---------------------------------------------------------------- extensions

export async function getExtensions(kind?: "skill" | "mcp" | "plugin"): Promise<Extension[]> {
  return (await listAll("/extensions", { kind })).map(mapExtension);
}

export async function getExtension(id: string): Promise<Extension> {
  return mapExtension(await apiFetch<Raw>(`/extensions/${enc(id)}`));
}

export async function updateExtension(id: string, payload: { enabled: boolean }): Promise<Extension> {
  return mapExtension(await apiFetch<Raw>(`/extensions/${enc(id)}`, put(payload)));
}

export async function testExtension(id: string): Promise<ExtensionTestResult> {
  return apiFetch<ExtensionTestResult>(`/extensions/${enc(id)}/test`, post());
}

export async function testMcpConnection(id: string): Promise<{ success: boolean; latency_ms: number; message: string }> {
  const started = performance.now();
  const r = await testExtension(id);
  return {
    success: r.ok,
    latency_ms: Math.round(performance.now() - started),
    message: r.ok ? `Connected. ${r.tools.length} tool(s) discovered.` : (r.error ?? "Connection failed"),
  };
}

// ---------------------------------------------------------------- secrets (values are write-only)

export async function getSecrets(): Promise<SecretItem[]> {
  return listAll<SecretItem>("/secrets");
}

/** Store or replace a key. The value is only ever in this request body; callers must clear their input. */
export async function setSecret(name: string, value: string): Promise<void> {
  await apiFetch(`/secrets/${enc(name)}`, put({ value }));
}

export async function deleteSecret(name: string): Promise<void> {
  await apiFetch(`/secrets/${enc(name)}`, { method: "DELETE" });
}

export async function testSecret(name: string): Promise<SecretTestResult> {
  return apiFetch<SecretTestResult>(`/secrets/${enc(name)}/test`, post());
}

// ---------------------------------------------------------------- memory (temporal facts)

export async function getMemoryFacts(opts?: {
  scope?: string;
  scope_id?: string;
  include_expired?: boolean;
}): Promise<MemoryFact[]> {
  return listAll<MemoryFact>("/memory", { ...opts });
}

export async function searchMemory(q: string): Promise<MemoryFact[]> {
  const res = await apiFetch<Paginated<MemoryFact>>(`/memory/search${qs({ q })}`);
  return res.items;
}

export async function getMemoryFact(id: string): Promise<MemoryFact> {
  return apiFetch<MemoryFact>(`/memory/${enc(id)}`);
}

/** Supersedes the fact: the old one is expired and the returned new fact replaces it. */
export async function editMemoryFact(id: string, content: string): Promise<MemoryFact> {
  return apiFetch<MemoryFact>(`/memory/${enc(id)}`, put({ content }));
}

/** Expires the fact (never hard-deleted). */
export async function forgetMemoryFact(id: string): Promise<void> {
  await apiFetch<void>(`/memory/${enc(id)}`, { method: "DELETE" });
}

export async function getMemoryRevisions(id: string): Promise<MemoryFact[]> {
  const res = await apiFetch<Paginated<MemoryFact>>(`/memory/${enc(id)}/revisions`);
  return res.items;
}

/** Legacy document view of facts for the current memory page. */
export async function getMemoryDocs(scope?: string, search?: string): Promise<MemoryDoc[]> {
  const facts = search ? await searchMemory(search) : await getMemoryFacts({ scope });
  return facts
    .filter((f) => !scope || scope === "all" || f.scope === scope)
    .map((f) => ({
      id: f.id,
      scope: f.scope,
      scope_id: f.scope_id ?? undefined,
      path: f.source_id || `${f.scope}${f.scope_id ? `/${f.scope_id}` : ""}/${f.id}`,
      content: f.content,
      revision: 1,
      updated_at: f.valid_from,
    }));
}

// ---------------------------------------------------------------- schedules

export async function getSchedules(): Promise<Schedule[]> {
  return (await listAll("/schedules")).map(mapSchedule);
}

export async function createSchedule(payload: ScheduleInput): Promise<Schedule> {
  return mapSchedule(await apiFetch<Raw>("/schedules", post(payload)));
}

export async function updateSchedule(id: string, payload: ScheduleInput): Promise<Schedule> {
  return mapSchedule(await apiFetch<Raw>(`/schedules/${enc(id)}`, put(payload)));
}

export async function deleteSchedule(id: string): Promise<void> {
  await apiFetch<void>(`/schedules/${enc(id)}`, { method: "DELETE" });
}

export async function toggleSchedule(id: string): Promise<Schedule> {
  const current = (await getSchedules()).find((s) => s.id === id);
  if (!current) throw new ApiError(404, "not_found", `schedule ${id} not found`);
  return updateSchedule(id, {
    agent: current.agent,
    cron: current.cron,
    prompt: current.prompt,
    enabled: !current.enabled,
  });
}

// ---------------------------------------------------------------- live streams

/**
 * Subscribe to a run's event stream. Thin wrapper over the shared SSE client in lib/sse.ts
 * (reconnect with backoff, Last-Event-ID resume, dedupe by run_id + seq). Returns an unsubscribe fn.
 */
export { subscribeToRunStream } from "./sse";
