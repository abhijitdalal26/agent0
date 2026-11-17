"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  Clock,
  Coins,
  Cpu,
  FolderOpen,
  Play,
  RotateCcw,
  Square,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  getRun,
  getRunCriteriaAndVerdicts,
  getRunArtifacts,
  stopRun,
  retryTask,
  subscribeToRunStream,
} from "@/lib/api";
import type { Run, Criterion, Verdict, Artifact, RunEvent } from "@/types";
import { formatCurrency, formatTokens, formatRelativeTime } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { EventTimeline } from "@/components/EventTimeline";
import { VerificationPanel } from "@/components/VerificationPanel";
import { ArtifactViewer } from "@/components/ArtifactViewer";

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const runId = resolvedParams.id;

  const [run, setRun] = useState<Run | null>(null);
  const [attempt, setAttempt] = useState<number>(2);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const loadRunData = async (selectedAttempt = attempt) => {
    try {
      const activeRunId = selectedAttempt === 1 ? `${runId}-att1` : runId;
      const [r, cv, arts] = await Promise.all([
        getRun(activeRunId),
        getRunCriteriaAndVerdicts(activeRunId),
        getRunArtifacts(activeRunId),
      ]);
      if (r) setRun(r);
      setCriteria(cv.criteria);
      setVerdicts(cv.verdicts);
      setArtifacts(arts);
    } catch (err) {
      console.error("Failed to load run details:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRunData(attempt);

    // Subscribe to SSE event stream with auto-reconnection
    const unsubscribe = subscribeToRunStream(
      runId,
      (newEvent) => {
        setEvents((prev) => {
          if (prev.some((e) => e.id === newEvent.id)) return prev;
          return [...prev, newEvent];
        });
      },
      (err) => console.warn("SSE stream reconnection notice:", err)
    );

    return () => unsubscribe();
  }, [runId, attempt]);

  const handleStop = async () => {
    if (!run) return;
    try {
      setActionLoading(true);
      await stopRun(run.id);
      loadRunData(attempt);
    } catch (err) {
      console.error("Failed to stop run:", err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!run) return;
    try {
      setActionLoading(true);
      await retryTask(run.task_id);
      setAttempt((prev) => prev + 1);
      loadRunData(attempt + 1);
    } catch (err) {
      console.error("Failed to retry run:", err);
    } finally {
      setActionLoading(false);
    }
  };

  if (!run && !loading) {
    return (
      <div className="py-20 text-center space-y-3">
        <h2 className="text-base font-semibold text-foreground">Run not found</h2>
        <Link href="/tasks" className="text-xs text-blue-500 hover:underline">
          Return to Tasks
        </Link>
      </div>
    );
  }

  const isRunning = run && ["planning", "executing", "verifying"].includes(run.status);

  return (
    <div className="space-y-6">
      {/* Back button & Breadcrumb */}
      <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
        <Link href="/tasks" className="hover:text-foreground flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Tasks</span>
        </Link>
        <span>/</span>
        <span className="text-foreground">{runId}</span>
      </div>

      {/* 3.3 Header */}
      {run && (
        <div className="p-4 sm:p-6 rounded-xl border border-border bg-card/60 backdrop-blur space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2.5">
                <StatusBadge status={run.status} />

                <span className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">
                  agent/{run.agent}
                </span>

                <span className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground flex items-center gap-1">
                  <Cpu className="w-3 h-3 text-purple-400" />
                  {run.model_profile}
                </span>
              </div>

              <h1 className="text-lg sm:text-xl font-bold tracking-tight text-foreground pt-1">
                Make 3 Instagram ad variants for our oral weight-loss program, launch Monday
              </h1>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2">
              {isRunning ? (
                <button
                  onClick={handleStop}
                  disabled={actionLoading}
                  className="px-3 py-1.5 text-xs font-semibold text-rose-500 hover:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop Run</span>
                </button>
              ) : (
                <button
                  onClick={handleRetry}
                  disabled={actionLoading}
                  className="px-3 py-1.5 text-xs font-semibold text-foreground bg-secondary hover:bg-secondary/80 border border-border rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>New Attempt</span>
                </button>
              )}

              <button
                onClick={() => alert("Opening sandbox file inspector: /workspace/artifacts/")}
                className="px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-card border border-border hover:bg-secondary rounded-lg transition-colors flex items-center gap-1.5"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Sandbox Files</span>
              </button>
            </div>
          </div>

          {/* Meta & Attempts Selector */}
          <div className="pt-3 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
            {/* Attempt Switcher */}
            <div className="flex items-center gap-1.5">
              <span className="text-muted-foreground font-sans">Attempt:</span>
              <button
                onClick={() => setAttempt(1)}
                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                  attempt === 1
                    ? "bg-foreground text-background font-bold"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                Attempt 1 (Failed check)
              </button>
              <button
                onClick={() => setAttempt(2)}
                className={`px-2 py-0.5 rounded text-xs transition-colors ${
                  attempt === 2
                    ? "bg-foreground text-background font-bold"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                Attempt 2 (Succeeded)
              </button>
            </div>

            {/* Totals: Tokens, Cost, Duration */}
            <div className="flex flex-wrap items-center gap-4 text-muted-foreground">
              <span>
                Tokens: <strong className="text-foreground">{formatTokens(run.tokens_in + run.tokens_out)}</strong> ({formatTokens(run.tokens_in)} in / {formatTokens(run.tokens_out)} out)
              </span>
              <span>
                Cost: <strong className="text-emerald-500">{formatCurrency(run.cost_usd)}</strong>
              </span>
              <span>
                Duration: <strong className="text-foreground">92s</strong>
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Split Layout: Left Timeline vs Right Verification & Artifacts */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Timeline (Live Streamed) */}
        <div className="lg:col-span-7 h-[700px] flex flex-col">
          <EventTimeline events={events} autoScroll={true} />
        </div>

        {/* Right Column: Verification Report & Artifacts Preview */}
        <div className="lg:col-span-5 space-y-6">
          <VerificationPanel criteria={criteria} verdicts={verdicts} />
          <ArtifactViewer artifacts={artifacts} />
        </div>
      </div>
    </div>
  );
}
