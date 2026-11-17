"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import {
  AlertOctagon, ArrowDown, BookOpen, Brain, CheckCircle2, ChevronDown, ChevronUp, Clock, Cpu,
  Database, Flag, Play, ShieldAlert, ShieldCheck, Sparkles, Terminal, Wand2, XCircle, MinusCircle,
} from "lucide-react";
import type { Criterion, RunEvent } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { ApprovalCard } from "./ApprovalCard";
import { RelTime } from "./ui";

interface Props {
  events: RunEvent[];
  criteria?: Criterion[];
  autoScroll?: boolean;
  showRun?: boolean;
  title?: string;
  emptyHint?: string;
  live?: boolean;
}

const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : JSON.stringify(v));
const num = (v: unknown) => (typeof v === "number" ? v : undefined);

function Row({ ev, icon, tone, label, right, showRun, children }: {
  ev: RunEvent; icon: ReactNode; tone: string; label: ReactNode; right?: ReactNode; showRun?: boolean; children?: ReactNode;
}) {
  return (
    <div className={`p-2.5 sm:p-3 rounded-lg border ${tone} space-y-1.5 min-w-0`}>
      <div className="flex items-center justify-between gap-x-2 gap-y-0.5 flex-wrap">
        <div className="flex items-center gap-1.5 min-w-0 text-xs font-medium text-foreground">
          {icon}
          <span className="truncate">{label}</span>
        </div>
        <div className="flex items-center gap-2.5 font-mono text-[11px] text-muted-foreground shrink-0">
          {right}
          {showRun && (
            <Link href={`/runs/${ev.run_id}`} className="text-blue-500 hover:underline">{ev.run_id}</Link>
          )}
          <RelTime iso={ev.created_at} />
        </div>
      </div>
      {children}
    </div>
  );
}

const Pre = ({ children, max = "max-h-48" }: { children: ReactNode; max?: string }) => (
  <pre className={`p-2 rounded bg-muted/60 text-foreground font-mono text-[11px] whitespace-pre-wrap break-words overflow-auto ${max} border border-border`}>
    {children}
  </pre>
);

function Toggle({ open, onClick, children }: { open: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button onClick={onClick} className="text-[11px] font-mono text-muted-foreground hover:text-foreground flex items-center gap-1">
      {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      {children}
    </button>
  );
}

export function EventTimeline({ events, criteria = [], autoScroll = true, showRun = false, title = "Live timeline", emptyHint, live = true }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [away, setAway] = useState(false);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const toggle = (id: string) => setOpen((p) => ({ ...p, [id]: !p[id] }));

  const critById = useMemo(() => Object.fromEntries(criteria.map((c) => [c.id, c])), [criteria]);
  const decided = useMemo(() => {
    const m: Record<string, RunEvent> = {};
    for (const e of events) if (e.type === "approval.decided") m[str(e.payload.approval_id)] = e;
    return m;
  }, [events]);

  useEffect(() => {
    const el = scrollRef.current;
    if (autoScroll && !away && el) el.scrollTop = el.scrollHeight;
  }, [events, autoScroll, away]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (el) setAway(el.scrollHeight - el.scrollTop - el.clientHeight > 60);
  };
  const jump = () => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    setAway(false);
  };

  const render = (ev: RunEvent): ReactNode => {
    const p = ev.payload;
    const isOpen = !!open[ev.id];
    const base = { ev, showRun };
    switch (ev.type) {
      case "run.started":
        return <Row {...base} icon={<Play className="w-3.5 h-3.5 text-blue-500" />} tone="border-border bg-card/40" label={<>Run started{p.title ? <span className="text-muted-foreground font-normal"> · {str(p.title)}</span> : null}</>} />;
      case "plan.created": {
        const steps = (p.steps as string[]) ?? [];
        const crit = (p.criteria as Criterion[]) ?? [];
        return (
          <Row {...base} icon={<Brain className="w-4 h-4 text-blue-500" />} tone="border-blue-500/30 bg-blue-500/[0.04]" label="Plan created">
            <div className="text-sm font-semibold text-foreground">{str(p.goal)}</div>
            {steps.length > 0 && (
              <ol className="space-y-1 pl-1">
                {steps.map((s, i) => (
                  <li key={i} className="flex gap-2 text-xs text-muted-foreground">
                    <span className="font-mono text-[10px] text-blue-500 bg-blue-500/10 rounded px-1.5 h-4 mt-0.5">{i + 1}</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ol>
            )}
            {crit.length > 0 && (
              <div className="pt-1 space-y-1">
                <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Acceptance criteria</div>
                {crit.map((c) => (
                  <div key={c.id} className="flex gap-2 text-xs">
                    <span className="font-mono text-[10px] uppercase px-1.5 rounded bg-muted text-muted-foreground h-4 mt-0.5 shrink-0">{c.type}</span>
                    <span className="text-foreground">{c.description}</span>
                  </div>
                ))}
              </div>
            )}
          </Row>
        );
      }
      case "model.call": {
        const tin = num(p.tokens_in), tout = num(p.tokens_out), cost = num(p.cost_usd), lat = num(p.latency_ms);
        const detail = str(p.messages_preview || p.messages);
        return (
          <Row
            {...base}
            icon={<Cpu className="w-3.5 h-3.5 text-purple-500" />}
            tone="border-border bg-card/60"
            label={<>{str(p.model) || "model"} <span className="text-[10px] font-mono px-1.5 rounded bg-muted text-muted-foreground">{str(p.provider)}</span>{p.profile ? <span className="text-[11px] font-mono text-muted-foreground"> {str(p.profile)}</span> : null}</>}
            right={<>
              {cost !== undefined && <span className="text-emerald-500 font-semibold">{formatCurrency(cost)}</span>}
              {lat !== undefined && <span className="flex items-center gap-1"><Clock className="w-3 h-3 opacity-60" />{lat}ms</span>}
            </>}
          >
            {tin !== undefined && (
              <div className="text-[11px] font-mono text-muted-foreground">
                {tin.toLocaleString()} in · {(tout ?? 0).toLocaleString()} out tokens
              </div>
            )}
            {detail && (
              <div>
                <Toggle open={isOpen} onClick={() => toggle(ev.id)}>messages</Toggle>
                {isOpen && <Pre>{detail}</Pre>}
              </div>
            )}
          </Row>
        );
      }
      case "tool.call":
        return (
          <Row {...base} icon={<Terminal className="w-3.5 h-3.5 text-blue-500" />} tone="border-border bg-card/40" label={<span className="font-mono font-semibold">{str(p.tool)}</span>}>
            {p.args != null && (
              <div>
                <Toggle open={isOpen} onClick={() => toggle(ev.id)}>args</Toggle>
                {isOpen ? <Pre>{JSON.stringify(p.args, null, 2)}</Pre> : <p className="font-mono text-[11px] text-muted-foreground truncate">{JSON.stringify(p.args)}</p>}
              </div>
            )}
          </Row>
        );
      case "tool.result": {
        const ok = p.ok !== false;
        const out = str(p.output);
        const long = out.length > 240;
        return (
          <Row
            {...base}
            icon={ok ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <XCircle className="w-3.5 h-3.5 text-rose-500" />}
            tone={`ml-3 sm:ml-5 ${ok ? "border-border bg-muted/30" : "border-rose-500/30 bg-rose-500/[0.04]"}`}
            label={<span className="font-mono">{str(p.tool)} {ok ? "result" : "failed"}</span>}
            right={<>{num(p.ms) !== undefined && <span>{num(p.ms)}ms</span>}{num(p.chars) !== undefined && <span>{num(p.chars)} chars</span>}</>}
          >
            <Pre max={isOpen ? "max-h-96" : "max-h-20"}>{!isOpen && long ? out.slice(0, 240) + "…" : out}</Pre>
            {long && <Toggle open={isOpen} onClick={() => toggle(ev.id)}>{isOpen ? "collapse" : "expand"}</Toggle>}
          </Row>
        );
      }
      case "skill.loaded":
        return <Row {...base} icon={<Wand2 className="w-3.5 h-3.5 text-cyan-500" />} tone="border-cyan-500/20 bg-cyan-500/[0.03]" label={<>Skill loaded <span className="font-mono">{str(p.name)}</span></>} right={num(p.chars) !== undefined ? <span>{num(p.chars)} chars</span> : null} />;
      case "memory.recalled":
        return <Row {...base} icon={<Database className="w-3.5 h-3.5 text-violet-500" />} tone="border-violet-500/20 bg-violet-500/[0.03]" label={`Memory recalled · ${num(p.facts) ?? 0} facts, ${num(p.past_runs) ?? 0} past runs`} />;
      case "memory.saved": {
        const items = (p.items as { content: string; verdict: string }[]) ?? [];
        return (
          <Row {...base} icon={<Database className="w-3.5 h-3.5 text-violet-500" />} tone="border-violet-500/20 bg-violet-500/[0.03]" label={`Memory saved · ${items.length} item${items.length === 1 ? "" : "s"}`}>
            {items.map((it, i) => (
              <div key={i} className="flex gap-2 text-xs">
                <span className="font-mono text-[10px] uppercase px-1.5 rounded bg-violet-500/10 text-violet-500 h-4 mt-0.5 shrink-0">{it.verdict}</span>
                <span className="text-muted-foreground">{it.content}</span>
              </div>
            ))}
          </Row>
        );
      }
      case "knowledge.read": {
        const ids = (p.ids as string[]) ?? [];
        return (
          <Row {...base} icon={<BookOpen className="w-3.5 h-3.5 text-teal-500" />} tone="border-teal-500/20 bg-teal-500/[0.03]" label={<>Knowledge read <span className="font-mono">{str(p.source)}</span></>} right={<span>{ids.length} record{ids.length === 1 ? "" : "s"}</span>}>
            {p.query ? <p className="text-xs text-muted-foreground line-clamp-2">&ldquo;{str(p.query)}&rdquo;</p> : null}
            {ids.length > 0 && <p className="font-mono text-[10px] text-muted-foreground break-all">{ids.join(", ")}</p>}
          </Row>
        );
      }
      case "check.result": {
        const status = str(p.status) || "pending";
        const evidence = str(p.evidence);
        const skipped = p.skipped === true || (status === "pending" && evidence.startsWith("skipped:"));
        const score = num(p.score);
        const c = critById[str(p.check_id)];
        const tone = skipped ? "border-border bg-muted/30" : status === "pass" ? "border-emerald-500/30 bg-emerald-500/[0.04]" : status === "pending" ? "border-border bg-card/40" : "border-rose-500/30 bg-rose-500/[0.04]";
        const icon = skipped ? <MinusCircle className="w-4 h-4 text-muted-foreground" /> : status === "pass" ? <CheckCircle2 className="w-4 h-4 text-emerald-500" /> : status === "pending" ? <Clock className="w-4 h-4 text-muted-foreground" /> : <XCircle className="w-4 h-4 text-rose-500" />;
        const chip = skipped ? "bg-muted text-muted-foreground" : status === "pass" ? "bg-emerald-500/15 text-emerald-500" : status === "pending" ? "bg-muted text-muted-foreground" : "bg-rose-500/15 text-rose-500";
        return (
          <Row {...base} icon={icon} tone={tone}
            label={<>Check <span className="font-mono">{str(p.check_id)}</span> <span className={`ml-1 text-[10px] font-mono px-1.5 rounded uppercase ${chip}`}>{skipped ? "skipped" : status}</span></>}
            right={score !== undefined ? <span className="text-purple-500 font-semibold">judge {score}</span> : null}>
            {c && <p className="text-xs text-foreground pl-5">{c.description}</p>}
            {evidence && <p className="text-xs text-muted-foreground leading-relaxed pl-5 break-words">{evidence}</p>}
          </Row>
        );
      }
      case "approval.requested": {
        const id = str(p.approval_id);
        const d = decided[id];
        const decision = d ? str(d.payload.decision) : "";
        return (
          <div className="min-w-0">
            <ApprovalCard
              approval={{
                id, run_id: ev.run_id, question: str(p.question) || "Approval requested",
                options: (p.options as string[]) ?? ["Approve", "Reject"],
                status: !d ? "pending" : decision.startsWith("approve") ? "approved" : "rejected",
                decided_by: d ? str(d.payload.by) : undefined, decided_at: d?.created_at,
              }}
              hideRunLink={!showRun}
            />
          </div>
        );
      }
      case "approval.decided": {
        const ok = str(p.decision).startsWith("approve");
        return <Row {...base} icon={<ShieldCheck className={`w-3.5 h-3.5 ${ok ? "text-emerald-500" : "text-rose-500"}`} />} tone="border-border bg-card/40" label={`Approval ${ok ? "approved" : "rejected"}${p.by ? ` by ${str(p.by)}` : ""}`} />;
      }
      case "error":
      case "budget.exceeded":
        return (
          <Row {...base} icon={<AlertOctagon className="w-4 h-4 text-rose-500" />} tone="border-rose-500/50 bg-rose-500/10" label={<span className="text-rose-500 uppercase tracking-wide">{ev.type === "error" ? "Error" : "Budget exceeded"}</span>}>
            <p className="text-xs text-rose-600 dark:text-rose-300 break-words">{str(p.message || p.reason) || JSON.stringify(p)}</p>
          </Row>
        );
      case "run.finished": {
        const st = str(p.status);
        const good = st === "succeeded";
        return (
          <Row {...base} icon={<Flag className={`w-3.5 h-3.5 ${good ? "text-emerald-500" : st === "failed" ? "text-rose-500" : "text-zinc-500"}`} />}
            tone={good ? "border-emerald-500/30 bg-emerald-500/[0.04]" : st === "failed" ? "border-rose-500/30 bg-rose-500/[0.04]" : "border-border bg-card/40"}
            label={`Run ${st || "finished"}${num(p.attempts) ? ` after ${num(p.attempts)} attempt${num(p.attempts) === 1 ? "" : "s"}` : ""}`}
            right={num(p.cost_usd) !== undefined ? <span className="text-emerald-500 font-semibold">{formatCurrency(num(p.cost_usd))}</span> : null} />
        );
      }
      default:
        return <Row {...base} icon={<ShieldAlert className="w-3.5 h-3.5 text-muted-foreground" />} tone="border-border bg-card/30" label={<span className="font-mono">{String(ev.type)}</span>} />;
    }
  };

  return (
    <div className="relative flex flex-col h-full min-h-[320px] bg-card/50 rounded-xl border border-border overflow-hidden">
      <div className="px-3 sm:px-4 py-2.5 border-b border-border bg-card/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2 h-2 rounded-full shrink-0 ${live ? "bg-blue-500 animate-pulse" : "bg-zinc-500"}`} />
          <h3 className="text-xs font-semibold uppercase tracking-wide truncate">{title}</h3>
          <span className="text-[11px] font-mono text-muted-foreground px-1.5 rounded bg-muted">{events.length}</span>
        </div>
        {away && (
          <button onClick={jump} className="text-[11px] font-medium text-blue-500 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-0.5 rounded-full border border-blue-500/20 flex items-center gap-1 shrink-0">
            <ArrowDown className="w-3 h-3" />Jump to latest
          </button>
        )}
      </div>
      <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto p-2.5 sm:p-4 space-y-2.5 text-xs">
        {events.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground space-y-1">
            <Sparkles className="w-7 h-7 mx-auto opacity-40" />
            <p className="text-sm font-medium text-foreground">No events yet</p>
            <p>{emptyHint ?? "Events appear here as the agent plans, calls models and tools, and verifies its work."}</p>
          </div>
        ) : (
          events.map((ev) => <div key={ev.id}>{render(ev)}</div>)
        )}
      </div>
    </div>
  );
}
