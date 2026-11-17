"use client";

import { AlertTriangle, CheckCircle2, Clock, FileText, Globe, MinusCircle, ShieldCheck, Star, Terminal, UserCheck, XCircle } from "lucide-react";
import type { Criterion, Verdict } from "@/types";
import { EmptyState } from "./ui";

type Shown = "pass" | "fail" | "error" | "pending" | "skipped";

const STYLE: Record<Shown, { label: string; chip: string; card: string; icon: React.ReactNode }> = {
  pass: { label: "Passed", chip: "text-emerald-500 bg-emerald-500/10 border-emerald-500/20", card: "border-emerald-500/30 bg-emerald-500/[0.03]", icon: <CheckCircle2 className="w-3 h-3" /> },
  fail: { label: "Failed", chip: "text-rose-500 bg-rose-500/10 border-rose-500/20", card: "border-rose-500/30 bg-rose-500/[0.04]", icon: <XCircle className="w-3 h-3" /> },
  error: { label: "Error", chip: "text-rose-500 bg-rose-500/10 border-rose-500/20", card: "border-rose-500/30 bg-rose-500/[0.04]", icon: <AlertTriangle className="w-3 h-3" /> },
  pending: { label: "Pending", chip: "text-muted-foreground bg-muted border-border", card: "border-border bg-card/40", icon: <Clock className="w-3 h-3" /> },
  skipped: { label: "Skipped", chip: "text-muted-foreground bg-muted border-border", card: "border-border bg-muted/30 opacity-80", icon: <MinusCircle className="w-3 h-3" /> },
};

export function shownStatus(v?: Verdict): Shown {
  if (!v) return "pending";
  if (v.status === "pending" && v.evidence.startsWith("skipped:")) return "skipped";
  return v.status;
}

function TypeIcon({ type }: { type: string }) {
  switch (type) {
    case "command": return <Terminal className="w-3.5 h-3.5 text-blue-500" />;
    case "artifact": return <FileText className="w-3.5 h-3.5 text-purple-500" />;
    case "http":
    case "browser": return <Globe className="w-3.5 h-3.5 text-cyan-500" />;
    case "human": return <UserCheck className="w-3.5 h-3.5 text-amber-500" />;
    default: return <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />;
  }
}

export function VerificationPanel({ criteria, verdicts }: { criteria: Criterion[]; verdicts: Verdict[] }) {
  const byId = new Map(verdicts.map((v) => [v.check_id, v]));
  const rows = [
    ...criteria.map((c) => ({ id: c.id, type: c.type as string, description: c.description, verdict: byId.get(c.id) })),
    ...verdicts.filter((v) => !criteria.some((c) => c.id === v.check_id)).map((v) => ({ id: v.check_id, type: v.type as string, description: v.check_id, verdict: v })),
  ];
  const passed = rows.filter((r) => shownStatus(r.verdict) === "pass").length;
  const failed = rows.filter((r) => ["fail", "error"].includes(shownStatus(r.verdict))).length;

  return (
    <div className="bg-card/50 rounded-xl border border-border p-3 sm:p-4 space-y-3">
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wide flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-emerald-500" />Verification
        </h3>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-semibold">{passed}/{rows.length}</span>
          {failed > 0 && <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-500 border border-rose-500/20 font-semibold">{failed} failed</span>}
        </div>
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No acceptance criteria" hint="Criteria appear once the plan is created. Add your own when creating a task." />
      ) : (
        <div className="space-y-2.5">
          {rows.map((r) => {
            const st = shownStatus(r.verdict);
            const s = STYLE[st];
            return (
              <div key={r.id} className={`p-3 rounded-lg border text-xs ${s.card}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <TypeIcon type={r.type} />
                    <span className="font-mono text-[10px] uppercase text-muted-foreground px-1 rounded bg-muted">{r.type}</span>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${s.chip}`}>{s.icon}{s.label}</span>
                </div>
                <div className="mt-2 text-foreground font-medium leading-snug">{r.description}</div>
                {r.verdict && (r.verdict.evidence || r.verdict.score !== undefined && r.verdict.score !== null) && (
                  <div className="mt-2 pt-2 border-t border-border/60 space-y-1">
                    {r.verdict.score !== undefined && r.verdict.score !== null && (
                      <div className="font-mono text-purple-500 font-semibold flex items-center gap-1 text-[11px]">
                        <Star className="w-3 h-3 fill-current" />Judge score {r.verdict.score}
                      </div>
                    )}
                    {r.verdict.evidence && (
                      <p className="text-[11px] text-muted-foreground leading-relaxed font-mono bg-muted/40 p-2 rounded border border-border/40 whitespace-pre-wrap break-words max-h-40 overflow-auto">
                        {r.verdict.evidence}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
