"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Cpu, FolderOpen, RotateCcw, ShieldAlert, ShieldCheck, ShieldX, Square } from "lucide-react";
import { getRun, getRunArtifacts, getRunCriteriaAndVerdicts, getRunEvents, getRunVerify, retryTask, stopRun } from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import type { Artifact, Criterion, Run, RunEvent, RunVerify, Task, Verdict } from "@/types";
import { formatCurrency, formatTokens } from "@/lib/utils";
import { StatusBadge } from "@/components/StatusBadge";
import { EventTimeline } from "@/components/EventTimeline";
import { VerificationPanel } from "@/components/VerificationPanel";
import { ArtifactViewer } from "@/components/ArtifactViewer";
import { ApprovalCard } from "@/components/ApprovalCard";
import { EmptyState, RelTime, Skeleton, formatDuration, isActive } from "@/components/ui";
import { getRunsForTask, getTaskById } from "@/components/data";

function mergeEvents(prev: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const seen = new Set(prev.map((e) => e.id));
  const add = incoming.filter((e) => !seen.has(e.id));
  if (add.length === 0) return prev;
  return [...prev, ...add].sort((a, b) => a.seq - b.seq || a.created_at.localeCompare(b.created_at));
}

function Stream({ runId, onEvent }: { runId: string; onEvent: (e: RunEvent) => void }) {
  useEventStream(`runs/${runId}/stream`, { onEvent });
  return null;
}

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: runId } = use(params);
  const router = useRouter();

  const [run, setRun] = useState<Run | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [attempts, setAttempts] = useState<Run[]>([]);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [baseVerdicts, setBaseVerdicts] = useState<Verdict[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"stop" | "retry" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [verify, setVerify] = useState<RunVerify | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const lastSeq = useRef(0);
  const artifactsRef = useRef<HTMLDivElement>(null);

  const refreshRun = useCallback(async () => {
    const [r, cv, arts] = await Promise.all([
      getRun(runId),
      getRunCriteriaAndVerdicts(runId).catch(() => ({ criteria: [], verdicts: [] })),
      getRunArtifacts(runId).catch(() => []),
    ]);
    if (r) setRun(r);
    setCriteria(cv.criteria);
    setBaseVerdicts(cv.verdicts);
    setArtifacts(arts);
    return r;
  }, [runId]);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setEvents([]);
    lastSeq.current = 0;
    (async () => {
      try {
        const [r, evs] = await Promise.all([refreshRun(), getRunEvents(runId, 0)]);
        if (!live) return;
        setEvents(evs);
        if (r) {
          const [t, list] = await Promise.all([getTaskById(r.task_id), getRunsForTask(r.task_id)]);
          if (!live) return;
          setTask(t);
          setAttempts(list.length ? list : [r]);
        }
      } catch {
        if (live) setError("Could not load this run.");
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => { live = false; };
  }, [runId, refreshRun]);

  useEffect(() => {
    lastSeq.current = events.reduce((m, e) => Math.max(m, e.seq), 0);
  }, [events]);

  const active = !!run && (isActive(run.status) || run.status === "waiting_approval");

  const onStreamEvent = useCallback((e: RunEvent) => {
    if (e.run_id !== runId) return;
    setEvents((p) => mergeEvents(p, [e]));
    refreshRun().catch(() => {});
  }, [runId, refreshRun]);

  // Fallback and catch-up after a dropped connection: the stream resumes via Last-Event-ID, this fills any gap.
  useEffect(() => {
    if (!active) return;
    const t = setInterval(async () => {
      const more = await getRunEvents(runId, lastSeq.current).catch(() => []);
      if (more.length) setEvents((p) => mergeEvents(p, more));
      refreshRun().catch(() => {});
    }, 5000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(tick); };
  }, [active, runId, refreshRun]);

  const verdicts = useMemo(() => {
    const m = new Map(baseVerdicts.map((v) => [v.check_id, v]));
    for (const e of events) {
      if (e.type === "check.result") {
        const v = e.payload as unknown as Verdict;
        if (v.check_id) m.set(v.check_id, { ...v, evidence: v.evidence ?? "", cost_usd: v.cost_usd ?? 0 });
      }
    }
    return [...m.values()];
  }, [baseVerdicts, events]);

  const pendingApprovals = useMemo(() => {
    const decided = new Set(events.filter((e) => e.type === "approval.decided").map((e) => String(e.payload.approval_id)));
    return events.filter((e) => e.type === "approval.requested" && !decided.has(String(e.payload.approval_id)));
  }, [events]);

  const stop = async () => {
    if (!run || !confirm("Stop this run?")) return;
    setBusy("stop");
    setError(null);
    try {
      await stopRun(run.id);
      await refreshRun();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Stop failed");
    } finally {
      setBusy(null);
    }
  };

  const checkChain = async () => {
    setVerifyBusy(true);
    try {
      setVerify(await getRunVerify(runId));
    } catch {
      setVerify(null);
    } finally {
      setVerifyBusy(false);
    }
  };

  const retry = async () => {
    if (!run) return;
    setBusy("retry");
    setError(null);
    try {
      const res = await retryTask(run.task_id);
      router.push(`/runs/${res.run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Retry failed");
      setBusy(null);
    }
  };

  if (loading && !run) {
    return <div className="space-y-4"><Skeleton rows={2} /><Skeleton rows={4} /></div>;
  }
  if (!run) {
    return (
      <EmptyState
        title="Run not found"
        hint={error ?? "It may have been deleted, or the link is wrong."}
        action={<Link href="/tasks" className="text-xs text-blue-500 hover:underline">Back to tasks</Link>}
      />
    );
  }

  const title = task?.title ?? `Run ${run.id}`;
  const attemptList = attempts.length ? attempts : [run];

  return (
    <div className="space-y-4 sm:space-y-6">
      {run && active && <Stream runId={runId} onEvent={onStreamEvent} />}

      <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground min-w-0">
        <Link href="/tasks" className="hover:text-foreground flex items-center gap-1 shrink-0">
          <ArrowLeft className="w-3.5 h-3.5" />Tasks
        </Link>
        <span>/</span>
        <span className="text-foreground truncate">{run.id}</span>
      </div>

      <div className="p-3 sm:p-5 rounded-xl border border-border bg-card/60 space-y-3 sm:space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-3">
          <div className="space-y-1.5 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={run.status} />
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground">agent/{run.agent}</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground flex items-center gap-1">
                <Cpu className="w-3 h-3 text-purple-500" />{run.model_profile || "—"}
              </span>
            </div>
            <h1 className="text-base sm:text-xl font-bold tracking-tight text-foreground break-words">{title}</h1>
            {run.current_step && active && (
              <p className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
                <span className="truncate">{run.current_step}</span>
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {active && (
              <button onClick={stop} disabled={busy !== null} className="px-3 py-2 sm:py-1.5 text-xs font-semibold text-rose-500 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-lg disabled:opacity-50 flex items-center gap-1.5">
                <Square className="w-3.5 h-3.5 fill-current" />{busy === "stop" ? "Stopping…" : "Stop"}
              </button>
            )}
            {!active && (
              <button onClick={retry} disabled={busy !== null} className="px-3 py-2 sm:py-1.5 text-xs font-semibold text-foreground bg-secondary hover:bg-secondary/80 border border-border rounded-lg disabled:opacity-50 flex items-center gap-1.5">
                <RotateCcw className="w-3.5 h-3.5" />{busy === "retry" ? "Starting…" : "Retry"}
              </button>
            )}
            <button
              onClick={checkChain}
              disabled={verifyBusy}
              title={verify?.head_hash ? `head ${verify.head_hash}` : "Recompute the hash chain over every event in this run"}
              className={`px-3 py-2 sm:py-1.5 text-xs font-medium border rounded-lg flex items-center gap-1.5 disabled:opacity-50 ${
                verify === null
                  ? "text-muted-foreground hover:text-foreground bg-card border-border hover:bg-secondary"
                  : verify.ok
                    ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/30"
                    : "text-rose-500 bg-rose-500/10 border-rose-500/30"
              }`}
            >
              {verify === null ? (
                <ShieldCheck className="w-3.5 h-3.5" />
              ) : verify.ok ? (
                <ShieldCheck className="w-3.5 h-3.5" />
              ) : (
                <ShieldX className="w-3.5 h-3.5" />
              )}
              {verifyBusy ? "Verifying…" : verify === null ? "Verify trail" : verify.ok ? `Chain intact · ${verify.events}` : `Broken @ seq ${verify.bad_seq}`}
            </button>
            <button
              onClick={() => artifactsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
              className="px-3 py-2 sm:py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground bg-card border border-border hover:bg-secondary rounded-lg flex items-center gap-1.5"
            >
              <FolderOpen className="w-3.5 h-3.5" />Sandbox files
            </button>
          </div>
        </div>

        {error && <p className="text-xs text-rose-500">{error}</p>}

        <div className="pt-3 border-t border-border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-muted-foreground">Attempt</span>
            {attemptList.map((a) => (
              <Link
                key={a.id}
                href={`/runs/${a.id}`}
                className={`px-2 py-1 rounded font-mono ${a.id === run.id ? "bg-foreground text-background font-bold" : "bg-muted text-muted-foreground hover:text-foreground"}`}
              >
                {a.attempt}
                {a.id !== run.id && <span className="ml-1 opacity-70">{a.status}</span>}
              </Link>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-x-5 gap-y-1 font-mono text-muted-foreground">
            <span>Tokens <strong className="text-foreground">{formatTokens(run.tokens_in + run.tokens_out)}</strong> <span className="hidden sm:inline">({formatTokens(run.tokens_in)} in / {formatTokens(run.tokens_out)} out)</span></span>
            <span>Cost <strong className="text-emerald-500">{formatCurrency(run.cost_usd)}</strong></span>
            <span>Duration <strong className="text-foreground">{formatDuration(run.started_at, active ? undefined : run.ended_at, now)}</strong></span>
            <span>Started <RelTime iso={run.started_at} className="text-foreground" /></span>
          </div>
        </div>
      </div>

      {pendingApprovals.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xs font-semibold text-amber-500 uppercase tracking-wider flex items-center gap-1.5">
            <ShieldAlert className="w-4 h-4" />Needs you
          </h2>
          {pendingApprovals.map((e) => (
            <ApprovalCard
              key={e.id}
              hideRunLink
              approval={{
                id: String(e.payload.approval_id), run_id: e.run_id, question: String(e.payload.question ?? "Approval requested"),
                options: (e.payload.options as string[]) ?? ["Approve", "Reject"], status: "pending",
              }}
              onDecided={() => refreshRun().catch(() => {})}
            />
          ))}
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">
        <div className="lg:col-span-7 h-[65vh] lg:h-[calc(100vh-15rem)] lg:min-h-[520px] lg:sticky lg:top-4">
          <EventTimeline events={events} criteria={criteria} live={active} />
        </div>
        <div className="lg:col-span-5 space-y-4 sm:space-y-6 min-w-0">
          <VerificationPanel criteria={criteria} verdicts={verdicts} />
          <div ref={artifactsRef} className="scroll-mt-4">
            <ArtifactViewer artifacts={artifacts} />
          </div>
        </div>
      </div>
    </div>
  );
}
