// Server-side fake of the agent0 backend, used by the proxy when AGENT0_MOCK=1.
// It speaks the real /api/v1 wire format (paginated envelopes, {run, spec, verdicts, artifacts}, SSE
// with named events), built from the fixtures in ./fixtures. Never imported by client code.
import type { Approval, Run, RunEvent, Task } from "@/types";
import {
  MOCK_AGENTS,
  MOCK_APPROVALS,
  MOCK_ARTIFACTS,
  MOCK_CRITERIA_VERDICTS,
  MOCK_EXTENSIONS,
  MOCK_MEMORY_DOCS,
  MOCK_MODEL_PROFILES,
  MOCK_RUNS,
  MOCK_RUN_EVENTS,
  MOCK_SCHEDULES,
  MOCK_TASKS,
  MOCK_USAGE_RECORDS,
} from "./fixtures";

type J = Record<string, any>;

export interface MockRequest {
  method: string;
  segments: string[];
  searchParams: URLSearchParams;
  body?: string;
  lastEventId?: string | null;
  signal?: AbortSignal;
}

const ACTIVE = ["planning", "executing", "verifying"];
const TERMINAL = ["succeeded", "failed", "stopped"];
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

interface State {
  tasks: J[];
  runs: Record<string, J>;
  events: Record<string, J[]>;
  approvals: J[];
  profiles: J[];
  extensions: J[];
  schedules: J[];
  facts: J[];
  secrets: Record<string, J>;
  agents: J[];
  seq: number;
}

function initState(): State {
  const now = Date.now();
  const facts: J[] = MOCK_MEMORY_DOCS.map((d) => ({
    id: d.id,
    scope: d.scope,
    scope_id: d.scope_id ?? null,
    content: d.content,
    source_id: d.path,
    valid_from: d.updated_at,
    valid_to: null,
    superseded_by: null,
    current: true,
  }));
  facts.push({
    id: "mem-old-1",
    scope: "global",
    scope_id: null,
    content: "Default sandbox timeout is 60 seconds.",
    source_id: "run-205",
    valid_from: new Date(now - 86400000 * 9).toISOString(),
    valid_to: new Date(now - 86400000 * 3).toISOString(),
    superseded_by: "mem-1",
    current: false,
  });
  const names = [
    ["GROQ_API_KEY", "store", "gsk1"],
    ["GEMINI_API_KEY", "env", null],
    ["OPENAI_API_KEY", null, null],
    ["AGENT0_TELEGRAM_BOT_TOKEN", "store", "T0k3"],
  ] as const;
  const secrets: J = {};
  for (const [name, source, last4] of names) {
    secrets[name] = {
      name,
      last4,
      configured: source !== null,
      source,
      updated_at: source === "store" ? new Date(now - 86400000 * 2).toISOString() : null,
    };
  }
  return {
    tasks: clone(MOCK_TASKS as J[]),
    runs: clone(MOCK_RUNS as J),
    events: clone(MOCK_RUN_EVENTS as J),
    approvals: clone(MOCK_APPROVALS as J[]),
    profiles: MOCK_MODEL_PROFILES.map((p) => ({ ...clone(p as J), key_env: p.key_env_var ?? null })),
    extensions: MOCK_EXTENSIONS.map((e) => {
      const { tools, bundles, source_path, runs_count, content_markdown, ...rest } = clone(e as J);
      return {
        ...rest,
        config: { ...rest.config, path: source_path, tools, bundles, runs_count, content_markdown },
      };
    }),
    schedules: MOCK_SCHEDULES.map((s) => {
      const { last_run, next_run, cron_readable, ...rest } = clone(s as J);
      return { ...rest, last_run_at: last_run ?? null };
    }),
    facts,
    secrets,
    agents: clone(MOCK_AGENTS as J[]),
    seq: 1,
  };
}

function state(): State {
  const g = globalThis as J;
  return (g.__agent0Mock ??= initState());
}

function json(data: unknown, status = 200): Response {
  if (status === 204) return new Response(null, { status });
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json" } });
}

function fail(status: number, code: string, message: string): Response {
  return json({ error: { code, message } }, status);
}

function page<T>(items: T[], params: URLSearchParams, map: (x: T) => unknown = (x) => x): Response {
  const limit = Math.min(Math.max(Number(params.get("limit")) || 50, 1), 200);
  const offset = Number(params.get("cursor")) || 0;
  const chunk = items.slice(offset, offset + limit);
  return json({
    items: chunk.map(map),
    next_cursor: offset + limit < items.length ? String(offset + limit) : null,
  });
}

const parse = (body?: string): J => {
  try {
    return body ? JSON.parse(body) : {};
  } catch {
    return {};
  }
};

function checksOf(runId: string, run: J): { total: number; passed: number } {
  const cv = (MOCK_CRITERIA_VERDICTS as J)[runId];
  if (!cv) return { total: run.checks_total ?? 0, passed: run.checks_passed ?? 0 };
  return {
    total: cv.criteria.length,
    passed: cv.verdicts.filter((v: J) => v.status === "pass").length,
  };
}

function runOut(run: J): J {
  const { total, passed } = checksOf(run.id, run);
  return { ...run, ended_at: run.ended_at ?? null, checks_total: total, checks_passed: passed };
}

function taskOut(task: J): J {
  const s = state();
  const runs = Object.values(s.runs).filter((r) => r.task_id === task.id);
  runs.sort((a, b) => (a.started_at < b.started_at ? 1 : -1));
  const { checks_total, checks_passed, cost_usd, ...rest } = task;
  return {
    ...rest,
    attempts: Math.max(task.attempts ?? 1, runs.length),
    latest_run: runs[0] ? runOut(runs[0]) : null,
  };
}

function agentOut(a: J): J {
  const policy: J = {};
  for (const t of a.tools ?? []) policy[t.name] = t.permission;
  return {
    name: a.name,
    description: a.description,
    instructions: a.instructions,
    capability: "chat",
    prefer: "smart",
    model_profile: a.model_profile ?? null,
    tools: (a.tools ?? []).map((t: J) => t.name),
    skills: [],
    mcp: [],
    policy,
    budget: a.budgets ?? {},
    version: a.versions?.[0]?.version ?? 1,
    runs_7d: a.runs_7d,
    success_rate: typeof a.success_rate === "number" ? a.success_rate / 100 : null,
    avg_cost_usd: a.avg_cost ?? null,
  };
}

/** Events a fake "live" run keeps producing. */
function nextFakeEvent(runId: string): J {
  const s = state();
  const list = (s.events[runId] ??= []);
  const seq = (list.length ? list[list.length - 1].seq : 0) + 1;
  const kinds = ["model.call", "tool.call", "tool.result", "check.result"] as const;
  const type = kinds[seq % kinds.length];
  const payloads: Record<string, J> = {
    "model.call": {
      provider: "Groq",
      model: "llama-3.3-70b-versatile",
      tokens_in: 320 + seq,
      tokens_out: 85,
      cost_usd: 0.00012,
      latency_ms: 290,
      messages_preview: "Mock stream: agent working.",
    },
    "tool.call": { tool: "run_shell", args: { command: "pytest -q" } },
    "tool.result": { tool: "run_shell", ok: true, result: "12 passed in 1.4s" },
    "check.result": { check_id: "c-1", status: "pass", evidence: "mock check passed" },
  };
  const ev = {
    id: `ev-mock-${runId}-${seq}`,
    run_id: runId,
    seq,
    created_at: new Date().toISOString(),
    type,
    payload: { ...payloads[type], simulated: true },
  };
  list.push(ev);
  return ev;
}

const encoder = new TextEncoder();

function sse(req: MockRequest, runId: string | null): Response {
  const s = state();
  const last = Number(req.lastEventId) || 0;
  const run = runId ? s.runs[runId] : null;
  if (runId && !run) return fail(404, "not_found", `run ${runId} not found`);

  let timer: ReturnType<typeof setInterval> | undefined;
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const frame = (ev: J, withId: boolean) =>
        controller.enqueue(
          encoder.encode(`${withId ? `id: ${ev.seq}\n` : ""}event: ${ev.type}\ndata: ${JSON.stringify(ev)}\n\n`),
        );
      const close = () => {
        if (timer) clearInterval(timer);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      };
      controller.enqueue(encoder.encode(": connected\n\n"));
      if (runId) {
        for (const ev of s.events[runId] ?? []) if (ev.seq > last) frame(ev, true);
        if (TERMINAL.includes(run!.status)) return close();
      }
      timer = setInterval(() => {
        try {
          if (runId) {
            const cur = s.runs[runId];
            if (TERMINAL.includes(cur.status)) return close();
            if (ACTIVE.includes(cur.status)) frame(nextFakeEvent(runId), true);
            else controller.enqueue(encoder.encode(": ping\n\n"));
          } else {
            const live = Object.values(s.runs).filter((r) => ACTIVE.includes(r.status));
            if (live.length) frame(nextFakeEvent(live[Math.floor(Math.random() * live.length)].id), false);
            else controller.enqueue(encoder.encode(": ping\n\n"));
          }
        } catch {
          close();
        }
      }, 2000);
      req.signal?.addEventListener("abort", close);
    },
    cancel() {
      if (timer) clearInterval(timer);
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
  });
}

function between(items: J[], field: string, params: URLSearchParams): J[] {
  const from = params.get("from");
  const to = params.get("to");
  return items.filter((i) => (!from || i[field] >= from) && (!to || i[field] < to));
}

export async function handleMock(req: MockRequest): Promise<Response> {
  const s = state();
  const { method, segments: seg, searchParams: q } = req;
  const [a, b, c, d] = seg;
  const body = parse(req.body);

  // ---- stats
  if (a === "stats" && b === "overview" && method === "GET") {
    const runs = Object.values(s.runs);
    return json({
      running: runs.filter((r) => ACTIVE.includes(r.status)).length,
      waiting_approval: runs.filter((r) => r.status === "waiting_approval").length,
      succeeded_24h: runs.filter((r) => r.status === "succeeded").length + 12,
      failed_24h: runs.filter((r) => r.status === "failed").length + 2,
      spend_today_usd: Number(runs.reduce((sum, r) => sum + (r.cost_usd ?? 0), 0).toFixed(6)),
    });
  }

  // ---- tasks
  if (a === "tasks") {
    if (!b && method === "GET") {
      const needle = q.get("q")?.toLowerCase();
      let items = s.tasks.filter(
        (t) =>
          (!q.get("status") || t.status === q.get("status")) &&
          (!q.get("agent") || t.agent === q.get("agent")) &&
          (!q.get("source") || t.source === q.get("source")) &&
          (!needle || t.title.toLowerCase().includes(needle)),
      );
      items = between(items, "created_at", q);
      return page(items, q, taskOut);
    }
    if (!b && method === "POST") {
      if (!body.prompt) return fail(422, "validation_error", "prompt is required");
      const id = `task-${++s.seq}${Date.now().toString().slice(-4)}`;
      const runId = `run-${id.slice(5)}`;
      const nowIso = new Date().toISOString();
      const task = {
        id,
        title: body.title || String(body.prompt).slice(0, 80),
        prompt: body.prompt,
        source: "api",
        agent: body.agent || "executor",
        status: "planning",
        attempts: 1,
        notify_level: body.notify_level || "milestones",
        budget: body.budget || {},
        created_at: nowIso,
      };
      const run = {
        id: runId,
        task_id: id,
        attempt: 1,
        status: "planning",
        agent: task.agent,
        model_profile: "groq-llama-3.3-70b",
        current_step: "Initializing TaskSpec and acceptance criteria",
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0,
        started_at: nowIso,
        checks_total: body.criteria?.length ?? 0,
        checks_passed: 0,
      };
      s.tasks.unshift(task);
      s.runs[runId] = run;
      s.events[runId] = [
        { id: `ev-${runId}-1`, run_id: runId, seq: 1, created_at: nowIso, type: "run.started", payload: { task_id: id } },
      ];
      return json({ task: taskOut(task), run: runOut(run) }, 201);
    }
    const task = s.tasks.find((t) => t.id === b);
    if (!task) return fail(404, "not_found", `task ${b} not found`);
    if (!c && method === "GET") {
      const runs = Object.values(s.runs).filter((r) => r.task_id === task.id);
      return json({ task: taskOut(task), runs: runs.map(runOut) });
    }
    if (c === "retry" && method === "POST") {
      const runId = `run-r${Date.now().toString().slice(-5)}`;
      const attempt = (task.attempts ?? 1) + 1;
      task.attempts = attempt;
      task.status = "executing";
      const run = {
        id: runId,
        task_id: task.id,
        attempt,
        status: "executing",
        agent: task.agent,
        model_profile: "groq-llama-3.3-70b",
        current_step: `Attempt ${attempt}: re-executing with prior failure feedback`,
        tokens_in: 0,
        tokens_out: 0,
        cost_usd: 0,
        started_at: new Date().toISOString(),
        checks_total: 0,
        checks_passed: 0,
      };
      s.runs[runId] = run;
      s.events[runId] = [
        { id: `ev-${runId}-1`, run_id: runId, seq: 1, created_at: run.started_at, type: "run.started", payload: { attempt } },
      ];
      return json({ run: runOut(run) }, 201);
    }
  }

  // ---- runs
  if (a === "runs") {
    if (!b && method === "GET") {
      const status = q.get("status");
      const items = Object.values(s.runs)
        .filter((r) => (!status || r.status === status) && (!q.get("task_id") || r.task_id === q.get("task_id")))
        .sort((x, y) => (x.started_at < y.started_at ? 1 : -1));
      return page(items, q, runOut);
    }
    const run = s.runs[b];
    if (!run) return fail(404, "not_found", `run ${b} not found`);
    if (!c && method === "GET") {
      const cv = (MOCK_CRITERIA_VERDICTS as J)[run.id] ?? (MOCK_CRITERIA_VERDICTS as J)["run-102"];
      return json({
        run: runOut(run),
        spec: { goal: s.tasks.find((t) => t.id === run.task_id)?.prompt ?? "", criteria: cv.criteria },
        verdicts: cv.verdicts,
        artifacts: ((MOCK_ARTIFACTS as J)[run.id] ?? []).map((x: J) => ({
          ...x,
          url: `/api/v1/runs/${run.id}/artifacts/${x.id}`,
        })),
      });
    }
    if (c === "events" && method === "GET") {
      const after = Number(q.get("after_seq")) || 0;
      const limit = Math.min(Number(q.get("limit")) || 200, 1000);
      const all = (s.events[run.id] ?? []).filter((e: J) => e.seq > after);
      return json({
        items: all.slice(0, limit),
        next_cursor: all.length > limit ? String(all[limit - 1].seq) : null,
      });
    }
    if (c === "stream" && method === "GET") return sse(req, run.id);
    if (c === "stop" && method === "POST") {
      if (TERMINAL.includes(run.status)) return fail(409, "run_finished", `run is already ${run.status}`);
      run.status = "stopped";
      run.current_step = "Stopped by operator";
      run.ended_at = new Date().toISOString();
      return json({ run: runOut(run) });
    }
    if (c === "artifacts" && d && method === "GET") {
      const art = ((MOCK_ARTIFACTS as J)[run.id] ?? []).find((x: J) => x.id === d);
      if (!art) return fail(404, "not_found", "artifact not found");
      return new Response(art.content_preview ?? `mock artifact ${art.path}\n`, {
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
  }

  // ---- approvals
  if (a === "approvals") {
    if (!b && method === "GET") {
      const st = q.get("status");
      return page(s.approvals.filter((x) => !st || x.status === st), q);
    }
    if (b && method === "POST") {
      const ap = s.approvals.find((x) => x.id === b);
      if (!ap) return fail(404, "not_found", `approval ${b} not found`);
      if (body.decision !== "approve" && body.decision !== "reject") {
        return fail(422, "validation_error", "decision must be approve or reject");
      }
      ap.status = body.decision === "approve" ? "approved" : "rejected";
      ap.decided_by = "dashboard";
      ap.decided_at = new Date().toISOString();
      ap.note = body.note ?? null;
      const run = s.runs[ap.run_id];
      if (run?.status === "waiting_approval") {
        run.status = body.decision === "approve" ? "executing" : "stopped";
        run.current_step = body.decision === "approve" ? "Approval granted" : "Approval rejected";
      }
      return json(ap);
    }
  }

  // ---- events (global feed)
  if (a === "events" && !b && method === "GET") {
    const types = q.get("type")?.split(",").filter(Boolean);
    let all = Object.values(s.events).flat() as J[];
    all = all.filter(
      (e) =>
        (!types || types.includes(e.type)) &&
        (!q.get("run_id") || e.run_id === q.get("run_id")) &&
        (!q.get("agent") || s.runs[e.run_id]?.agent === q.get("agent")),
    );
    all.sort((x, y) => (x.created_at < y.created_at ? 1 : -1));
    return page(all, q);
  }
  if (a === "stream" && !b && method === "GET") return sse(req, null);

  // ---- agents
  if (a === "agents") {
    if (!b && method === "GET") return page(s.agents, q, agentOut);
    const ag = s.agents.find((x) => x.name === b || x.id === b);
    if (b && !ag) return fail(404, "not_found", `agent ${b} not found`);
    if (b && !c && method === "GET") return json(agentOut(ag!));
    if (b && c === "versions" && method === "GET") return json({ items: ag!.versions ?? [], next_cursor: null });
    if (b && !c && method === "PUT") {
      if (typeof body.instructions === "string") ag!.instructions = body.instructions;
      if (body.model_profile) ag!.model_profile = body.model_profile;
      if (body.budget || body.budgets) ag!.budgets = body.budget ?? body.budgets;
      return json(agentOut(ag!));
    }
  }

  // ---- model profiles, router, usage
  if (a === "model-profiles") {
    if (!b && method === "GET") {
      const cap = q.get("capability");
      return page(s.profiles.filter((p) => !cap || p.capability === cap), q);
    }
    if (!b && method === "POST") {
      const p = { id: body.name, key_configured: false, enabled: true, tags: [], cost: {}, ...body };
      s.profiles.push(p);
      return json(p, 201);
    }
    const idx = s.profiles.findIndex((p) => p.id === b);
    if (idx < 0) return fail(404, "not_found", `profile ${b} not found`);
    if (method === "PUT") {
      s.profiles[idx] = { ...s.profiles[idx], ...body };
      return json(s.profiles[idx]);
    }
    if (method === "DELETE") {
      s.profiles.splice(idx, 1);
      return json(null, 204);
    }
  }
  if (a === "router" && b === "preview" && method === "GET") {
    const cap = q.get("capability") ?? "chat";
    const prefer = q.get("prefer") ?? "cheap";
    const pool = s.profiles.filter((p) => p.capability === cap && p.enabled && p.key_configured);
    const tag = prefer === "smart" ? "smart" : prefer;
    const pick = pool.find((p) => p.tags?.includes(tag)) ?? pool[0] ?? null;
    return json({
      profile: pick,
      reason: pick
        ? `Selected '${pick.name}' as the best '${prefer}' match among ${pool.length} enabled ${cap} profiles.`
        : `No enabled ${cap} profile has a configured key.`,
    });
  }
  if (a === "usage") {
    const rows = between(clone(MOCK_USAGE_RECORDS as J[]), "created_at", q).filter(
      (r) =>
        (!q.get("provider") || r.provider === q.get("provider")) &&
        (!q.get("capability") || r.capability === q.get("capability")),
    );
    if (!b && method === "GET") return page(rows, q);
    if (b === "summary" && method === "GET") {
      const by = q.get("group_by") ?? "provider";
      const groups: Record<string, J> = {};
      for (const r of rows) {
        const key = by === "day" ? String(r.created_at).slice(0, 10) : by === "agent" ? "mock-agent" : r[by];
        const g = (groups[key] ??= { [by]: key, calls: 0, cost_usd: 0, input_units: 0, output_units: 0, errors: 0 });
        g.calls += 1;
        g.cost_usd = Number((g.cost_usd + r.cost_usd).toFixed(6));
        g.input_units += r.input_units;
        g.output_units += r.output_units;
        if (!r.ok) g.errors += 1;
      }
      return json({ group_by: by, items: Object.values(groups) });
    }
  }

  // ---- extensions
  if (a === "extensions") {
    if (!b && method === "GET") {
      const kind = q.get("kind");
      return page(s.extensions.filter((e) => !kind || e.kind === kind), q);
    }
    const ext = s.extensions.find((e) => e.id === b);
    if (!ext) return fail(404, "not_found", `extension ${b} not found`);
    if (!c && method === "GET") return json(ext);
    if (!c && method === "PUT") {
      if (typeof body.enabled === "boolean") ext.enabled = body.enabled;
      return json(ext);
    }
    if (c === "test" && method === "POST") {
      return json({ ok: true, tools: ext.config?.tools ?? ["mock_tool"], error: null });
    }
  }

  // ---- secrets (values are never returned)
  if (a === "secrets") {
    if (!b && method === "GET") return json({ items: Object.values(s.secrets), next_cursor: null });
    const item = s.secrets[b];
    if (!item) return fail(422, "unknown_secret", `${b} is not a recognised secret name`);
    if (c === "test" && method === "POST") {
      return item.configured
        ? json({ ok: true, message: "Key accepted by provider (mock)." })
        : fail(409, "not_configured", `${b} is not configured`);
    }
    if (!c && method === "PUT") {
      if (item.source === "env") return fail(409, "env_managed", `${b} is set in the environment and is read-only here`);
      const value = String(body.value ?? "").trim();
      if (!value) return fail(422, "validation_error", "value must be a single non-empty line");
      Object.assign(item, { configured: true, source: "store", last4: value.slice(-4), updated_at: new Date().toISOString() });
      return json(item);
    }
    if (!c && method === "DELETE") {
      if (item.source === "env") return fail(409, "env_managed", `${b} is set in the environment and is read-only here`);
      if (item.source !== "store") return fail(404, "not_found", `${b} is not stored`);
      Object.assign(item, { configured: false, source: null, last4: null, updated_at: null });
      return json(item);
    }
  }

  // ---- memory facts
  if (a === "memory") {
    if (!b && method === "GET") {
      const inc = q.get("include_expired") === "true";
      return page(
        s.facts.filter(
          (f) =>
            (inc || f.current) &&
            (!q.get("scope") || q.get("scope") === "all" || f.scope === q.get("scope")) &&
            (!q.get("scope_id") || f.scope_id === q.get("scope_id")),
        ),
        q,
      );
    }
    if (b === "search" && method === "GET") {
      const needle = (q.get("q") ?? "").toLowerCase();
      return json({ items: s.facts.filter((f) => f.current && f.content.toLowerCase().includes(needle)), next_cursor: null });
    }
    const fact = s.facts.find((f) => f.id === b);
    if (!fact) return fail(404, "not_found", `fact ${b} not found`);
    if (!c && method === "GET") return json(fact);
    if (c === "revisions" && method === "GET") {
      const chain = s.facts.filter((f) => f.id === fact.id || f.superseded_by === fact.id || fact.superseded_by === f.id);
      return json({ items: chain, next_cursor: null });
    }
    if (!c && method === "PUT") {
      if (!body.content) return fail(422, "validation_error", "content is required");
      const next = { ...fact, id: `mem-${Date.now()}`, content: body.content, valid_from: new Date().toISOString() };
      fact.valid_to = new Date().toISOString();
      fact.current = false;
      fact.superseded_by = next.id;
      s.facts.push(next);
      return json(next);
    }
    if (!c && method === "DELETE") {
      fact.valid_to = new Date().toISOString();
      fact.current = false;
      return json(null, 204);
    }
  }

  // ---- schedules
  if (a === "schedules") {
    if (!b && method === "GET") return page(s.schedules, q);
    if (!b && method === "POST") {
      const row = { id: `sch-${Date.now()}`, enabled: true, last_run_at: null, ...body };
      s.schedules.push(row);
      return json(row, 201);
    }
    const idx = s.schedules.findIndex((x) => x.id === b);
    if (idx < 0) return fail(404, "not_found", `schedule ${b} not found`);
    if (method === "PUT") {
      s.schedules[idx] = { ...s.schedules[idx], ...body };
      return json(s.schedules[idx]);
    }
    if (method === "DELETE") {
      s.schedules.splice(idx, 1);
      return json(null, 204);
    }
  }

  return fail(404, "not_found", `mock has no route for ${method} /${seg.join("/")}`);
}

// Re-exported so typed helpers can reference the fixture-backed entity types.
export type { Approval, Run, RunEvent, Task };
