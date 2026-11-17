"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Plus, Filter, ArrowUpRight, CheckCircle2, RotateCcw } from "lucide-react";
import { getTasks, retryTask } from "@/lib/api";
import type { Task, RunStatus } from "@/types";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { NewTaskDialog } from "@/components/NewTaskDialog";

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [agentFilter, setAgentFilter] = useState<string>("");
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const data = await getTasks({
        q: search || undefined,
        status: statusFilter || undefined,
        source: sourceFilter || undefined,
        agent: agentFilter || undefined,
      });
      setTasks(data);
    } catch (err) {
      console.error("Failed to load tasks:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
  }, [search, statusFilter, sourceFilter, agentFilter]);

  const handleRetry = async (taskId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await retryTask(taskId);
      loadTasks();
    } catch (err) {
      console.error("Failed to retry task:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
            Tasks & Workflows
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Filter, inspect verification criteria, and dispatch new agent runs.
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

      {/* Filter Row */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tasks by title or prompt..."
            className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-input bg-card/60 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="executing">Executing</option>
            <option value="planning">Planning</option>
            <option value="waiting_approval">Waiting Approval</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="stopped">Stopped</option>
          </select>

          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground focus:outline-none"
          >
            <option value="">All Sources</option>
            <option value="telegram">Telegram</option>
            <option value="cli">CLI</option>
            <option value="api">API</option>
            <option value="schedule">Schedule</option>
          </select>

          <select
            value={agentFilter}
            onChange={(e) => setAgentFilter(e.target.value)}
            className="text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground focus:outline-none"
          >
            <option value="">All Agents</option>
            <option value="creative-pack">creative-pack</option>
            <option value="analytics-agent">analytics-agent</option>
            <option value="planner">planner</option>
            <option value="executor">executor</option>
            <option value="ops-agent">ops-agent</option>
          </select>
        </div>
      </div>

      {/* Tasks Table */}
      <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
        {tasks.length === 0 ? (
          <div className="py-16 text-center text-muted-foreground text-xs space-y-2">
            <p className="text-sm font-medium text-foreground">No tasks match your filters</p>
            <p>Send a prompt in Telegram with /task or click New Task to launch an agent run.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
                <tr>
                  <th className="py-3 px-4">Task</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Agent</th>
                  <th className="py-3 px-4">Source</th>
                  <th className="py-3 px-4">Attempts</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Cost</th>
                  <th className="py-3 px-4">Created</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {tasks.map((task) => (
                  <tr
                    key={task.id}
                    className="hover:bg-secondary/30 transition-colors group cursor-pointer"
                    onClick={() => {
                      // Navigate to corresponding run
                      window.location.href = `/runs/run-102`;
                    }}
                  >
                    <td className="py-3 px-4 max-w-sm">
                      <div className="font-semibold text-foreground line-clamp-1 group-hover:text-blue-500 transition-colors">
                        {task.title}
                      </div>
                      <div className="text-[11px] font-mono text-muted-foreground">
                        id/{task.id}
                      </div>
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap">
                      <StatusBadge status={task.status} />
                    </td>

                    <td className="py-3 px-4 font-mono text-foreground whitespace-nowrap">
                      {task.agent}
                    </td>

                    <td className="py-3 px-4 font-mono uppercase text-muted-foreground text-[11px] whitespace-nowrap">
                      {task.source}
                    </td>

                    <td className="py-3 px-4 font-mono text-muted-foreground whitespace-nowrap">
                      {task.attempts} / {task.budget?.max_steps ? 3 : 2}
                    </td>

                    <td className="py-3 px-4 whitespace-nowrap font-mono">
                      {task.checks_total ? (
                        <span
                          className={
                            task.checks_passed === task.checks_total
                              ? "text-emerald-500 font-semibold"
                              : "text-amber-500"
                          }
                        >
                          ✓ {task.checks_passed}/{task.checks_total} checks
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono font-medium text-emerald-500 whitespace-nowrap">
                      {formatCurrency(task.cost_usd || 0)}
                    </td>

                    <td className="py-3 px-4 font-mono text-muted-foreground whitespace-nowrap">
                      {formatRelativeTime(task.created_at)}
                    </td>

                    <td className="py-3 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        {task.status === "failed" && (
                          <button
                            onClick={(e) => handleRetry(task.id, e)}
                            className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary flex items-center gap-1 font-mono text-[11px]"
                            title="Retry with feedback"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Retry</span>
                          </button>
                        )}
                        <Link
                          href={`/runs/run-102`}
                          className="p-1 rounded text-muted-foreground hover:text-blue-500"
                        >
                          <ArrowUpRight className="w-4 h-4" />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <NewTaskDialog
        isOpen={isNewTaskOpen}
        onClose={() => {
          setIsNewTaskOpen(false);
          loadTasks();
        }}
      />
    </div>
  );
}
