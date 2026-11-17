"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, Plus, Power, Trash2 } from "lucide-react";
import {
  createSchedule,
  deleteSchedule,
  errMessage,
  listAgents,
  listSchedules,
  updateSchedule,
  type AgentLite,
  type ScheduleItem,
} from "@/lib/api-settings";
import { describeCron } from "@/components/new/cron";
import { formatRelativeTime } from "@/lib/utils";
import { Badge, btn, btnDanger, btnPrimary, Empty, ErrorBox, inputCls, Loading } from "@/components/new/ui";

const PRESETS = [
  { label: "Every day 09:00", cron: "0 9 * * *" },
  { label: "Every Monday 09:00", cron: "0 9 * * 1" },
  { label: "Weekdays 08:30", cron: "30 8 * * 1-5" },
  { label: "Every hour", cron: "0 * * * *" },
];

function CreateForm({ agents, onCreated, onCancel }: { agents: AgentLite[]; onCreated: () => void; onCancel: () => void }) {
  const [agent, setAgent] = useState(agents[0]?.name ?? "");
  const [cron, setCron] = useState("0 9 * * 1");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const fields = cron.trim().split(/\s+/).filter(Boolean).length;
  const preview = describeCron(cron);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await createSchedule({ agent, cron: cron.trim(), prompt: prompt.trim(), enabled: true });
      onCreated();
    } catch (e2) {
      setErr(errMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="space-y-1 text-xs">
          <span className="font-medium text-foreground">Agent</span>
          <select value={agent} onChange={(e) => setAgent(e.target.value)} className={inputCls} required>
            {agents.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-xs">
          <span className="font-medium text-foreground">Cron (5 fields: minute hour day month weekday)</span>
          <input value={cron} onChange={(e) => setCron(e.target.value)} className={`${inputCls} font-mono`} required spellCheck={false} />
          <span className={`block text-[11px] ${preview ? "text-emerald-500" : "text-muted-foreground"}`} aria-live="polite">
            {fields !== 5 ? "Needs exactly 5 fields." : preview ? `Runs ${preview}.` : "Valid shape, but no plain-English preview for this expression."}
          </span>
        </label>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button key={p.cron} type="button" onClick={() => setCron(p.cron)} className="text-[11px] px-2 py-1 rounded-md border border-border hover:bg-secondary">
            {p.label}
          </button>
        ))}
      </div>
      <label className="space-y-1 text-xs block">
        <span className="font-medium text-foreground">Prompt</span>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className={inputCls} required placeholder="What should the agent do each run?" />
      </label>
      {err && <ErrorBox message={err} />}
      <div className="flex gap-2">
        <button type="submit" className={btnPrimary} disabled={busy || fields !== 5 || !prompt.trim() || !agent}>
          {busy ? "Creating..." : "Create schedule"}
        </button>
        <button type="button" className={btn} onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function ScheduleRow({ s, onChanged }: { s: ScheduleItem; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const readable = describeCron(s.cron);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      setConfirm(false);
      onChanged();
    } catch (e) {
      setErr(errMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`rounded-xl border p-4 space-y-2.5 ${s.enabled ? "border-border bg-card/60" : "border-border/60 bg-card/30"}`}>
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">{readable ?? s.cron}</span>
            <span className="font-mono text-[11px] text-muted-foreground">{s.cron}</span>
            <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-muted text-foreground">{s.agent}</span>
            <Badge tone={s.enabled ? "ok" : "muted"}>{s.enabled ? "enabled" : "paused"}</Badge>
          </div>
          <p className="text-xs text-muted-foreground whitespace-pre-wrap break-words">{s.prompt}</p>
          <div className="text-[11px] text-muted-foreground font-mono">
            {s.last_run_at ? `last run ${formatRelativeTime(s.last_run_at)}` : "never run"}
          </div>
        </div>
        {!confirm && (
          <div className="flex gap-2 shrink-0">
            <button
              className={btn}
              disabled={busy}
              aria-pressed={s.enabled}
              onClick={() => run(() => updateSchedule(s.id, { agent: s.agent, cron: s.cron, prompt: s.prompt, enabled: !s.enabled }))}
            >
              <Power className="w-3 h-3" /> {s.enabled ? "Pause" : "Enable"}
            </button>
            <button className={`${btn} text-rose-500`} disabled={busy} onClick={() => setConfirm(true)} aria-label="Delete schedule">
              <Trash2 className="w-3 h-3" /> Delete
            </button>
          </div>
        )}
      </div>
      {confirm && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-xs">
          <span className="flex-1">Delete this schedule permanently?</span>
          <div className="flex gap-2">
            <button className={btnDanger} disabled={busy} onClick={() => run(() => deleteSchedule(s.id))}>
              {busy ? "Deleting..." : "Delete"}
            </button>
            <button className={btn} disabled={busy} onClick={() => setConfirm(false)}>
              Keep
            </button>
          </div>
        </div>
      )}
      {err && <ErrorBox message={err} />}
    </li>
  );
}

export default function SchedulesPage() {
  const [items, setItems] = useState<ScheduleItem[] | null>(null);
  const [agents, setAgents] = useState<AgentLite[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, a] = await Promise.all([listSchedules(), listAgents().catch(() => ({ items: [] as AgentLite[] }))]);
      setItems(s.items);
      setAgents(a.items);
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-500" />
            <span>Schedules</span>
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Recurring prompts an agent runs on a cron schedule.</p>
        </div>
        {!creating && (
          <button className={btnPrimary} onClick={() => setCreating(true)}>
            <Plus className="w-3.5 h-3.5" /> New schedule
          </button>
        )}
      </div>

      {creating && (
        <CreateForm
          agents={agents}
          onCancel={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            load();
          }}
        />
      )}
      {creating && agents.length === 0 && <ErrorBox message="No agents were returned by the server, so a schedule cannot be created." />}

      {error && <ErrorBox message={error} onRetry={load} />}
      {!items && !error && <Loading label="Loading schedules" />}
      {items && items.length === 0 && <Empty>No schedules yet. Create one to run an agent on a recurring cron.</Empty>}
      {items && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((s) => (
            <ScheduleRow key={s.id} s={s} onChanged={load} />
          ))}
        </ul>
      )}
    </div>
  );
}
