import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, parseISO } from "date-fns";
import type { RunStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format currency according to spec §4:
 * "Costs always $0.0000 precision under $1, $0.00 above."
 */
export function formatCurrency(amount: number | undefined | null): string {
  if (amount === undefined || amount === null || isNaN(amount)) return "$0.0000";
  if (amount === 0) return "$0.0000";
  if (amount < 1) {
    return `$${amount.toFixed(4)}`;
  }
  return `$${amount.toFixed(2)}`;
}

export function formatTokens(tokens: number | undefined | null): string {
  if (!tokens) return "0";
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}k`;
  }
  return tokens.toLocaleString();
}

export function formatRelativeTime(isoString: string | undefined | null): string {
  if (!isoString) return "just now";
  try {
    const date = typeof isoString === "string" ? parseISO(isoString) : new Date(isoString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return isoString;
  }
}

export function formatDateTime(isoString: string | undefined | null): string {
  if (!isoString) return "";
  try {
    const date = typeof isoString === "string" ? parseISO(isoString) : new Date(isoString);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function getStatusBadgeClasses(status: RunStatus): {
  bg: string;
  text: string;
  border: string;
  dot: string;
} {
  switch (status) {
    case "executing":
    case "planning":
    case "verifying":
      return {
        bg: "bg-blue-500/10 dark:bg-blue-500/15",
        text: "text-blue-600 dark:text-blue-400",
        border: "border-blue-500/30",
        dot: "bg-blue-500 animate-pulse",
      };
    case "waiting_approval":
      return {
        bg: "bg-amber-500/10 dark:bg-amber-500/15",
        text: "text-amber-600 dark:text-amber-400",
        border: "border-amber-500/30",
        dot: "bg-amber-500 animate-pulse",
      };
    case "succeeded":
      return {
        bg: "bg-emerald-500/10 dark:bg-emerald-500/15",
        text: "text-emerald-600 dark:text-emerald-400",
        border: "border-emerald-500/30",
        dot: "bg-emerald-500",
      };
    case "failed":
      return {
        bg: "bg-rose-500/10 dark:bg-rose-500/15",
        text: "text-rose-600 dark:text-rose-400",
        border: "border-rose-500/30",
        dot: "bg-rose-500",
      };
    case "stopped":
    case "pending":
    default:
      return {
        bg: "bg-zinc-500/10 dark:bg-zinc-500/15",
        text: "text-zinc-600 dark:text-zinc-400",
        border: "border-zinc-500/30",
        dot: "bg-zinc-500",
      };
  }
}

export function getStatusLabel(status: RunStatus): string {
  switch (status) {
    case "planning":
      return "Planning";
    case "executing":
      return "Executing";
    case "verifying":
      return "Verifying";
    case "waiting_approval":
      return "Waiting Approval";
    case "succeeded":
      return "Succeeded";
    case "failed":
      return "Failed";
    case "stopped":
      return "Stopped";
    case "pending":
      return "Pending";
    default:
      return status;
  }
}
