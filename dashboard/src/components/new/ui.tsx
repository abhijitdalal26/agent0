"use client";

import type { ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-6 text-xs text-muted-foreground" role="status">
      <Loader2 className="w-4 h-4 animate-spin" />
      {label}...
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-xs text-rose-500">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-px" />
      <div className="flex-1 break-words">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="font-semibold underline">
          Retry
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="p-10 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl">{children}</div>;
}

export function Badge({ tone, children }: { tone: "ok" | "warn" | "bad" | "muted" | "info"; children: ReactNode }) {
  const c = {
    ok: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    warn: "bg-amber-500/15 text-amber-500 border-amber-500/30",
    bad: "bg-rose-500/15 text-rose-500 border-rose-500/30",
    info: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    muted: "bg-muted text-muted-foreground border-border",
  }[tone];
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium border ${c}`}>{children}</span>;
}

export const btn =
  "inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border border-border bg-card hover:bg-secondary transition-colors disabled:opacity-50";
export const btnPrimary =
  "inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors disabled:opacity-50";
export const btnDanger =
  "inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 rounded-lg transition-colors disabled:opacity-50";
export const inputCls =
  "w-full text-xs px-3 py-2 rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring";
