"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { getRun } from "@/lib/api";
import { useEventStream } from "@/lib/sse";
import type { RunEvent } from "@/types";
import { EventTimeline } from "@/components/EventTimeline";
import { PageHeader } from "@/components/ui";
import { getGlobalEvents } from "@/components/data";

const TYPES = [
  "run.started", "plan.created", "model.call", "tool.call", "tool.result", "skill.loaded", "memory.recalled",
  "memory.saved", "knowledge.read", "check.result", "approval.requested", "approval.decided", "budget.exceeded", "error", "run.finished",
];
const CAP = 500;

const sel = "text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground min-w-0";

export default function ActivityPage() {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [type, setType] = useState("");
  const [agent, setAgent] = useState("");
  const [runQ, setRunQ] = useState("");
  const [frozen, setFrozen] = useState<RunEvent[] | null>(null);
  const [agents, setAgents] = useState<Record<string, string>>({});
  const asked = useRef(new Set<string>());

  const add = useCallback((incoming: RunEvent[]) => {
    setEvents((prev) => {
      const seen = new Set(prev.map((e) => e.id));
      const fresh = incoming.filter((e) => !seen.has(e.id));
      if (!fresh.length) return prev;
      return [...prev, ...fresh].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.seq - b.seq).slice(-CAP);
    });
  }, []);

  useEffect(() => {
    getGlobalEvents().then((e) => add(e)).finally(() => setLoaded(true));
  }, [add]);

  const onEvent = useCallback((e: RunEvent) => add([e]), [add]);
  useEventStream("stream", { onEvent });

  useEffect(() => {
    for (const id of new Set(events.map((e) => e.run_id))) {
      if (asked.current.has(id)) continue;
      asked.current.add(id);
      getRun(id).then((r) => r && setAgents((m) => ({ ...m, [id]: r.agent }))).catch(() => {});
    }
  }, [events]);

  const source = frozen ?? events;
  const agentNames = useMemo(() => [...new Set(Object.values(agents))].sort(), [agents]);
  const shown = useMemo(
    () =>
      source.filter(
        (e) =>
          (!type || e.type === type) &&
          (!agent || (agents[e.run_id] ?? String(e.payload.agent ?? "")) === agent) &&
          (!runQ || e.run_id.toLowerCase().includes(runQ.trim().toLowerCase())),
      ),
    [source, type, agent, agents, runQ],
  );

  return (
    <div className="space-y-4 sm:space-y-5">
      <PageHeader title="Activity" description="Every event across all runs, live." />

      <div className="flex flex-col md:flex-row md:items-center md:justify-end gap-2">
          <select value={type} onChange={(e) => setType(e.target.value)} className={sel} aria-label="Event type">
            <option value="">All types</option>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={agent} onChange={(e) => setAgent(e.target.value)} className={sel} aria-label="Agent">
            <option value="">All agents</option>
            {agentNames.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          <input value={runQ} onChange={(e) => setRunQ(e.target.value)} placeholder="Run id" aria-label="Run id" className={`${sel} font-mono`} />
          <button
            onClick={() => setFrozen(frozen ? null : events)}
            className="text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 hover:bg-secondary flex items-center justify-center gap-1.5"
          >
            {frozen ? <><Play className="w-3.5 h-3.5" />Resume</> : <><Pause className="w-3.5 h-3.5" />Pause</>}
          </button>
      </div>

      <div className="h-[70vh] lg:h-[calc(100vh-14rem)] min-h-[360px]">
        <EventTimeline
          events={shown}
          showRun
          live={!frozen}
          title={frozen ? "Paused" : "Live feed"}
          emptyHint={loaded ? (type || agent || runQ ? "No events match these filters." : "Start a task and its events will stream in here.") : "Loading…"}
        />
      </div>
    </div>
  );
}
