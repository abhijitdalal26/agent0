"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock, Coins, Plus, ShieldAlert, XCircle } from "lucide-react";
import { getApprovals, getLiveRuns, getOverviewStats, getTasks } from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import { formatCurrency } from "@/lib/utils";
import type { Approval, OverviewStats, Run, RunEvent, Task } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { ApprovalCard } from "@/components/ApprovalCard";
import { NewTaskDialog } from "@/components/NewTaskDialog";
import { EmptyState, RelTime, Skeleton, formatDuration, isFinished } from "@/components/ui";
import { runIdForTask } from "@/components/data";

function Stat({ label, icon, value, tone = "text-foreground", className = "" }: { label: string; icon: React.ReactNode; value: React.ReactNode; tone?: string; className?: string }) {
  return (
    <div className={`p-3 sm:p-3.5 rounded-xl border border-border bg-card/60 space-y-1 ${className}`}>
      <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">{icon}{label}</span>
      <div className={`text-xl sm:text-2xl font-bold font-mono ${tone}`}>{value}</div>
    </div>
  );
}

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [liveRuns, setLiveRuns] = useState<Run[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newOpen, setNewOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      const [s, a, r, t] = await Promise.all([getOverviewStats(), getApprovals("pending"), getLiveRuns(), getTasks()]);
      setStats(s);
      setApprovals(a);
      setLiveRuns(r);
      setTasks(t);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onEvent = useCallback((_: RunEvent) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(load, 400);
  }, [load]);
  useEventStream("stream", { onEvent });

  useEffect(() => {
    load();
    const poll = setInterval(load, 15000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(poll); clearInterval(tick); clearTimeout(timer.current); };
  }, [load]);

  const taskById = new Map(tasks.map((t) => [t.id, t]));
  const finished = tasks.filter((t) => isFinished(t.status)).slice(0, 20);

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight">Overview</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">What is running, what needs you, and what just finished.</p>
        </div>
        <button onClick={() => setNewOpen(true)} className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shrink-0">
          <Plus className="w-4 h-4" />New task
        </button>
      </div>

      {failed && !stats && (
        <EmptyState title="Could not reach the API" hint="Check that the agent0 API is running and the dashboard proxy is configured." action={<button onClick={load} className="text-xs text-blue-500 hover:underline">Retry</button>} />
      )}

      {approvals.length > 0 && (
        <section className="space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-xs font-semibold text-amber-500 tracking-wider uppercase flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />Needs you ({approvals.length})
            </h2>
            <Link href="/approvals" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">All approvals<ArrowRight className="w-3 h-3" /></Link>
          </div>
          {approvals.map((a) => (
            <ApprovalCard key={a.id} approval={a} onDecided={load} />
          ))}
        </section>
      )}

      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-2.5 sm:gap-3">
          <Stat label="Running" icon={<span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />} value={stats.running_now} tone="text-blue-500" />
          <Stat label="Waiting" icon={<ShieldAlert className="w-3.5 h-3.5 text-amber-500" />} value={stats.waiting_approval} tone="text-amber-500" />
          <Stat label="Succeeded 24h" icon={<CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />} value={stats.succeeded_24h} tone="text-emerald-500" />
          <Stat label="Failed 24h" icon={<XCircle className="w-3.5 h-3.5 text-rose-500" />} value={stats.failed_24h} tone="text-rose-500" />
          <Stat label="Spend today" icon={<Coins className="w-3.5 h-3.5 text-purple-500" />} value={formatCurrency(stats.spend_today_usd)} tone="text-purple-500" className="col-span-2 lg:col-span-1" />
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold tracking-wider uppercase flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500" />Live runs
          </h2>
          <span className="text-xs text-muted-foreground font-mono">{liveRuns.length} active</span>
        </div>
        {loading ? (
          <Skeleton rows={2} />
        ) : liveRuns.length === 0 ? (
          <EmptyState title="Nothing running" hint="Send /task in Telegram or click New task to start an agent run." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {liveRuns.map((run) => {
              const t = taskById.get(run.task_id);
              const max = (t as (Task & { max_attempts?: number }) | undefined)?.max_attempts;
              return (
                <Link key={run.id} href={`/runs/${run.id}`} className="group p-3.5 sm:p-4 rounded-xl border border-border bg-card/60 hover:bg-card hover:border-blue-500/40 transition-colors space-y-2.5 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-foreground line-clamp-2 group-hover:text-blue-500">{t?.title ?? `Run ${run.id}`}</div>
                      <div className="text-[11px] font-mono text-muted-foreground truncate">{run.agent} · attempt {run.attempt}{max ? ` of ${max}` : ""}</div>
                    </div>
                    <StatusBadge status={run.status} className="shrink-0" />
                  </div>
                  <div className="px-2.5 py-2 rounded-lg bg-muted/50 border border-border/40 text-xs font-mono flex items-center gap-2 min-w-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
                    <span className="truncate">{run.current_step || "Working…"}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-mono text-muted-foreground pt-1.5 border-t border-border/40">
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDuration(run.started_at, undefined, now)}</span>
                    <span className="text-emerald-500 font-semibold">{formatCurrency(run.cost_usd)}</span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold tracking-wider uppercase">Recently finished</h2>
          <Link href="/tasks" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1">All tasks<ArrowRight className="w-3 h-3" /></Link>
        </div>
        {loading ? (
          <Skeleton rows={3} />
        ) : finished.length === 0 ? (
          <EmptyState title="No finished runs yet" hint="Completed, failed and stopped runs show up here with their verification result." />
        ) : (
          <div className="rounded-xl border border-border bg-card/40 divide-y divide-border overflow-hidden">
            {finished.map((t) => (
              <Link key={t.id} href={`/runs/${runIdForTask(t)}`} className="p-3 sm:p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-3 hover:bg-secondary/40 text-xs">
                <div className="min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge status={t.status} />
                    <span className="font-mono text-muted-foreground text-[11px]">{t.agent}</span>
                  </div>
                  <div className="font-medium text-sm line-clamp-1">{t.title}</div>
                </div>
                <div className="flex items-center gap-3 sm:gap-4 font-mono text-muted-foreground shrink-0">
                  {t.checks_total ? (
                    <span className={t.checks_passed === t.checks_total ? "text-emerald-500 font-medium" : "text-amber-500 font-medium"}>✓ {t.checks_passed}/{t.checks_total}</span>
                  ) : null}
                  <span>{formatCurrency(t.cost_usd ?? 0)}</span>
                  <RelTime iso={t.created_at} className="text-muted-foreground/70" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <NewTaskDialog isOpen={newOpen} onClose={() => { setNewOpen(false); load(); }} />
    </div>
  );
}
