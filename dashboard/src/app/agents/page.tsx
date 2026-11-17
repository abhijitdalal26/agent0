"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, ArrowRight, Wrench, CheckCircle2, Cpu, Coins, Shield } from "lucide-react";
import { getAgents } from "@/lib/api";
import type { AgentDefinition } from "@/types";
import { formatCurrency } from "@/lib/utils";

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAgents().then((data) => {
      setAgents(data);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Bot className="w-5 h-5 text-blue-500" />
          <span>Agent Definitions & Roles</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Autonomous agents, system instructions, tool permission policies, and cost envelopes.
        </p>
      </div>

      {/* Agents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {agents.map((agent) => (
          <Link
            key={agent.id}
            href={`/agents/${agent.name}`}
            className="group p-5 rounded-xl border border-border bg-card/60 hover:bg-card hover:border-blue-500/40 transition-all space-y-4 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500 group-hover:scale-105 transition-transform">
                    <Bot className="w-4 h-4" />
                  </div>
                  <h3 className="font-semibold text-foreground text-sm font-mono group-hover:text-blue-500 transition-colors">
                    {agent.name}
                  </h3>
                </div>

                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground flex items-center gap-1">
                  <Cpu className="w-3 h-3 text-purple-400" />
                  {agent.model_profile}
                </span>
              </div>

              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {agent.description}
              </p>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2 py-3 border-y border-border/40 text-xs font-mono">
              <div>
                <span className="text-[10px] text-muted-foreground block">Tools</span>
                <span className="font-semibold text-foreground">{agent.tool_count} active</span>
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground block">7d Pass Rate</span>
                <span className="font-semibold text-emerald-500">{agent.success_rate}%</span>
              </div>
              <div>
                <span className="text-[10px] text-muted-foreground block">Avg Cost</span>
                <span className="font-semibold text-foreground">{formatCurrency(agent.avg_cost)}</span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
              <span>{agent.runs_7d} runs in past 7 days</span>
              <span className="text-blue-500 group-hover:translate-x-1 transition-transform flex items-center gap-1 font-medium">
                <span>Configure Agent</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
