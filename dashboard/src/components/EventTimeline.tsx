"use client";

import { useEffect, useRef, useState } from "react";
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Coins,
  Cpu,
  FileCode,
  Layers,
  Sparkles,
  Terminal,
  Wrench,
  XCircle,
  AlertOctagon,
  ArrowDown,
  ShieldAlert,
} from "lucide-react";
import type { RunEvent } from "@/types";
import { formatCurrency, formatRelativeTime } from "@/lib/utils";
import { ApprovalCard } from "./ApprovalCard";

interface EventTimelineProps {
  events: RunEvent[];
  autoScroll?: boolean;
}

export function EventTimeline({ events, autoScroll = true }: EventTimelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  // Auto-scroll logic
  useEffect(() => {
    if (autoScroll && !userScrolledUp && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, autoScroll, userScrolledUp]);

  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 40;
    setUserScrolledUp(!isAtBottom);
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
      setUserScrolledUp(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedEvents((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="relative flex flex-col h-full bg-card/50 rounded-xl border border-border overflow-hidden">
      {/* Timeline Header */}
      <div className="px-4 py-2.5 border-b border-border bg-card/80 backdrop-blur flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          <h3 className="text-xs font-semibold text-foreground tracking-wide uppercase">
            Live Execution Stream
          </h3>
          <span className="text-[11px] font-mono text-muted-foreground px-1.5 py-0.2 rounded bg-muted">
            {events.length} events
          </span>
        </div>

        {userScrolledUp && (
          <button
            onClick={scrollToBottom}
            className="text-[11px] font-medium text-blue-500 hover:text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-full border border-blue-500/20 flex items-center gap-1 transition-colors"
          >
            <ArrowDown className="w-3 h-3" />
            <span>Jump to latest</span>
          </button>
        )}
      </div>

      {/* Events Scroll Area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-4 space-y-3 font-sans text-xs"
      >
        {events.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground">
            <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-40 animate-pulse" />
            <p>Waiting for agent workflow stream...</p>
          </div>
        ) : (
          events.map((event) => {
            const isExpanded = !!expandedEvents[event.id];

            switch (event.type) {
              case "plan.created": {
                const goal = (event.payload.goal as string) || "Formulated task spec";
                const steps = (event.payload.steps as string[]) || [];

                return (
                  <div
                    key={event.id}
                    className="p-3.5 rounded-lg border border-blue-500/30 bg-blue-500/[0.03] space-y-2"
                  >
                    <div className="flex items-center justify-between text-blue-500">
                      <div className="flex items-center gap-2 font-medium">
                        <Brain className="w-4 h-4" />
                        <span>Plan Created</span>
                      </div>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {formatRelativeTime(event.created_at)}
                      </span>
                    </div>

                    <div className="text-sm font-semibold text-foreground">{goal}</div>

                    {steps.length > 0 && (
                      <ol className="space-y-1.5 pt-1 pl-1">
                        {steps.map((st, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-xs text-muted-foreground">
                            <span className="font-mono text-[10px] text-blue-400 bg-blue-500/10 rounded px-1.5 py-0.2 mt-0.5">
                              {idx + 1}
                            </span>
                            <span>{st}</span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                );
              }

              case "model.call": {
                const model = (event.payload.model as string) || "Model";
                const provider = (event.payload.provider as string) || "Provider";
                const cost = event.payload.cost_usd as number;
                const latency = event.payload.latency_ms as number;
                const tokensIn = event.payload.tokens_in as number;
                const tokensOut = event.payload.tokens_out as number;
                const messagesPreview = event.payload.messages_preview as string;

                return (
                  <div
                    key={event.id}
                    className="p-3 rounded-lg border border-border bg-card/60 hover:bg-card transition-colors space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 font-medium text-foreground">
                        <Cpu className="w-3.5 h-3.5 text-purple-400" />
                        <span>{model}</span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-muted text-muted-foreground">
                          {provider}
                        </span>
                      </div>

                      <div className="flex items-center gap-3 font-mono text-[11px] text-muted-foreground">
                        {cost !== undefined && (
                          <span className="text-emerald-500 font-semibold">{formatCurrency(cost)}</span>
                        )}
                        {latency !== undefined && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 opacity-60" />
                            {latency}ms
                          </span>
                        )}
                        <span className="text-muted-foreground/60">{formatRelativeTime(event.created_at)}</span>
                      </div>
                    </div>

                    {tokensIn !== undefined && (
                      <div className="flex items-center gap-3 text-[11px] font-mono text-muted-foreground">
                        <span>in: {tokensIn.toLocaleString()} tok</span>
                        <span>out: {tokensOut?.toLocaleString() || 0} tok</span>
                      </div>
                    )}

                    {messagesPreview && (
                      <div>
                        <button
                          onClick={() => toggleExpand(event.id)}
                          className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 mt-1"
                        >
                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          <span>{isExpanded ? "Hide prompt preview" : "Show prompt preview"}</span>
                        </button>
                        {isExpanded && (
                          <pre className="mt-2 p-2.5 rounded bg-zinc-950 text-zinc-300 font-mono text-[11px] whitespace-pre-wrap overflow-x-auto border border-zinc-800">
                            {messagesPreview}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                );
              }

              case "tool.call": {
                const tool = (event.payload.tool as string) || "tool";
                const args = event.payload.args as Record<string, unknown>;

                return (
                  <div
                    key={event.id}
                    className="p-2.5 rounded-lg border border-border bg-card/40 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-mono text-xs text-foreground font-semibold">
                        <Terminal className="w-3.5 h-3.5 text-blue-400" />
                        <span>{tool}</span>
                      </div>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {formatRelativeTime(event.created_at)}
                      </span>
                    </div>

                    {args && (
                      <div>
                        <button
                          onClick={() => toggleExpand(event.id)}
                          className="text-[11px] font-mono text-muted-foreground hover:text-foreground flex items-center gap-1"
                        >
                          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          <span>args</span>
                        </button>
                        {isExpanded ? (
                          <pre className="mt-1.5 p-2 rounded bg-zinc-950 text-zinc-300 font-mono text-[11px] overflow-x-auto border border-zinc-800">
                            {JSON.stringify(args, null, 2)}
                          </pre>
                        ) : (
                          <p className="font-mono text-[11px] text-muted-foreground truncate">
                            {JSON.stringify(args)}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              }

              case "tool.result": {
                const tool = (event.payload.tool as string) || "tool";
                const output = (event.payload.output as string) || "";

                return (
                  <div
                    key={event.id}
                    className="p-2.5 rounded-lg border border-border bg-muted/30 ml-4 space-y-1"
                  >
                    <div className="flex items-center justify-between text-muted-foreground text-[11px]">
                      <span className="font-mono font-medium text-foreground flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                        result of {tool}
                      </span>
                      <span className="font-mono">{formatRelativeTime(event.created_at)}</span>
                    </div>
                    <pre className="p-2 rounded bg-zinc-950 text-zinc-300 font-mono text-[11px] whitespace-pre-wrap max-h-40 overflow-y-auto border border-zinc-800">
                      {output}
                    </pre>
                  </div>
                );
              }

              case "check.result": {
                const checkId = (event.payload.check_id as string) || "check";
                const status = (event.payload.status as string) || "pending";
                const evidence = (event.payload.evidence as string) || "";
                const score = event.payload.score as number;
                const isPass = status === "pass";

                return (
                  <div
                    key={event.id}
                    className={`p-3 rounded-lg border ${
                      isPass
                        ? "border-emerald-500/30 bg-emerald-500/[0.03]"
                        : "border-rose-500/30 bg-rose-500/[0.03]"
                    } space-y-1.5`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {isPass ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        ) : (
                          <XCircle className="w-4 h-4 text-rose-500" />
                        )}
                        <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                          Verification Check: {checkId}
                        </span>
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.2 rounded uppercase ${
                            isPass ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"
                          }`}
                        >
                          {status}
                        </span>
                      </div>

                      {score !== undefined && (
                        <span className="font-mono text-xs font-semibold text-purple-400">
                          Score: {score}/5.0
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-muted-foreground leading-relaxed pl-5">
                      {evidence}
                    </p>
                  </div>
                );
              }

              case "approval.requested": {
                const question = (event.payload.question as string) || "Human operator approval requested";
                const approvalId = (event.payload.approval_id as string) || "app";

                return (
                  <div key={event.id} className="pt-1">
                    <ApprovalCard
                      approval={{
                        id: approvalId,
                        run_id: event.run_id,
                        question,
                        options: ["Approve", "Reject"],
                        status: "pending",
                      }}
                    />
                  </div>
                );
              }

              case "error":
              case "budget.exceeded": {
                return (
                  <div
                    key={event.id}
                    className="p-3 rounded-lg border border-rose-500 bg-rose-500/10 text-rose-400 space-y-1"
                  >
                    <div className="flex items-center gap-2 font-semibold">
                      <AlertOctagon className="w-4 h-4 text-rose-500" />
                      <span>{event.type.replace(".", " ").toUpperCase()}</span>
                    </div>
                    <p className="text-xs text-rose-300">
                      {(event.payload.message as string) || JSON.stringify(event.payload)}
                    </p>
                  </div>
                );
              }

              default: {
                return (
                  <div
                    key={event.id}
                    className="p-2 rounded-lg border border-border bg-card/30 flex items-center justify-between text-muted-foreground"
                  >
                    <div className="flex items-center gap-2">
                      <Layers className="w-3.5 h-3.5 text-blue-400" />
                      <span className="font-mono text-[11px] text-foreground">{event.type}</span>
                    </div>
                    <span className="text-[10px] font-mono">{formatRelativeTime(event.created_at)}</span>
                  </div>
                );
              }
            }
          })
        )}
      </div>
    </div>
  );
}
