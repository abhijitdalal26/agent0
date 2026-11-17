"use client";

import { useEffect, useState } from "react";
import { Calendar, Clock, Bot, Power, Plus, Play, CheckCircle2 } from "lucide-react";
import { getSchedules, toggleSchedule } from "@/lib/api";
import type { Schedule } from "@/types";
import { formatRelativeTime } from "@/lib/utils";

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);

  useEffect(() => {
    getSchedules().then(setSchedules);
  }, []);

  const handleToggle = async (id: string) => {
    try {
      const updated = await toggleSchedule(id);
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
    } catch (err) {
      console.error("Failed to toggle schedule:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Calendar className="w-5 h-5 text-blue-500" />
            <span>Automated Recurring Schedules</span>
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Ops automation, background maintenance tasks, and scheduled data extraction.
          </p>
        </div>
      </div>

      {/* Schedules List */}
      <div className="space-y-3">
        {schedules.map((sch) => (
          <div
            key={sch.id}
            className={`p-4 rounded-xl border transition-all space-y-3 ${
              sch.enabled
                ? "bg-card/70 border-border"
                : "bg-card/30 border-border/60 opacity-60"
            }`}
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    {sch.cron_readable}
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    ({sch.cron})
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">
                    agent/{sch.agent}
                  </span>
                </div>

                <p className="text-sm font-semibold text-foreground pt-1">
                  {sch.prompt}
                </p>
              </div>

              {/* Toggle Switch */}
              <div className="flex items-center gap-3 self-end sm:self-center">
                <button
                  onClick={() => handleToggle(sch.id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold transition-colors ${
                    sch.enabled
                      ? "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30 hover:bg-emerald-500/20"
                      : "bg-muted text-muted-foreground border border-border hover:bg-secondary"
                  }`}
                >
                  <Power className="w-3.5 h-3.5" />
                  <span>{sch.enabled ? "Active" : "Paused"}</span>
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-6 pt-2 border-t border-border/40 text-xs font-mono text-muted-foreground">
              {sch.last_run && (
                <span>Last run: <strong className="text-foreground">{formatRelativeTime(sch.last_run)}</strong></span>
              )}
              {sch.next_run && sch.enabled && (
                <span>Next run: <strong className="text-blue-400">{formatRelativeTime(sch.next_run)}</strong></span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
