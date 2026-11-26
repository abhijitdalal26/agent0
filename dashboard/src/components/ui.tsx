import type { ReactNode } from "react";
import { formatDateTime, formatRelativeTime } from "@/lib/utils";

export function RelTime({ iso, className = "" }: { iso?: string | null; className?: string }) {
  if (!iso) return <span className={className}>—</span>;
  return (
    <time dateTime={iso} title={formatDateTime(iso)} className={className}>
      {formatRelativeTime(iso)}
    </time>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pb-5 mb-6 border-b border-border/60">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex items-center gap-2 shrink-0">{children}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="p-8 text-center border border-dashed border-border rounded-xl text-muted-foreground text-xs space-y-1.5">
      {icon && <div className="flex justify-center opacity-70">{icon}</div>}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {hint && <p>{hint}</p>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 rounded-lg bg-muted/50 animate-pulse" />
      ))}
    </div>
  );
}

export function formatDuration(startIso?: string, endIso?: string, now = Date.now()): string {
  if (!startIso) return "—";
  const ms = (endIso ? Date.parse(endIso) : now) - Date.parse(startIso);
  if (!isFinite(ms) || ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export const ACTIVE = ["planning", "executing", "verifying"] as const;
export const isActive = (s: string) => (ACTIVE as readonly string[]).includes(s);
export const isFinished = (s: string) => ["succeeded", "failed", "stopped"].includes(s);
