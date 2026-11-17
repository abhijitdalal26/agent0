// SSE client over the proxy. Used by the run page (per-run stream) and the Overview/Activity pages
// (global stream). Reconnects with exponential backoff, resumes from the last seen seq and drops
// duplicate events (run_id + seq), so replays after a reconnect are harmless.
import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "@/types";
import { proxyUrl } from "./http";

/** Backend emits `event: <type>` frames, which EventSource only delivers to per-type listeners. */
export const RUN_EVENT_TYPES = [
  "run.started",
  "plan.created",
  "model.call",
  "tool.call",
  "tool.result",
  "skill.loaded",
  "memory.recalled",
  "memory.saved",
  "knowledge.read",
  "check.result",
  "approval.requested",
  "approval.decided",
  "budget.exceeded",
  "error",
  "run.finished",
] as const;

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface EventStreamOptions {
  onEvent: (event: RunEvent) => void;
  onStatus?: (status: StreamStatus) => void;
  onError?: (err: unknown) => void;
}

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30_000;
const SEEN_LIMIT = 5000;

/** Opens the stream at `path` (e.g. "/runs/abc/stream" or "/stream"). Returns a close function. */
export function openEventStream(path: string, opts: EventStreamOptions): () => void {
  if (typeof EventSource === "undefined") return () => {};

  let source: EventSource | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;
  let stopped = false;
  let lastSeq = 0;
  const seen = new Set<string>();

  const setStatus = (s: StreamStatus) => opts.onStatus?.(s);

  const handle = (e: MessageEvent) => {
    let event: RunEvent;
    try {
      event = JSON.parse(e.data) as RunEvent;
    } catch (err) {
      opts.onError?.(err);
      return;
    }
    const key = `${event.run_id}:${event.seq}`;
    if (seen.has(key)) return;
    seen.add(key);
    if (seen.size > SEEN_LIMIT) seen.delete(seen.values().next().value as string);
    if (typeof event.seq === "number" && event.seq > lastSeq) lastSeq = event.seq;
    attempt = 0;
    opts.onEvent(event);
  };

  const connect = () => {
    if (stopped) return;
    setStatus(attempt === 0 ? "connecting" : "reconnecting");
    // EventSource cannot set headers on a fresh connection, so the resume point goes in a query
    // param that the proxy turns into the Last-Event-ID header. Per-run streams only: the global
    // stream carries no ids and seq is per run.
    const resume = path.includes("/runs/") && lastSeq > 0 ? `${path.includes("?") ? "&" : "?"}last_event_id=${lastSeq}` : "";
    const es = new EventSource(proxyUrl(path) + resume);
    source = es;
    es.onopen = () => {
      attempt = 0;
      setStatus("open");
    };
    es.onmessage = handle;
    for (const type of RUN_EVENT_TYPES) es.addEventListener(type, handle as EventListener);
    es.onerror = (err) => {
      opts.onError?.(err);
      // CONNECTING means the browser is already retrying (and sends Last-Event-ID itself).
      // CLOSED means it gave up (HTTP error, 401, proxy down): back off and reconnect ourselves.
      if (es.readyState !== EventSource.CLOSED) {
        setStatus("reconnecting");
        return;
      }
      es.close();
      if (stopped) return;
      const delay = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** attempt) * (0.75 + Math.random() * 0.5);
      attempt += 1;
      setStatus("reconnecting");
      timer = setTimeout(connect, delay);
    };
  };

  connect();

  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    source?.close();
    setStatus("closed");
  };
}

/** React hook: subscribe to an SSE path for the lifetime of the component. Pass null to stay idle. */
export function useEventStream(
  path: string | null,
  { onEvent, onStatus, onError }: EventStreamOptions,
): { status: StreamStatus } {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  // Latest callbacks without resubscribing on every render.
  const handlers = useRef({ onEvent, onStatus, onError });
  handlers.current = { onEvent, onStatus, onError };

  useEffect(() => {
    if (!path) return;
    return openEventStream(path, {
      onEvent: (e) => handlers.current.onEvent(e),
      onStatus: (s) => {
        setStatus(s);
        handlers.current.onStatus?.(s);
      },
      onError: (err) => handlers.current.onError?.(err),
    });
  }, [path]);

  return { status };
}

/** Callback-style subscription kept for the run detail page. Returns an unsubscribe function. */
export function subscribeToRunStream(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (err: unknown) => void,
): () => void {
  return openEventStream(`/runs/${encodeURIComponent(runId)}/stream`, { onEvent, onError });
}
