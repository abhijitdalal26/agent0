"use client";

import { useEffect, useState } from "react";
import { ShieldAlert, CheckCircle2, History, AlertTriangle } from "lucide-react";
import { getApprovals } from "@/lib/api";
import type { Approval } from "@/types";
import { ApprovalCard } from "@/components/ApprovalCard";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      const data = await getApprovals();
      setApprovals(data);
    } catch (err) {
      console.error("Failed to load approvals:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, []);

  const pendingList = approvals.filter((a) => a.status === "pending");
  const historyList = approvals.filter((a) => a.status !== "pending");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-amber-500" />
          <span>Human Approvals Queue</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Gated human-in-the-loop decisions for critical tool executions and high-risk actions.
        </p>
      </div>

      {/* Pending Section */}
      <section className="space-y-3">
        <div className="flex items-center justify-between pb-1">
          <h2 className="text-xs font-semibold text-amber-500 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4" />
            <span>Pending Authorization ({pendingList.length})</span>
          </h2>
        </div>

        {pendingList.length === 0 ? (
          <div className="p-8 text-center rounded-xl border border-dashed border-border text-muted-foreground text-xs space-y-1">
            <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1 opacity-70" />
            <p className="font-medium text-foreground">All clear — no pending approvals</p>
            <p className="text-[11px] text-muted-foreground">
              Risky tool calls (e.g. email dispatch, DB mutations) will pause here for sign-off.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingList.map((app) => (
              <ApprovalCard key={app.id} approval={app} onDecided={loadApprovals} />
            ))}
          </div>
        )}
      </section>

      {/* History Section */}
      <section className="space-y-3 pt-4 border-t border-border">
        <div className="flex items-center justify-between pb-1">
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <History className="w-4 h-4" />
            <span>Audit Trail & Historical Decisions ({historyList.length})</span>
          </h2>
        </div>

        <div className="space-y-3">
          {historyList.map((app) => (
            <ApprovalCard key={app.id} approval={app} />
          ))}
        </div>
      </section>
    </div>
  );
}
