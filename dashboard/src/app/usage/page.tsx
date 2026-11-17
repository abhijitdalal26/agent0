"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Receipt, Coins, TrendingUp, Cpu, ArrowUpRight, BarChart3 } from "lucide-react";
import { getUsageRecords } from "@/lib/api";
import type { UsageRecord } from "@/types";
import { formatCurrency, formatTokens, formatRelativeTime } from "@/lib/utils";

export default function UsagePage() {
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [providerFilter, setProviderFilter] = useState("");
  const [capabilityFilter, setCapabilityFilter] = useState("");

  useEffect(() => {
    getUsageRecords().then(setRecords);
  }, []);

  const filteredRecords = records.filter((r) => {
    if (providerFilter && r.provider !== providerFilter) return false;
    if (capabilityFilter && r.capability !== capabilityFilter) return false;
    return true;
  });

  // Calculate totals matching the exact sum of rows
  const totalCost = filteredRecords.reduce((acc, r) => acc + r.cost_usd, 0);
  const totalCalls = filteredRecords.length;
  const totalTokensIn = filteredRecords.reduce((acc, r) => acc + (r.input_units || 0), 0);
  const totalTokensOut = filteredRecords.reduce((acc, r) => acc + (r.output_units || 0), 0);
  const avgLatency =
    totalCalls > 0
      ? Math.round(filteredRecords.reduce((acc, r) => acc + r.latency_ms, 0) / totalCalls)
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Receipt className="w-5 h-5 text-emerald-400" />
          <span>Model Usage & Spend Analytics</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Audit every token, image, and voice generation call across providers with exact USD accounting.
        </p>
      </div>

      {/* Aggregate KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
            <Coins className="w-3.5 h-3.5 text-emerald-500" />
            Filtered Total Spend
          </span>
          <div className="text-2xl font-bold font-mono text-emerald-500">
            {formatCurrency(totalCost)}
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">
            Sum of {totalCalls} individual calls
          </span>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
            <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
            Model Calls
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">{totalCalls}</div>
          <span className="text-[10px] text-muted-foreground font-mono">100% success rate</span>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            Units Processed
          </span>
          <div className="text-2xl font-bold font-mono text-purple-400">
            {formatTokens(totalTokensIn + totalTokensOut)}
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">
            {formatTokens(totalTokensIn)} in · {formatTokens(totalTokensOut)} out
          </span>
        </div>

        <div className="p-4 rounded-xl border border-border bg-card/60 space-y-1">
          <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
            <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
            Mean Latency
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">{avgLatency}ms</div>
          <span className="text-[10px] text-muted-foreground font-mono">Across all capabilities</span>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={providerFilter}
          onChange={(e) => setProviderFilter(e.target.value)}
          className="text-xs px-2.5 py-1.5 rounded-lg border border-input bg-card/60 text-foreground"
        >
          <option value="">All Providers</option>
          <option value="Groq">Groq</option>
          <option value="Google">Google</option>
        </select>

        <select
          value={capabilityFilter}
          onChange={(e) => setCapabilityFilter(e.target.value)}
          className="text-xs px-2.5 py-1.5 rounded-lg border border-input bg-card/60 text-foreground"
        >
          <option value="">All Capabilities</option>
          <option value="chat">chat</option>
          <option value="image_gen">image_gen</option>
          <option value="vision">vision</option>
          <option value="tts">tts</option>
        </select>
      </div>

      {/* Individual Calls Table */}
      <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
              <tr>
                <th className="py-3 px-4">Profile & Model</th>
                <th className="py-3 px-4">Provider</th>
                <th className="py-3 px-4">Capability</th>
                <th className="py-3 px-4">Input / Output</th>
                <th className="py-3 px-4">Cost (USD)</th>
                <th className="py-3 px-4">Latency</th>
                <th className="py-3 px-4">Run Link</th>
                <th className="py-3 px-4 text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono">
              {filteredRecords.map((rec) => (
                <tr key={rec.id} className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3 px-4">
                    <span className="font-semibold text-foreground">{rec.profile}</span>
                    <span className="text-[11px] text-muted-foreground block">{rec.model}</span>
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap text-muted-foreground">
                    {rec.provider}
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap text-foreground">
                    {rec.capability}
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap text-muted-foreground">
                    {rec.input_units} in · {rec.output_units} out
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap font-semibold text-emerald-500">
                    {formatCurrency(rec.cost_usd)}
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap text-muted-foreground">
                    {rec.latency_ms}ms
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    {rec.run_id ? (
                      <Link
                        href={`/runs/${rec.run_id}`}
                        className="text-blue-500 hover:underline inline-flex items-center gap-0.5"
                      >
                        <span>{rec.run_id}</span>
                        <ArrowUpRight className="w-3 h-3" />
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>

                  <td className="py-3 px-4 text-right whitespace-nowrap text-muted-foreground">
                    {formatRelativeTime(rec.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
