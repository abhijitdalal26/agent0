"use client";

import { useEffect, useRef } from "react";
import type { RunEvent } from "@/types";

const TYPES = [
  "run.started", "plan.created", "model.call", "tool.call", "tool.result", "skill.loaded",
  "memory.recalled", "memory.saved", "knowledge.read", "check.result", "approval.requested",
  "approval.decided", "budget.exceeded", "error", "run.finished",
];

export function useEventStream(path: string | null, opts: { onEvent: (e: RunEvent) => void }) {
  const handler = useRef(opts.onEvent);
  handler.current = opts.onEvent;

  useEffect(() => {
    if (!path) return;
    const es = new EventSource(`/api/proxy/${path.replace(/^\/+/, "")}`);
    const on = (m: MessageEvent) => {
      try {
        handler.current(JSON.parse(m.data) as RunEvent);
      } catch {}
    };
    es.onmessage = on;
    TYPES.forEach((t) => es.addEventListener(t, on as EventListener));
    return () => es.close();
  }, [path]);
}
