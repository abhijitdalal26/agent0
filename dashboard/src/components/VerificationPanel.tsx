"use client";

import { CheckCircle2, XCircle, Clock, ShieldCheck, Terminal, FileText, Globe, UserCheck, Star } from "lucide-react";
import type { Criterion, Verdict } from "@/types";

interface VerificationPanelProps {
  criteria: Criterion[];
  verdicts: Verdict[];
}

export function VerificationPanel({ criteria, verdicts }: VerificationPanelProps) {
  const getIconForType = (type: string) => {
    switch (type) {
      case "command":
        return <Terminal className="w-3.5 h-3.5 text-blue-400" />;
      case "artifact":
        return <FileText className="w-3.5 h-3.5 text-purple-400" />;
      case "http":
      case "browser":
        return <Globe className="w-3.5 h-3.5 text-cyan-400" />;
      case "human":
        return <UserCheck className="w-3.5 h-3.5 text-amber-400" />;
      case "llm_judge":
      default:
        return <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />;
    }
  };

  const total = criteria.length;
  const passed = verdicts.filter((v) => v.status === "pass").length;
  const failed = verdicts.filter((v) => v.status === "fail").length;

  return (
    <div className="bg-card/50 rounded-xl border border-border p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <div>
          <h3 className="text-xs font-semibold text-foreground tracking-wide uppercase flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            <span>Verification Report</span>
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Strict acceptance criteria evaluated before task completion.
          </p>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-semibold">
            {passed}/{total} Passed
          </span>
          {failed > 0 && (
            <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-500 border border-rose-500/20 font-semibold">
              {failed} Failed
            </span>
          )}
        </div>
      </div>

      {/* Criteria & Verdicts List */}
      <div className="space-y-3">
        {criteria.map((crit) => {
          const verdict = verdicts.find((v) => v.check_id === crit.id);
          const status = verdict?.status || "pending";
          const isPass = status === "pass";
          const isFail = status === "fail";

          return (
            <div
              key={crit.id}
              className={`p-3 rounded-lg border text-xs transition-colors ${
                isPass
                  ? "border-emerald-500/30 bg-emerald-500/[0.02]"
                  : isFail
                  ? "border-rose-500/30 bg-rose-500/[0.03]"
                  : "border-border bg-card/40 opacity-70"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  {getIconForType(crit.type)}
                  <span className="font-mono text-[10px] uppercase text-muted-foreground px-1 rounded bg-muted">
                    {crit.type}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {isPass && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                      <CheckCircle2 className="w-3 h-3" />
                      Passed
                    </span>
                  )}
                  {isFail && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-500 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                      <XCircle className="w-3 h-3" />
                      Failed
                    </span>
                  )}
                  {status === "pending" && (
                    <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                      <Clock className="w-3 h-3" />
                      Pending
                    </span>
                  )}
                </div>
              </div>

              <div className="mt-2 text-foreground font-medium leading-snug">
                {crit.description}
              </div>

              {verdict && (
                <div className="mt-2 pt-2 border-t border-border/60 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>Evidence:</span>
                    {verdict.score !== undefined && (
                      <span className="font-mono text-purple-400 font-semibold flex items-center gap-1">
                        <Star className="w-3 h-3 fill-purple-400" />
                        Judge Score: {verdict.score}/5.0
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed font-mono bg-muted/40 p-2 rounded border border-border/40">
                    {verdict.evidence}
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
