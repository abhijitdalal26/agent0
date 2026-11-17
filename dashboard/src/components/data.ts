import { apiFetch, proxyUrl } from "@/lib/http";
import { getLiveRuns, getRun, getRunEvents, getTasks } from "@/lib/api";
import type { Run, RunEvent, Task } from "@/types";

export function artifactSrc(url: string): string {
  return url.startsWith("/api/v1/") ? proxyUrl(url.slice("/api/v1/".length)) : url;
}

export function runIdForTask(t: Task): string {
  const latest = (t as Task & { latest_run?: { id: string } | null }).latest_run;
  return latest?.id ?? `run-${t.id.replace(/^task-/, "")}`;
}

export async function getRunsForTask(taskId: string): Promise<Run[]> {
  try {
    const d = await apiFetch<Run[] | { items: Run[] }>(`runs?task_id=${encodeURIComponent(taskId)}`);
    const items = Array.isArray(d) ? d : d.items;
    return [...items].sort((a, b) => a.attempt - b.attempt);
  } catch {
    return [];
  }
}

export async function getTaskById(id: string): Promise<Task | null> {
  try {
    return await apiFetch<Task>(`tasks/${encodeURIComponent(id)}`);
  } catch {
    return (await getTasks().catch(() => [])).find((t) => t.id === id) ?? null;
  }
}

export interface FeedFilters { type?: string; agent?: string; run_id?: string }

export async function getGlobalEvents(f: FeedFilters = {}): Promise<RunEvent[]> {
  try {
    const q = new URLSearchParams();
    if (f.type) q.set("type", f.type);
    if (f.agent) q.set("agent", f.agent);
    if (f.run_id) q.set("run_id", f.run_id);
    const d = await apiFetch<RunEvent[] | { items: RunEvent[] }>(`events?${q}`);
    return Array.isArray(d) ? d : d.items;
  } catch {
    const runs = await getLiveRuns().catch(() => [] as Run[]);
    const all = await Promise.all(runs.map((r) => getRunEvents(r.id).catch(() => [] as RunEvent[])));
    return all.flat().sort((a, b) => a.created_at.localeCompare(b.created_at));
  }
}

export async function getRunSafe(id: string): Promise<Run | null> {
  return getRun(id).catch(() => null);
}
