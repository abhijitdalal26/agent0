import { getStatusBadgeClasses, getStatusLabel } from "@/lib/utils";
import type { RunStatus } from "@/types";

export function StatusBadge({ status, className = "" }: { status: RunStatus; className?: string }) {
  const styles = getStatusBadgeClasses(status);
  const label = getStatusLabel(status);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium ${styles.bg} ${styles.text} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${styles.dot}`} />
      <span>{label}</span>
    </span>
  );
}
