"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, X } from "lucide-react";
import { createTask, getAgents } from "@/lib/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  defaultAgent?: string;
}

type Notify = "final_only" | "milestones" | "everything";
interface CritRow { type: string; description: string; config: string }

const TYPES = ["command", "artifact", "http", "browser", "grounded", "llm_judge", "human"];
const HINT: Record<string, string> = {
  command: '{"cmd": "pytest -q", "expect_exit": 0}',
  artifact: '{"path": "out/report.md", "min_bytes": 100}',
  http: '{"url": "https://example.com", "status": 200}',
  browser: '{"url": "https://example.com", "expect_text": "Welcome"}',
  grounded: "{}",
  llm_judge: '{"rubric": "Brand voice is on point", "min_score": 4}',
  human: "{}",
};
const field = "w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring";

function parseConfig(s: string): { ok: true; value: Record<string, unknown> } | { ok: false } {
  if (!s.trim()) return { ok: true, value: {} };
  try {
    const v = JSON.parse(s);
    return v && typeof v === "object" && !Array.isArray(v) ? { ok: true, value: v } : { ok: false };
  } catch {
    return { ok: false };
  }
}

export function NewTaskDialog({ isOpen, onClose, defaultAgent }: Props) {
  const router = useRouter();
  const [agents, setAgents] = useState<string[]>([]);
  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [agent, setAgent] = useState(defaultAgent ?? "");
  const [notify, setNotify] = useState<Notify>("milestones");
  const [maxUsd, setMaxUsd] = useState("");
  const [maxSteps, setMaxSteps] = useState("");
  const [maxMinutes, setMaxMinutes] = useState("");
  const [criteria, setCriteria] = useState<CritRow[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    getAgents()
      .then((list) => {
        const names = list.map((a) => a.name);
        setAgents(names);
        setAgent((cur) => (cur && names.includes(cur) ? cur : names.includes("executor") ? "executor" : names[0] ?? ""));
      })
      .catch(() => setError("Could not load agents."));
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const patch = (i: number, p: Partial<CritRow>) => setCriteria((c) => c.map((r, k) => (k === i ? { ...r, ...p } : r)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    const rows = criteria.filter((c) => c.description.trim());
    const parsed = rows.map((c) => parseConfig(c.config));
    if (parsed.some((p) => !p.ok)) return setError("A criterion has invalid JSON config. It must be an object.");

    const budget: { max_usd?: number; max_steps?: number; max_minutes?: number } = {};
    if (maxUsd) budget.max_usd = parseFloat(maxUsd);
    if (maxSteps) budget.max_steps = parseInt(maxSteps, 10);
    if (maxMinutes) budget.max_minutes = parseInt(maxMinutes, 10);

    const payload = {
      title: title.trim() || prompt.trim().replace(/\s+/g, " ").slice(0, 80),
      prompt: prompt.trim(),
      agent,
      notify_level: notify,
      budget: Object.keys(budget).length ? budget : undefined,
      criteria: rows.length
        ? rows.map((c, i) => ({ id: `c${i + 1}`, type: c.type, description: c.description.trim(), config: (parsed[i] as { value: Record<string, unknown> }).value }))
        : undefined,
    };

    setSubmitting(true);
    setError(null);
    try {
      const { run } = await createTask(payload as unknown as Parameters<typeof createTask>[0]);
      onClose();
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the task.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center sm:p-4 bg-background/80 backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label="New task" onClick={(e) => e.stopPropagation()} className="relative w-full max-w-2xl bg-card border border-border rounded-t-xl sm:rounded-xl shadow-2xl p-4 sm:p-6 overflow-y-auto max-h-[92vh]">
        <div className="flex items-center justify-between pb-3 border-b border-border">
          <div>
            <h3 className="font-semibold text-base">New task</h3>
            <p className="text-xs text-muted-foreground">Describe the goal. Add checks the result must pass.</p>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary"><X className="w-5 h-5" /></button>
        </div>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold mb-1">Prompt <span className="text-rose-500">*</span></label>
            <textarea required rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="e.g. Summarise last week's failed runs and propose fixes" className={`${field} text-sm`} />
          </div>

          <div>
            <label className="block text-xs font-semibold mb-1">Title <span className="font-normal text-muted-foreground">(optional)</span></label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the start of the prompt" className={field} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold mb-1">Agent</label>
              <select value={agent} onChange={(e) => setAgent(e.target.value)} className={field} disabled={agents.length === 0}>
                {agents.length === 0 && <option value="">Loading…</option>}
                {agents.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1">Notify</label>
              <select value={notify} onChange={(e) => setNotify(e.target.value as Notify)} className={field}>
                <option value="milestones">Milestones</option>
                <option value="everything">Everything</option>
                <option value="final_only">Final result only</option>
              </select>
            </div>
          </div>

          <fieldset className="p-3 rounded-lg bg-secondary/30 border border-border">
            <legend className="px-1 text-xs font-semibold">Budget overrides <span className="font-normal text-muted-foreground">(blank = agent default)</span></legend>
            <div className="grid grid-cols-3 gap-2.5">
              {[
                ["Max USD", maxUsd, setMaxUsd, "0.05", "0.01"],
                ["Max steps", maxSteps, setMaxSteps, "1", "1"],
                ["Max minutes", maxMinutes, setMaxMinutes, "1", "1"],
              ].map(([label, val, set, step, min]) => (
                <div key={label as string}>
                  <label className="block text-[11px] text-muted-foreground mb-1">{label as string}</label>
                  <input type="number" inputMode="decimal" step={step as string} min={min as string} value={val as string} onChange={(e) => (set as (v: string) => void)(e.target.value)} className={`${field} font-mono`} />
                </div>
              ))}
            </div>
          </fieldset>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold">Acceptance criteria <span className="font-normal text-muted-foreground">(optional)</span></label>
              <button type="button" onClick={() => setCriteria((c) => [...c, { type: "command", description: "", config: "" }])} className="text-xs text-blue-500 hover:text-blue-400 font-medium inline-flex items-center gap-1">
                <Plus className="w-3.5 h-3.5" />Add check
              </button>
            </div>
            {criteria.length === 0 && <p className="text-xs text-muted-foreground">No extra checks. The planner will still propose its own.</p>}
            {criteria.map((c, i) => {
              const bad = !parseConfig(c.config).ok;
              return (
                <div key={i} className="p-2.5 rounded-lg border border-border space-y-2">
                  <div className="flex items-center gap-2">
                    <select value={c.type} onChange={(e) => patch(i, { type: e.target.value })} className={`${field} !w-36 shrink-0`} aria-label="Check type">
                      {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <input value={c.description} onChange={(e) => patch(i, { description: e.target.value })} placeholder="What must be true?" className={field} aria-label="Description" />
                    <button type="button" onClick={() => setCriteria((rows) => rows.filter((_, k) => k !== i))} aria-label="Remove check" className="p-1 text-muted-foreground hover:text-rose-500 shrink-0"><X className="w-4 h-4" /></button>
                  </div>
                  <textarea rows={2} value={c.config} onChange={(e) => patch(i, { config: e.target.value })} placeholder={HINT[c.type] ?? "{}"} aria-label="JSON config" className={`${field} font-mono text-[11px] ${bad ? "border-rose-500 focus:ring-rose-500" : ""}`} />
                  {bad && <p className="text-[11px] text-rose-500">Config must be a valid JSON object.</p>}
                </div>
              );
            })}
          </div>

          {error && <p className="text-xs text-rose-500">{error}</p>}

          <div className="pt-3 border-t border-border flex items-center justify-end gap-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-muted-foreground hover:text-foreground rounded-lg border border-border hover:bg-secondary">Cancel</button>
            <button type="submit" disabled={submitting || !prompt.trim() || !agent} className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg">
              {submitting ? "Starting…" : "Start task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
