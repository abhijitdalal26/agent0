"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BarChart3, Coins, Cpu, TrendingUp } from "lucide-react";
import { getUsageRecords } from "@/lib/api";
import type { UsageRecord } from "@/types";
import { formatCurrency, formatTokens } from "@/lib/utils";
import { EmptyState, PageHeader, RelTime, Skeleton } from "@/components/ui";

const PALETTE = ["#3b82f6", "#a855f7", "#10b981", "#f59e0b", "#06b6d4", "#f43f5e", "#84cc16"];
const PAGE = 50;
const sel = "text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground min-w-0";

type Rec = UsageRecord & { agent?: string };

function Card({ title, children, className = "" }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`p-3.5 sm:p-4 rounded-xl border border-border bg-card/60 space-y-3 min-w-0 ${className}`}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </div>
  );
}

function SpendChart({ rows, colorOf }: { rows: Rec[]; colorOf: (p: string) => string }) {
  const { buckets, providers, max } = useMemo(() => {
    const ts = rows.map((r) => Date.parse(r.created_at));
    const hourly = Math.max(...ts) - Math.min(...ts) < 2 * 86400000;
    const key = (iso: string) => (hourly ? iso.slice(0, 13) : iso.slice(0, 10));
    const m = new Map<string, Map<string, number>>();
    for (const r of rows) {
      const k = key(r.created_at);
      const b = m.get(k) ?? new Map<string, number>();
      b.set(r.provider, (b.get(r.provider) ?? 0) + r.cost_usd);
      m.set(k, b);
    }
    const buckets = [...m.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => ({ k, v, total: [...v.values()].reduce((a, b) => a + b, 0) }));
    return { buckets, providers: [...new Set(rows.map((r) => r.provider))], max: Math.max(...buckets.map((b) => b.total), 1e-9) };
  }, [rows]);

  const W = 560, H = 160, padL = 44, padB = 22, n = buckets.length;
  const bw = Math.min(36, (W - padL) / Math.max(n, 1) - 6);
  return (
    <div className="space-y-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Spend over time by provider">
        {[0, 0.5, 1].map((f) => {
          const y = H - padB - f * (H - padB - 8);
          return (
            <g key={f}>
              <line x1={padL} x2={W} y1={y} y2={y} stroke="currentColor" opacity={0.12} />
              <text x={padL - 6} y={y + 3} textAnchor="end" fontSize="9" fill="currentColor" opacity={0.6}>{formatCurrency(max * f)}</text>
            </g>
          );
        })}
        {buckets.map((b, i) => {
          const x = padL + 6 + i * ((W - padL - 6) / n) + ((W - padL - 6) / n - bw) / 2;
          let y = H - padB;
          return (
            <g key={b.k}>
              {providers.map((p) => {
                const v = b.v.get(p) ?? 0;
                if (!v) return null;
                const h = (v / max) * (H - padB - 8);
                y -= h;
                return <rect key={p} x={x} y={y} width={bw} height={Math.max(h, 1)} fill={colorOf(p)} rx={1.5}><title>{`${b.k} · ${p}: ${formatCurrency(v)}`}</title></rect>;
              })}
              {(n <= 8 || i % Math.ceil(n / 8) === 0) && (
                <text x={x + bw / 2} y={H - 6} textAnchor="middle" fontSize="9" fill="currentColor" opacity={0.6}>{b.k.length > 10 ? b.k.slice(11) + "h" : b.k.slice(5)}</text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        {providers.map((p) => (
          <span key={p} className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: colorOf(p) }} />{p}</span>
        ))}
      </div>
    </div>
  );
}

function Bars({ items, format, color }: { items: { label: string; value: number; sub?: string }[]; format: (n: number) => string; color: (l: string) => string }) {
  const max = Math.max(...items.map((i) => i.value), 1e-9);
  return (
    <div className="space-y-2">
      {items.map((i) => (
        <div key={i.label} className="space-y-1">
          <div className="flex justify-between gap-2 text-xs font-mono">
            <span className="truncate">{i.label}</span>
            <span className="text-muted-foreground shrink-0">{i.sub ? `${i.sub} · ` : ""}{format(i.value)}</span>
          </div>
          <div className="h-2 rounded bg-muted overflow-hidden">
            <div className="h-full rounded" style={{ width: `${Math.max((i.value / max) * 100, i.value > 0 ? 2 : 0)}%`, background: color(i.label) }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function UsagePage() {
  const [records, setRecords] = useState<Rec[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [provider, setProvider] = useState("");
  const [capability, setCapability] = useState("");
  const [agent, setAgent] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    getUsageRecords().then((r) => setRecords(r as Rec[])).catch(() => setError(true)).finally(() => setLoading(false));
  }, []);

  const opts = (f: (r: Rec) => string | undefined) => [...new Set(records.map(f).filter(Boolean) as string[])].sort();
  const providers = useMemo(() => opts((r) => r.provider), [records]); // eslint-disable-line react-hooks/exhaustive-deps
  const capabilities = useMemo(() => opts((r) => r.capability), [records]); // eslint-disable-line react-hooks/exhaustive-deps
  const agents = useMemo(() => opts((r) => r.agent), [records]); // eslint-disable-line react-hooks/exhaustive-deps
  const colorOf = (p: string) => PALETTE[Math.max(providers.indexOf(p), 0) % PALETTE.length];

  const rows = useMemo(
    () =>
      records
        .filter((r) => {
          const d = r.created_at.slice(0, 10);
          return (!provider || r.provider === provider) && (!capability || r.capability === capability) && (!agent || r.agent === agent) && (!from || d >= from) && (!to || d <= to);
        })
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [records, provider, capability, agent, from, to],
  );

  const agg = useMemo(() => {
    const cost = rows.reduce((a, r) => a + r.cost_usd, 0);
    const errs = rows.filter((r) => !r.ok).length;
    const byCap = new Map<string, { n: number; cost: number }>();
    const byProv = new Map<string, { n: number; err: number }>();
    const byRun = new Map<string, number>();
    for (const r of rows) {
      const c = byCap.get(r.capability) ?? { n: 0, cost: 0 };
      byCap.set(r.capability, { n: c.n + 1, cost: c.cost + r.cost_usd });
      const p = byProv.get(r.provider) ?? { n: 0, err: 0 };
      byProv.set(r.provider, { n: p.n + 1, err: p.err + (r.ok ? 0 : 1) });
      if (r.run_id) byRun.set(r.run_id, (byRun.get(r.run_id) ?? 0) + r.cost_usd);
    }
    return {
      cost,
      errs,
      units: rows.reduce((a, r) => a + (r.input_units || 0) + (r.output_units || 0), 0),
      latency: rows.length ? Math.round(rows.reduce((a, r) => a + r.latency_ms, 0) / rows.length) : 0,
      byCap: [...byCap.entries()].map(([label, v]) => ({ label, value: v.n, sub: formatCurrency(v.cost) })).sort((a, b) => b.value - a.value),
      byProv: [...byProv.entries()].map(([label, v]) => ({ label, value: (v.err / v.n) * 100, sub: `${v.err}/${v.n}` })),
      topRuns: [...byRun.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
    };
  }, [rows]);

  const filtered = !!(provider || capability || agent || from || to);

  return (
    <div className="space-y-4 sm:space-y-6">
      <PageHeader title="Usage" description="Every model call with exact cost. Totals always equal the sum of the rows below." />

      <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2">
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={sel} aria-label="From date" />
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={sel} aria-label="To date" />
        <select value={provider} onChange={(e) => setProvider(e.target.value)} className={sel} aria-label="Provider">
          <option value="">All providers</option>
          {providers.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select value={capability} onChange={(e) => setCapability(e.target.value)} className={sel} aria-label="Capability">
          <option value="">All capabilities</option>
          {capabilities.map((p) => <option key={p}>{p}</option>)}
        </select>
        {agents.length > 0 && (
          <select value={agent} onChange={(e) => setAgent(e.target.value)} className={sel} aria-label="Agent">
            <option value="">All agents</option>
            {agents.map((p) => <option key={p}>{p}</option>)}
          </select>
        )}
        {filtered && <button onClick={() => { setProvider(""); setCapability(""); setAgent(""); setFrom(""); setTo(""); }} className="text-xs px-2.5 py-2 text-blue-500 hover:underline">Clear</button>}
      </div>

      {loading ? (
        <Skeleton rows={4} />
      ) : error ? (
        <EmptyState title="Could not load usage" hint="Check the API connection and reload." />
      ) : rows.length === 0 ? (
        <EmptyState title={filtered ? "No calls match these filters" : "No model calls yet"} hint={filtered ? "Widen the date range or clear a filter." : "Usage is recorded as soon as an agent calls a model."} />
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 sm:gap-3">
            {[
              [<Coins key="a" className="w-3.5 h-3.5 text-emerald-500" />, "Total spend", formatCurrency(agg.cost), "text-emerald-500", `${rows.length} calls`],
              [<BarChart3 key="b" className="w-3.5 h-3.5 text-blue-500" />, "Error rate", `${((agg.errs / rows.length) * 100).toFixed(1)}%`, agg.errs ? "text-rose-500" : "text-foreground", `${agg.errs} failed`],
              [<Cpu key="c" className="w-3.5 h-3.5 text-purple-500" />, "Units", formatTokens(agg.units), "text-purple-500", "tokens, images, chars"],
              [<TrendingUp key="d" className="w-3.5 h-3.5 text-cyan-500" />, "Mean latency", `${agg.latency}ms`, "text-foreground", "all capabilities"],
            ].map(([icon, label, value, tone, sub]) => (
              <div key={label as string} className="p-3 sm:p-4 rounded-xl border border-border bg-card/60 space-y-1">
                <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">{icon}{label}</span>
                <div className={`text-xl sm:text-2xl font-bold font-mono ${tone}`}>{value}</div>
                <span className="text-[10px] text-muted-foreground font-mono">{sub}</span>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4">
            <Card title="Spend over time" className="lg:col-span-2"><SpendChart rows={rows} colorOf={colorOf} /></Card>
            <Card title="Calls by capability"><Bars items={agg.byCap} format={(n) => `${n} calls`} color={() => "#3b82f6"} /></Card>
            <Card title="Error rate by provider"><Bars items={agg.byProv} format={(n) => `${n.toFixed(1)}%`} color={(l) => (agg.byProv.find((p) => p.label === l)?.value ? "#f43f5e" : "#10b981")} /></Card>
            <Card title="Top runs by cost" className="lg:col-span-2">
              {agg.topRuns.length === 0 ? (
                <p className="text-xs text-muted-foreground">No calls are linked to a run in this selection.</p>
              ) : (
                <div className="divide-y divide-border">
                  {agg.topRuns.map(([id, cost]) => (
                    <Link key={id} href={`/runs/${id}`} className="py-2 flex justify-between text-xs font-mono hover:text-blue-500">
                      <span className="flex items-center gap-1">{id}<ArrowUpRight className="w-3 h-3" /></span>
                      <span className="text-emerald-500 font-semibold">{formatCurrency(cost)}</span>
                    </Link>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
                  <tr>{["Profile", "Provider", "Capability", "In / Out", "Cost", "Latency", "Result", "Run", "Time"].map((h) => <th key={h} className="py-3 px-4 whitespace-nowrap">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-border font-mono">
                  {rows.slice(0, limit).map((r) => (
                    <tr key={r.id} className="hover:bg-secondary/30">
                      <td className="py-2.5 px-4"><span className="font-semibold">{r.profile}</span><span className="text-[11px] text-muted-foreground block">{r.model}</span></td>
                      <td className="py-2.5 px-4 whitespace-nowrap"><span className="inline-block w-2 h-2 rounded-sm mr-1.5" style={{ background: colorOf(r.provider) }} />{r.provider}</td>
                      <td className="py-2.5 px-4 whitespace-nowrap">{r.capability}</td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-muted-foreground">{r.input_units} / {r.output_units}</td>
                      <td className="py-2.5 px-4 whitespace-nowrap font-semibold text-emerald-500">{formatCurrency(r.cost_usd)}</td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-muted-foreground">{r.latency_ms}ms</td>
                      <td className="py-2.5 px-4 whitespace-nowrap">{r.ok ? <span className="text-emerald-500">ok</span> : <span className="text-rose-500">error</span>}</td>
                      <td className="py-2.5 px-4 whitespace-nowrap">
                        {r.run_id ? <Link href={`/runs/${r.run_id}`} className="text-blue-500 hover:underline inline-flex items-center gap-0.5">{r.run_id}<ArrowUpRight className="w-3 h-3" /></Link> : <span className="text-muted-foreground">—</span>}
                      </td>
                      <td className="py-2.5 px-4 whitespace-nowrap text-muted-foreground"><RelTime iso={r.created_at} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rows.length > limit && (
              <button onClick={() => setLimit((l) => l + PAGE)} className="w-full py-2.5 text-xs text-blue-500 hover:bg-secondary/40 border-t border-border">
                Show more ({rows.length - limit} remaining)
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
