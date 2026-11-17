"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Filter, RefreshCw, ArrowUpRight } from "lucide-react";
import { getRunEvents } from "@/lib/api";
import type { RunEvent } from "@/types";
import { EventTimeline } from "@/components/EventTimeline";

export default function ActivityPage() {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [filterType, setFilterType] = useState("");

  const loadEvents = async () => {
    // Fetch global activity from mock/api
    const evs = await getRunEvents("run-102");
    setEvents(evs);
  };

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 5000);
    return () => clearInterval(interval);
  }, []);

  const filtered = filterType ? events.filter((e) => e.type === filterType) : events;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-500" />
            <span>Global Real-Time Activity Feed</span>
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">
            Continuous unified event stream across all running agents, sandboxes, and verification checks.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-input bg-card/60 text-foreground"
          >
            <option value="">All Event Types</option>
            <option value="model.call">model.call</option>
            <option value="tool.call">tool.call</option>
            <option value="check.result">check.result</option>
            <option value="approval.requested">approval.requested</option>
            <option value="plan.created">plan.created</option>
            <option value="run.finished">run.finished</option>
          </select>
        </div>
      </div>

      {/* Main Timeline View */}
      <div className="h-[750px]">
        <EventTimeline events={filtered} autoScroll={false} />
      </div>
    </div>
  );
}
