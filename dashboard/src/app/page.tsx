"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  Coins,
  Play,
  Plus,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import { getOverviewStats, getApprovals, getLiveRuns, getTasks } from "@/lib/api";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import type { OverviewStats, Approval, Run, Task } from "@/types";
import { StatusBadge } from "@/components/StatusBadge";
import { ApprovalCard } from "@/components/ApprovalCard";
import { NewTaskDialog } from "@/components/NewTaskDialog";

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [liveRuns, setLiveRuns] = useState<Run[]>([]);
  const [recentTasks, setRecentTasks] = useState<Task[]>([]);
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [s, apps, runs, tasks] = await Promise.all([
        getOverviewStats(),
        getApprovals("pending"),
        getLiveRuns(),
        getTasks(),
      ]);
      setStats(s);
      setPendingApprovals(apps);
      setLiveRuns(runs);
      setRecentTasks(tasks.slice(0, 10));
    } catch (err) {
      console.error("Failed to load overview data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Refresh interval for live operational view
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Operational Command Center</span>
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Multi-model agent steering, live execution inspection, and verification gates.
          </p>
        </div>

        <button
          onClick={() => setIsNewTaskOpen(true)}
          className="inline-flex items-center justify-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-sm shadow-blue-500/30 transition-all hover:scale-[1.02]"
        >
          <Plus className="w-4 h-4" />
          <span>New Task</span>
        </button>
      </div>

      {/* 3.1 Stat Row */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              Running Now
            </span>
            <div className="text-2xl font-bold font-mono text-foreground">
              {stats.running_now}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
              Needs Approval
            </span>
            <div className="text-2xl font-bold font-mono text-amber-500">
              {stats.waiting_approval}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              Succeeded (24h)
            </span>
            <div className="text-2xl font-bold font-mono text-emerald-500">
              {stats.succeeded_24h}
            </div>
          </div>

          <div className="p-3.5 rounded-xl border border-border bg-card/60 space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
              <XCircle className="w-3.5 h-3.5 text-rose-500" />
              Failed (24h)
            </span>
            <div className="text-2xl font-bold font-mono text-rose-500">
              {stats.failed_24h}
            </div>
          </div>

          <div className="col-span-2 lg:col-span-1 p-3.5 rounded-xl border border-border bg-card/60 space-y-1">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
              <Coins className="w-3.5 h-3.5 text-purple-400" />
              Spend Today
            </span>
            <div className="text-2xl font-bold font-mono text-purple-400">
              {formatCurrency(stats.spend_today_usd)}
            </div>
          </div>
        </div>
      )}

      {/* Prominent "Needs You" Section */}
      {pendingApprovals.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-amber-500 tracking-wider uppercase flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              <span>Needs You — Pending Approvals ({pendingApprovals.length})</span>
            </h2>
            <Link
              href="/approvals"
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 font-medium"
            >
              <span>View all approvals</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-2.5">
            {pendingApprovals.map((app) => (
              <ApprovalCard
                key={app.id}
                approval={app}
                onDecided={() => loadData()}
              />
            ))}
          </div>
        </section>
      )}

      {/* Live Runs Grid */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-foreground tracking-wider uppercase flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500" />
            <span>Active Runs in Flight</span>
          </h2>
          <span className="text-xs text-muted-foreground font-mono">
            {liveRuns.length} active
          </span>
        </div>

        {liveRuns.length === 0 ? (
          <div className="p-8 text-center border border-dashed border-border rounded-xl text-muted-foreground text-xs space-y-1">
            <p>No agents currently executing.</p>
            <p className="text-[11px] text-muted-foreground/70">
              Dispatch a new task via Telegram /task or click New Task above.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {liveRuns.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="group p-4 rounded-xl border border-border bg-card/60 hover:bg-card hover:border-blue-500/40 transition-all space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold text-foreground group-hover:text-blue-500 transition-colors">
                        {run.agent}
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        attempt {run.attempt}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-muted-foreground">
                      run/{run.id}
                    </span>
                  </div>
                  <StatusBadge status={run.status} />
                </div>

                <div className="p-2.5 rounded-lg bg-zinc-950/40 border border-border/40 text-xs font-mono text-foreground flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                  <span className="truncate">{run.current_step || "Executing workflow"}</span>
                </div>

                <div className="flex items-center justify-between text-xs font-mono text-muted-foreground pt-1 border-t border-border/40">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatRelativeTime(run.started_at)}
                  </span>
                  <span className="text-emerald-500 font-semibold">
                    {formatCurrency(run.cost_usd)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Recent Finished Runs */}
      <section className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-foreground tracking-wider uppercase">
            Recent Task History
          </h2>
          <Link
            href="/tasks"
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 font-medium"
          >
            <span>View all tasks</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
          <div className="divide-y divide-border">
            {recentTasks.map((t) => (
              <Link
                key={t.id}
                href={`/tasks`}
                className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-secondary/40 transition-colors text-xs"
              >
                <div className="space-y-1 flex-1">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={t.status} />
                    <span className="font-mono text-muted-foreground text-[11px] uppercase">
                      {t.source}
                    </span>
                    <span className="font-mono text-muted-foreground text-[11px]">
                      • {t.agent}
                    </span>
                  </div>
                  <div className="font-medium text-foreground text-sm line-clamp-1">
                    {t.title}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground self-end sm:self-center">
                  {t.checks_total !== undefined && (
                    <span className="text-emerald-500 font-medium">
                      ✓ {t.checks_passed}/{t.checks_total} checks
                    </span>
                  )}
                  <span>{formatCurrency(t.cost_usd || 0)}</span>
                  <span className="text-muted-foreground/60">
                    {formatRelativeTime(t.created_at)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* New Task Dialog */}
      <NewTaskDialog
        isOpen={isNewTaskOpen}
        onClose={() => {
          setIsNewTaskOpen(false);
          loadData();
        }}
      />
    </div>
  );
}
