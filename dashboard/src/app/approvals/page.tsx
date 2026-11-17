"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, History, ShieldAlert } from "lucide-react";
import { getApprovals } from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import type { Approval, RunEvent } from "@/types";
import { ApprovalCard } from "@/components/ApprovalCard";
import { EmptyState, Skeleton } from "@/components/ui";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    try {
      setApprovals(await getApprovals());
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const onEvent = useCallback((e: RunEvent) => {
    if (e.type !== "approval.requested" && e.type !== "approval.decided") return;
    clearTimeout(timer.current);
    timer.current = setTimeout(load, 300);
  }, [load]);
  useEventStream("stream", { onEvent });

  useEffect(() => {
    load();
    const poll = setInterval(load, 20000);
    return () => { clearInterval(poll); clearTimeout(timer.current); };
  }, [load]);

  const pending = approvals.filter((a) => a.status === "pending");
  const history = approvals.filter((a) => a.status !== "pending");

  return (
    <div className="space-y-5 sm:space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-500" />Approvals
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">Risky actions pause here until you approve or reject them.</p>
      </div>

      {failed && approvals.length === 0 && (
        <EmptyState title="Could not load approvals" hint="Check the API connection." action={<button onClick={load} className="text-xs text-blue-500 hover:underline">Retry</button>} />
      )}

      <section className="space-y-3">
        <h2 className="text-xs font-semibold text-amber-500 uppercase tracking-wider flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4" />Pending ({pending.length})
        </h2>
        {loading ? (
          <Skeleton rows={2} />
        ) : pending.length === 0 ? (
          <EmptyState icon={<CheckCircle2 className="w-6 h-6 text-emerald-500" />} title="All clear" hint="Nothing is waiting on you. Tool calls that need sign-off will appear here and in Telegram." />
        ) : (
          pending.map((a) => <ApprovalCard key={a.id} approval={a} onDecided={load} />)
        )}
      </section>

      <section className="space-y-3 pt-4 border-t border-border">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <History className="w-4 h-4" />History ({history.length})
        </h2>
        {!loading && history.length === 0 ? (
          <EmptyState title="No past decisions" hint="Approved and rejected requests are kept here as an audit trail." />
        ) : (
          history.map((a) => <ApprovalCard key={a.id} approval={a} />)
        )}
      </section>
    </div>
  );
}
