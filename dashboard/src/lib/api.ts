import type {
  OverviewStats,
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
} from "@/types";
import {
  MOCK_OVERVIEW_STATS,
  MOCK_APPROVALS,
  MOCK_TASKS,
  MOCK_RUNS,
  MOCK_CRITERIA_VERDICTS,
  MOCK_RUN_EVENTS,
  MOCK_ARTIFACTS,
  MOCK_AGENTS,
  MOCK_MODEL_PROFILES,
  MOCK_USAGE_RECORDS,
  MOCK_EXTENSIONS,
  MOCK_MEMORY_DOCS,
  MOCK_SCHEDULES,
} from "@/mocks/fixtures";

const isMock = process.env.NEXT_PUBLIC_MOCK === "1" || !process.env.NEXT_PUBLIC_API_URL;
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// In-memory mock state for live interactions without backend
let stateApprovals = [...MOCK_APPROVALS];
let stateTasks = [...MOCK_TASKS];
let stateRuns = { ...MOCK_RUNS };
let stateRunEvents = { ...MOCK_RUN_EVENTS };
let stateCriteriaVerdicts = { ...MOCK_CRITERIA_VERDICTS };
let stateAgents = [...MOCK_AGENTS];
let stateSchedules = [...MOCK_SCHEDULES];

export async function getOverviewStats(): Promise<OverviewStats> {
  if (isMock) {
    const pendingCount = stateApprovals.filter((a) => a.status === "pending").length;
    const runningCount = Object.values(stateRuns).filter((r) =>
      ["planning", "executing", "verifying"].includes(r.status)
    ).length;
    return {
      ...MOCK_OVERVIEW_STATS,
      waiting_approval: pendingCount,
      running_now: runningCount,
    };
  }
  const res = await fetch(`${API_BASE}/stats/overview`);
  return res.json();
}

export async function getTasks(filters?: {
  status?: string;
  agent?: string;
  source?: string;
  q?: string;
}): Promise<Task[]> {
  if (isMock) {
    let result = [...stateTasks];
    if (filters?.status) {
      result = result.filter((t) => t.status === filters.status);
    }
    if (filters?.agent) {
      result = result.filter((t) => t.agent === filters.agent);
    }
    if (filters?.source) {
      result = result.filter((t) => t.source === filters.source);
    }
    if (filters?.q) {
      const q = filters.q.toLowerCase();
      result = result.filter((t) => t.title.toLowerCase().includes(q) || t.prompt.toLowerCase().includes(q));
    }
    return result;
  }
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.agent) params.set("agent", filters.agent);
  if (filters?.source) params.set("source", filters.source);
  if (filters?.q) params.set("q", filters.q);
  const res = await fetch(`${API_BASE}/tasks?${params.toString()}`);
  const data = await res.json();
  return data.items || data;
}

export async function createTask(payload: {
  title: string;
  prompt: string;
  agent: string;
  notify_level: "final_only" | "milestones" | "everything";
  budget?: { max_usd?: number; max_steps?: number };
  criteria?: { description: string; type: string }[];
}): Promise<{ task: Task; run: Run }> {
  if (isMock) {
    const taskId = `task-${Date.now().toString().slice(-4)}`;
    const runId = `run-${Date.now().toString().slice(-4)}`;
    const newTask: Task = {
      id: taskId,
      title: payload.title,
      prompt: payload.prompt,
      source: "api",
      agent: payload.agent,
      status: "planning",
      attempts: 1,
      notify_level: payload.notify_level,
      budget: payload.budget || { max_usd: 1.0, max_steps: 25 },
      created_at: new Date().toISOString(),
      checks_total: payload.criteria?.length || 2,
      checks_passed: 0,
      cost_usd: 0.0,
    };
    const newRun: Run = {
      id: runId,
      task_id: taskId,
      attempt: 1,
      status: "planning",
      agent: payload.agent,
      model_profile: "groq-llama-3.3-70b",
      current_step: "Initializing TaskSpec and acceptance criteria",
      tokens_in: 0,
      tokens_out: 0,
      cost_usd: 0.0,
      started_at: new Date().toISOString(),
      checks_total: newTask.checks_total || 2,
      checks_passed: 0,
    };
    stateTasks.unshift(newTask);
    stateRuns[runId] = newRun;
    stateRunEvents[runId] = [
      {
        id: `ev-${Date.now()}`,
        run_id: runId,
        seq: 1,
        created_at: new Date().toISOString(),
        type: "run.started",
        payload: { task_id: taskId, attempt: 1, agent: payload.agent },
      },
    ];
    return { task: newTask, run: newRun };
  }

  const res = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function getLiveRuns(): Promise<Run[]> {
  if (isMock) {
    return Object.values(stateRuns).filter((r) =>
      ["planning", "executing", "verifying", "waiting_approval"].includes(r.status)
    );
  }
  const res = await fetch(`${API_BASE}/runs?status=running`);
  const data = await res.json();
  return data.items || data;
}

export async function getRun(id: string): Promise<Run | null> {
  if (isMock) {
    return stateRuns[id] || null;
  }
  const res = await fetch(`${API_BASE}/runs/${id}`);
  if (!res.ok) return null;
  return res.json();
}

export async function getRunCriteriaAndVerdicts(runId: string): Promise<{
  criteria: Criterion[];
  verdicts: Verdict[];
}> {
  if (isMock) {
    return (
      stateCriteriaVerdicts[runId] ||
      stateCriteriaVerdicts["run-102"] || { criteria: [], verdicts: [] }
    );
  }
  const res = await fetch(`${API_BASE}/runs/${runId}`);
  const data = await res.json();
  return { criteria: data.criteria || [], verdicts: data.verdicts || [] };
}

export async function getRunEvents(runId: string, afterSeq = 0): Promise<RunEvent[]> {
  if (isMock) {
    const events = stateRunEvents[runId] || stateRunEvents["run-102"] || [];
    return events.filter((e) => e.seq > afterSeq);
  }
  const res = await fetch(`${API_BASE}/runs/${runId}/events?after_seq=${afterSeq}`);
  return res.json();
}

export async function getRunArtifacts(runId: string): Promise<Artifact[]> {
  if (isMock) {
    return MOCK_ARTIFACTS[runId] || MOCK_ARTIFACTS["run-102"] || [];
  }
  const res = await fetch(`${API_BASE}/runs/${runId}`);
  const data = await res.json();
  return data.artifacts || [];
}

export async function getApprovals(status?: "pending" | "approved" | "rejected"): Promise<Approval[]> {
  if (isMock) {
    if (status) {
      return stateApprovals.filter((a) => a.status === status);
    }
    return [...stateApprovals];
  }
  const q = status ? `?status=${status}` : "";
  const res = await fetch(`${API_BASE}/approvals${q}`);
  return res.json();
}

export async function decideApproval(
  id: string,
  decision: "approve" | "reject",
  note?: string
): Promise<Approval> {
  if (isMock) {
    const idx = stateApprovals.findIndex((a) => a.id === id);
    if (idx !== -1) {
      const updated: Approval = {
        ...stateApprovals[idx],
        status: decision === "approve" ? "approved" : "rejected",
        decided_by: "@operator (Dashboard)",
        decided_at: new Date().toISOString(),
        note: note || undefined,
      };
      stateApprovals[idx] = updated;

      // Update corresponding run status if waiting
      const run = Object.values(stateRuns).find((r) => r.id === updated.run_id);
      if (run && run.status === "waiting_approval") {
        run.status = decision === "approve" ? "executing" : "stopped";
        run.current_step =
          decision === "approve"
            ? "Approval granted: proceeding to next action"
            : "Approval rejected: run stopped by operator";
      }

      return updated;
    }
    throw new Error("Approval not found");
  }

  const res = await fetch(`${API_BASE}/approvals/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, note }),
  });
  return res.json();
}

export async function stopRun(runId: string): Promise<{ success: boolean }> {
  if (isMock) {
    if (stateRuns[runId]) {
      stateRuns[runId].status = "stopped";
      stateRuns[runId].current_step = "Manually stopped by operator via Dashboard";
    }
    return { success: true };
  }
  const res = await fetch(`${API_BASE}/runs/${runId}/stop`, { method: "POST" });
  return res.json();
}

export async function retryTask(taskId: string): Promise<{ task: Task; run: Run }> {
  if (isMock) {
    const task = stateTasks.find((t) => t.id === taskId);
    if (task) {
      task.attempts += 1;
      task.status = "executing";
      const newRunId = `run-${Date.now().toString().slice(-4)}`;
      const newRun: Run = {
        id: newRunId,
        task_id: taskId,
        attempt: task.attempts,
        status: "executing",
        agent: task.agent,
        model_profile: "groq-llama-3.3-70b",
        current_step: `Attempt ${task.attempts}: re-executing with prior failure feedback`,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0.0,
        started_at: new Date().toISOString(),
        checks_total: task.checks_total || 3,
        checks_passed: 0,
      };
      stateRuns[newRunId] = newRun;
      return { task, run: newRun };
    }
    throw new Error("Task not found");
  }
  const res = await fetch(`${API_BASE}/tasks/${taskId}/retry`, { method: "POST" });
  return res.json();
}

export async function getAgents(): Promise<AgentDefinition[]> {
  if (isMock) {
    return [...stateAgents];
  }
  const res = await fetch(`${API_BASE}/agents`);
  return res.json();
}

export async function getAgent(name: string): Promise<AgentDefinition | null> {
  if (isMock) {
    return stateAgents.find((a) => a.name === name || a.id === name) || null;
  }
  const res = await fetch(`${API_BASE}/agents/${name}`);
  if (!res.ok) return null;
  return res.json();
}

export async function updateAgent(
  name: string,
  payload: Partial<AgentDefinition>
): Promise<AgentDefinition> {
  if (isMock) {
    const idx = stateAgents.findIndex((a) => a.name === name || a.id === name);
    if (idx !== -1) {
      stateAgents[idx] = { ...stateAgents[idx], ...payload };
      return stateAgents[idx];
    }
    throw new Error("Agent not found");
  }
  const res = await fetch(`${API_BASE}/agents/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function getModelProfiles(capability?: string): Promise<ModelProfile[]> {
  if (isMock) {
    if (capability && capability !== "all") {
      return MOCK_MODEL_PROFILES.filter((m) => m.capability === capability);
    }
    return [...MOCK_MODEL_PROFILES];
  }
  const q = capability ? `?capability=${capability}` : "";
  const res = await fetch(`${API_BASE}/model-profiles${q}`);
  return res.json();
}

export async function getRouterPreview(
  capability: string,
  prefer: "cheap" | "fast" | "smart"
): Promise<{ profile: ModelProfile; reason: string }> {
  if (isMock) {
    const candidates = MOCK_MODEL_PROFILES.filter(
      (m) => m.capability === capability && m.key_configured && m.enabled
    );
    if (prefer === "cheap") {
      const match =
        candidates.find((c) => c.tags.includes("cheap")) || candidates[0] || MOCK_MODEL_PROFILES[0];
      return {
        profile: match,
        reason: `Selected profile '${match.name}' because it offers the lowest input/output cost per Mtok in the '${capability}' category.`,
      };
    }
    if (prefer === "fast") {
      const match =
        candidates.find((c) => c.tags.includes("fast")) || candidates[0] || MOCK_MODEL_PROFILES[0];
      return {
        profile: match,
        reason: `Selected profile '${match.name}' due to sub-400ms average round-trip latency on Groq hardware.`,
      };
    }
    const match =
      candidates.find((c) => c.tags.includes("smart") || c.tags.includes("high-reasoning")) ||
      candidates[0] ||
      MOCK_MODEL_PROFILES[1];
    return {
      profile: match,
      reason: `Selected profile '${match.name}' for maximum reasoning depth, complex tool calling, and verifier independence.`,
    };
  }

  const res = await fetch(`${API_BASE}/router/preview?capability=${capability}&prefer=${prefer}`);
  return res.json();
}

export async function getUsageRecords(): Promise<UsageRecord[]> {
  if (isMock) {
    return [...MOCK_USAGE_RECORDS];
  }
  const res = await fetch(`${API_BASE}/usage`);
  return res.json();
}

export async function getExtensions(kind?: "skill" | "mcp" | "plugin"): Promise<Extension[]> {
  if (isMock) {
    if (kind) {
      return MOCK_EXTENSIONS.filter((e) => e.kind === kind);
    }
    return [...MOCK_EXTENSIONS];
  }
  const q = kind ? `?kind=${kind}` : "";
  const res = await fetch(`${API_BASE}/extensions${q}`);
  return res.json();
}

export async function testMcpConnection(id: string): Promise<{ success: boolean; latency_ms: number; message: string }> {
  if (isMock) {
    await new Promise((r) => setTimeout(r, 600));
    return {
      success: true,
      latency_ms: 42,
      message: "Connected cleanly. 4 MCP tools discovered and registered.",
    };
  }
  const res = await fetch(`${API_BASE}/extensions/${id}/test`, { method: "POST" });
  return res.json();
}

export async function getMemoryDocs(scope?: string, search?: string): Promise<MemoryDoc[]> {
  if (isMock) {
    let docs = [...MOCK_MEMORY_DOCS];
    if (scope && scope !== "all") {
      docs = docs.filter((d) => d.scope === scope);
    }
    if (search) {
      const q = search.toLowerCase();
      docs = docs.filter((d) => d.path.toLowerCase().includes(q) || d.content.toLowerCase().includes(q));
    }
    return docs;
  }
  const params = new URLSearchParams();
  if (scope) params.set("scope", scope);
  if (search) params.set("q", search);
  const res = await fetch(`${API_BASE}/memory?${params.toString()}`);
  return res.json();
}

export async function getSchedules(): Promise<Schedule[]> {
  if (isMock) {
    return [...stateSchedules];
  }
  const res = await fetch(`${API_BASE}/schedules`);
  return res.json();
}

export async function toggleSchedule(id: string): Promise<Schedule> {
  if (isMock) {
    const s = stateSchedules.find((item) => item.id === id);
    if (s) {
      s.enabled = !s.enabled;
      return { ...s };
    }
    throw new Error("Schedule not found");
  }
  const res = await fetch(`${API_BASE}/schedules/${id}/toggle`, { method: "POST" });
  return res.json();
}

/**
 * Live SSE subscription with Last-Event-ID reconnection per spec §7.
 * In mock mode, simulates real-time stream with simulated events.
 */
export function subscribeToRunStream(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (err: unknown) => void
): () => void {
  if (isMock) {
    // Deliver existing events first
    const existing = stateRunEvents[runId] || stateRunEvents["run-102"] || [];
    existing.forEach((ev, idx) => {
      setTimeout(() => onEvent(ev), idx * 40);
    });

    let currentSeq = existing.length;
    // Simulate periodic live heartbeat/activity
    const interval = setInterval(() => {
      if (Math.random() > 0.6) {
        currentSeq++;
        const simulatedEvent: RunEvent = {
          id: `ev-sim-${Date.now()}`,
          run_id: runId,
          seq: currentSeq,
          created_at: new Date().toISOString(),
          type: "model.call",
          payload: {
            provider: "Groq",
            model: "llama-3.3-70b-versatile",
            tokens_in: 320,
            tokens_out: 85,
            cost_usd: 0.00012,
            latency_ms: 290,
            simulated: true,
            messages_preview: "Heartbeat stream check: agent status nominal.",
          },
        };
        onEvent(simulatedEvent);
      }
    }, 8000);

    return () => clearInterval(interval);
  }

  // Real backend SSE stream
  let eventSource: EventSource | null = null;
  let lastEventId = "";

  const connect = () => {
    const url = `${API_BASE}/runs/${runId}/stream`;
    eventSource = new EventSource(url);

    eventSource.onmessage = (e) => {
      try {
        lastEventId = e.lastEventId || lastEventId;
        const parsed = JSON.parse(e.data) as RunEvent;
        onEvent(parsed);
      } catch (err) {
        onError?.(err);
      }
    };

    eventSource.onerror = (err) => {
      onError?.(err);
      eventSource?.close();
      // Reconnect after 3 seconds with Last-Event-ID
      setTimeout(() => connect(), 3000);
    };
  };

  connect();

  return () => {
    eventSource?.close();
  };
}
