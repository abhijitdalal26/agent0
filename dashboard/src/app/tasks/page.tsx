"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Plus, RotateCcw, Search } from "lucide-react";
import { getAgents, getTasks, retryTask } from "@/lib/api";
import type { Task } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { NewTaskDialog } from "@/components/NewTaskDialog";
import { EmptyState, PageHeader, RelTime, Skeleton } from "@/components/ui";
import { runIdForTask } from "@/components/data";

const sel = "text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground focus:outline-none min-w-0";

export default function TasksPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [agent, setAgent] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setQ(search), 250);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    getAgents().then((a) => setAgents(a.map((x) => x.name))).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    try {
      setTasks(await getTasks({ q: q || undefined, status: status || undefined, source: source || undefined, agent: agent || undefined }));
      setError(null);
    } catch {
      setError("Could not load tasks.");
    } finally {
      setLoading(false);
    }
  }, [q, status, source, agent]);

  useEffect(() => {
    load();
    const poll = setInterval(load, 15000);
    return () => clearInterval(poll);
  }, [load]);

  const retry = async (id: string, e: React.MouseEvent) => {
    e.preventDefault();
    try {
      const { run } = await retryTask(id);
      router.push(`/runs/${run.id}`);
    } catch {
      setError("Retry failed.");
    }
  };

  const shown = tasks.filter((t) => {
    const d = t.created_at.slice(0, 10);
    return (!from || d >= from) && (!to || d <= to);
  });
  const filtered = !!(q || status || source || agent || from || to);

  return (
    <div className="space-y-4 sm:space-y-6">
      <PageHeader title="Tasks" description="Every task, its attempts and verification result.">
        <button onClick={() => setNewOpen(true)} className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors shrink-0">
          <Plus className="w-4 h-4" />New task
        </button>
      </PageHeader>

      <div className="flex flex-col lg:flex-row gap-2.5">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by title" aria-label="Search tasks" className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-input bg-card/60 placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
        </div>
        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
          <select value={status} onChange={(e) => setStatus(e.target.value)} className={sel} aria-label="Status">
            <option value="">All statuses</option>
            {["pending", "planning", "executing", "verifying", "waiting_approval", "succeeded", "failed", "stopped"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </select>
          <select value={source} onChange={(e) => setSource(e.target.value)} className={sel} aria-label="Source">
            <option value="">All sources</option>
            {["telegram", "slack", "api", "cli", "schedule"].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={agent} onChange={(e) => setAgent(e.target.value)} className={sel} aria-label="Agent">
            <option value="">All agents</option>
            {agents.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={sel} aria-label="From date" />
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={sel} aria-label="To date" />
        </div>
      </div>

      {error && <p className="text-xs text-rose-500">{error}</p>}

      {loading ? (
        <Skeleton rows={5} />
      ) : shown.length === 0 ? (
        <EmptyState
          title={filtered ? "No tasks match these filters" : "No tasks yet"}
          hint={filtered ? "Clear a filter to see more." : "Send /task in Telegram or click New task."}
        />
      ) : (
        <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
                <tr>
                  {["Task", "Status", "Agent", "Source", "Attempts", "Checks", "Cost", "Created", ""].map((h) => <th key={h} className="py-3 px-4 whitespace-nowrap">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {shown.map((t) => (
                  <tr key={t.id} className="hover:bg-secondary/30 transition-colors group">
                    <td className="py-3 px-4 max-w-sm">
                      <Link href={`/runs/${runIdForTask(t)}`} className="font-semibold line-clamp-1 group-hover:text-blue-500">{t.title}</Link>
                      <div className="text-[11px] font-mono text-muted-foreground">{t.id}</div>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap"><StatusBadge status={t.status} /></td>
                    <td className="py-3 px-4 font-mono whitespace-nowrap">{t.agent}</td>
                    <td className="py-3 px-4 font-mono uppercase text-muted-foreground text-[11px] whitespace-nowrap">{t.source}</td>
                    <td className="py-3 px-4 font-mono text-muted-foreground">{t.attempts}</td>
                    <td className="py-3 px-4 whitespace-nowrap font-mono">
                      {t.checks_total ? (
                        <span className={t.checks_passed === t.checks_total ? "text-emerald-500 font-semibold" : "text-amber-500"}>✓ {t.checks_passed}/{t.checks_total}</span>
                      ) : <span className="text-muted-foreground">—</span>}
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-500 whitespace-nowrap">{formatCurrency(t.cost_usd ?? 0)}</td>
                    <td className="py-3 px-4 font-mono text-muted-foreground whitespace-nowrap"><RelTime iso={t.created_at} /></td>
                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        {(t.status === "failed" || t.status === "stopped") && (
                          <button onClick={(e) => retry(t.id, e)} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center gap-1 font-mono text-[11px]">
                            <RotateCcw className="w-3.5 h-3.5" />Retry
                          </button>
                        )}
                        <Link href={`/runs/${runIdForTask(t)}`} aria-label="Open run" className="p-1 rounded text-muted-foreground hover:text-blue-500"><ArrowUpRight className="w-4 h-4" /></Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <NewTaskDialog isOpen={newOpen} onClose={() => { setNewOpen(false); load(); }} />
    </div>
  );
}
