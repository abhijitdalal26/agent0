// API calls for the keys, settings, memory and schedules pages. Only apiFetch is used.
// Secret values are only ever passed as an argument to putSecret and are never stored or logged here.
import { apiFetch, ApiError } from "./http";

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface SecretItem {
  name: string;
  last4: string | null;
  configured: boolean;
  source: "env" | "store" | null;
  updated_at: string | null;
}

export interface ProfileLite {
  id: string;
  name: string;
  provider: string;
  key_env: string;
  enabled: boolean;
}

export interface SecretTestResult {
  ok: boolean;
  message: string;
}

export interface FactItem {
  id: string;
  scope: string;
  scope_id: string | null;
  content: string;
  source_id: string | null;
  valid_from: string | null;
  valid_to: string | null;
  superseded_by: string | null;
  current: boolean;
}

export interface ScheduleItem {
  id: string;
  agent: string;
  cron: string;
  prompt: string;
  enabled: boolean;
  last_run_at: string | null;
}

export interface ScheduleBody {
  agent: string;
  cron: string;
  prompt: string;
  enabled: boolean;
}

export interface AgentLite {
  name: string;
  description: string;
}

const enc = encodeURIComponent;

export const TELEGRAM_SECRET = "AGENT0_TELEGRAM_BOT_TOKEN";

// Secrets
export const listSecrets = () => apiFetch<Page<SecretItem>>("secrets");
export const listProfiles = () => apiFetch<Page<ProfileLite>>("model-profiles?limit=200");
export const putSecret = (name: string, value: string) =>
  apiFetch<SecretItem>(`secrets/${enc(name)}`, { method: "PUT", body: JSON.stringify({ value }) });
export const deleteSecret = (name: string) => apiFetch<SecretItem>(`secrets/${enc(name)}`, { method: "DELETE" });
export const testSecret = (name: string) =>
  apiFetch<SecretTestResult>(`secrets/${enc(name)}/test`, { method: "POST" });

// Memory
export function listFacts(scope: string, includeExpired: boolean) {
  const p = new URLSearchParams({ limit: "200" });
  if (scope !== "all") p.set("scope", scope);
  if (includeExpired) p.set("include_expired", "true");
  return apiFetch<Page<FactItem>>(`memory?${p}`);
}
export const searchFacts = (q: string) => apiFetch<Page<FactItem>>(`memory/search?q=${enc(q)}`);
export const editFact = (id: string, content: string) =>
  apiFetch<FactItem>(`memory/${enc(id)}`, { method: "PUT", body: JSON.stringify({ content }) });
export const forgetFact = (id: string) => apiFetch<void>(`memory/${enc(id)}`, { method: "DELETE" });
export const factRevisions = (id: string) => apiFetch<Page<FactItem>>(`memory/${enc(id)}/revisions`);

// Schedules
export const listSchedules = () => apiFetch<Page<ScheduleItem>>("schedules?limit=200");
export const listAgents = () => apiFetch<Page<AgentLite>>("agents?limit=200");
export const createSchedule = (b: ScheduleBody) =>
  apiFetch<ScheduleItem>("schedules", { method: "POST", body: JSON.stringify(b) });
export const updateSchedule = (id: string, b: ScheduleBody) =>
  apiFetch<ScheduleItem>(`schedules/${enc(id)}`, { method: "PUT", body: JSON.stringify(b) });
export const deleteSchedule = (id: string) => apiFetch<void>(`schedules/${enc(id)}`, { method: "DELETE" });

export function errMessage(e: unknown): string {
  return e instanceof Error ? e.message : "Request failed";
}

/** Friendly message for secret write errors. Never includes the submitted value. */
export function secretErrorMessage(e: unknown, name: string): string {
  if (e instanceof ApiError) {
    if (e.status === 503 || e.code === "secrets_disabled")
      return "Secret storage is disabled on the server. Set AGENT0_SECRET_KEY in the server environment and restart. Generate a key with `agent0 secrets-keygen`.";
    if (e.status === 409 && e.code === "env_managed")
      return `${name} is set in the server environment, so it is read-only here. Change it where the server is deployed.`;
    if (e.status === 409 && e.code === "not_configured") return `${name} is not configured yet.`;
    if (e.status === 404) return `${name} is not stored.`;
    if (e.status === 422) return `Rejected: ${e.message}`;
    if (e.status === 429) return "Too many requests. Wait a moment and try again.";
    if (e.status === 501) return "Testing is not available on this server.";
    return e.message;
  }
  return errMessage(e);
}
