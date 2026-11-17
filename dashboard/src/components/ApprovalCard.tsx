"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, XCircle, AlertTriangle, ArrowUpRight, MessageSquare } from "lucide-react";
import type { Approval } from "@/types";
import { decideApproval } from "@/lib/api";
import { formatRelativeTime } from "@/lib/utils";

interface ApprovalCardProps {
  approval: Approval;
  onDecided?: (updated: Approval) => void;
  compact?: boolean;
}

export function ApprovalCard({ approval, onDecided, compact = false }: ApprovalCardProps) {
  const [submitting, setSubmitting] = useState(false);
  const [showNoteInput, setShowNoteInput] = useState(false);
  const [note, setNote] = useState("");
  const [currentApproval, setCurrentApproval] = useState<Approval>(approval);

  const handleDecision = async (decision: "approve" | "reject") => {
    try {
      setSubmitting(true);
      const updated = await decideApproval(approval.id, decision, note.trim() || undefined);
      setCurrentApproval(updated);
      onDecided?.(updated);
    } catch (err) {
      console.error("Failed to decide approval:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const isPending = currentApproval.status === "pending";

  return (
    <div
      className={`rounded-lg border transition-all ${
        isPending
          ? "border-amber-500/40 bg-amber-500/[0.03] dark:bg-amber-950/20 shadow-sm"
          : "border-border bg-card opacity-80"
      } p-4`}
    >
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="space-y-1.5 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wider ${
                isPending
                  ? "bg-amber-500/20 text-amber-500 border border-amber-500/30"
                  : currentApproval.status === "approved"
                  ? "bg-emerald-500/20 text-emerald-500 border border-emerald-500/30"
                  : "bg-rose-500/20 text-rose-500 border border-rose-500/30"
              }`}
            >
              {isPending && <AlertTriangle className="w-3 h-3" />}
              {currentApproval.status === "approved" && <CheckCircle2 className="w-3 h-3" />}
              {currentApproval.status === "rejected" && <XCircle className="w-3 h-3" />}
              {currentApproval.status.replace("_", " ")}
            </span>

            <Link
              href={`/runs/${currentApproval.run_id}`}
              className="text-xs font-mono text-muted-foreground hover:text-foreground inline-flex items-center gap-1 group"
            >
              <span>run/{currentApproval.run_id}</span>
              <ArrowUpRight className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
            </Link>

            {currentApproval.decided_at && (
              <span className="text-xs text-muted-foreground">
                Decided {formatRelativeTime(currentApproval.decided_at)} by {currentApproval.decided_by}
              </span>
            )}
          </div>

          <h4 className="text-sm font-semibold text-foreground leading-snug">
            {currentApproval.question}
          </h4>

          {currentApproval.task_title && (
            <p className="text-xs text-muted-foreground line-clamp-1">
              Task: {currentApproval.task_title}
            </p>
          )}

          {currentApproval.note && (
            <div className="text-xs text-muted-foreground bg-muted/60 rounded px-2.5 py-1.5 mt-2 border border-border">
              <span className="font-semibold text-foreground">Operator note:</span> {currentApproval.note}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        {isPending && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2 sm:pt-0">
            {!showNoteInput && (
              <button
                type="button"
                onClick={() => setShowNoteInput(true)}
                className="px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground rounded border border-border hover:bg-secondary flex items-center justify-center gap-1"
                title="Add operator note"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span className="sm:hidden">Add Note</span>
              </button>
            )}

            <button
              type="button"
              disabled={submitting}
              onClick={() => handleDecision("reject")}
              className="px-3 py-1.5 text-xs font-medium text-rose-500 hover:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Reject</span>
            </button>

            <button
              type="button"
              disabled={submitting}
              onClick={() => handleDecision("approve")}
              className="px-3 py-1.5 text-xs font-medium text-emerald-950 dark:text-emerald-50 bg-emerald-500 hover:bg-emerald-400 font-semibold rounded-md transition-colors shadow-sm shadow-emerald-500/20 disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Approve</span>
            </button>
          </div>
        )}
      </div>

      {isPending && showNoteInput && (
        <div className="mt-3 pt-3 border-t border-border flex items-center gap-2">
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional decision note (e.g. approved for staging only)..."
            className="flex-1 text-xs px-2.5 py-1.5 rounded border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            type="button"
            onClick={() => setShowNoteInput(false)}
            className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
