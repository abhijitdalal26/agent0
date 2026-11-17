"use client";

import { useEffect, useState } from "react";
import { Cpu, Sparkles, Key, Zap, CheckCircle2, XCircle, ArrowRight, Gauge, DollarSign } from "lucide-react";
import { getModelProfiles, getRouterPreview } from "@/lib/api";
import type { ModelProfile, Capability } from "@/types";
import { formatCurrency } from "@/lib/utils";

const CAPABILITY_TABS: { id: Capability | "all"; label: string }[] = [
  { id: "all", label: "All Models" },
  { id: "chat", label: "Chat & Tools" },
  { id: "vision", label: "Vision" },
  { id: "image_gen", label: "Image Gen" },
  { id: "tts", label: "Voice (TTS)" },
  { id: "stt", label: "Speech-to-Text" },
  { id: "embedding", label: "Embeddings" },
];

export default function ModelsPage() {
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [selectedTab, setSelectedTab] = useState<Capability | "all">("all");
  const [routerCapability, setRouterCapability] = useState<Capability>("chat");
  const [routerPrefer, setRouterPrefer] = useState<"cheap" | "fast" | "smart">("fast");
  const [routerPreview, setRouterPreview] = useState<{ profile: ModelProfile; reason: string } | null>(null);

  useEffect(() => {
    getModelProfiles(selectedTab).then(setProfiles);
  }, [selectedTab]);

  useEffect(() => {
    getRouterPreview(routerCapability, routerPrefer).then(setRouterPreview);
  }, [routerCapability, routerPrefer]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Cpu className="w-5 h-5 text-purple-400" />
          <span>Model Registry & Provider Router</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Multi-provider configuration, latency & cost benchmarks, and dynamic capability routing.
        </p>
      </div>

      {/* Router Preview Interactive Sandbox */}
      <div className="p-4 rounded-xl border border-border bg-gradient-to-r from-purple-500/[0.05] via-blue-500/[0.05] to-transparent space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Dynamic Router Live Simulator
            </h3>
          </div>
          <span className="text-[11px] text-muted-foreground">
            Agents ask for a capability, not a model profile.
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Capability:</span>
            <select
              value={routerCapability}
              onChange={(e) => setRouterCapability(e.target.value as Capability)}
              className="text-xs font-mono px-2 py-1 rounded border border-input bg-background text-foreground"
            >
              <option value="chat">chat</option>
              <option value="vision">vision</option>
              <option value="image_gen">image_gen</option>
              <option value="tts">tts</option>
              <option value="stt">stt</option>
              <option value="embedding">embedding</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Preference:</span>
            <select
              value={routerPrefer}
              onChange={(e) => setRouterPrefer(e.target.value as any)}
              className="text-xs font-mono px-2 py-1 rounded border border-input bg-background text-foreground"
            >
              <option value="fast">fast (Lowest Latency)</option>
              <option value="cheap">cheap (Lowest Token Cost)</option>
              <option value="smart">smart (Highest Reasoning)</option>
            </select>
          </div>
        </div>

        {routerPreview && (
          <div className="p-3 rounded-lg bg-card border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2 font-mono">
                <span className="text-foreground font-semibold">Router selects:</span>
                <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20 font-bold">
                  {routerPreview.profile.name}
                </span>
                <span className="text-muted-foreground font-sans">({routerPreview.profile.provider})</span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {routerPreview.reason}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Capability Tabs */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-border pb-2">
        {CAPABILITY_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSelectedTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              selectedTab === tab.id
                ? "bg-secondary text-foreground font-semibold shadow-sm"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Model Profiles Table */}
      <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
              <tr>
                <th className="py-3 px-4">Profile</th>
                <th className="py-3 px-4">Provider</th>
                <th className="py-3 px-4">Capability</th>
                <th className="py-3 px-4">Tags</th>
                <th className="py-3 px-4">Cost Structure</th>
                <th className="py-3 px-4">API Key Status</th>
                <th className="py-3 px-4">7d Benchmarks</th>
                <th className="py-3 px-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {profiles.map((p) => (
                <tr key={p.id} className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3 px-4">
                    <div className="font-semibold text-foreground font-mono">{p.name}</div>
                    <div className="text-[11px] text-muted-foreground font-mono">{p.model}</div>
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono text-[11px]">
                      {p.provider}
                    </span>
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap font-mono text-foreground">
                    {p.capability}
                  </td>

                  <td className="py-3 px-4">
                    <div className="flex flex-wrap gap-1">
                      {p.tags.map((tag) => (
                        <span
                          key={tag}
                          className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-blue-500/10 text-blue-400"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>

                  <td className="py-3 px-4 font-mono text-muted-foreground text-[11px] whitespace-nowrap">
                    {p.cost.input_per_mtok !== undefined && (
                      <div>
                        ${p.cost.input_per_mtok}/M in · ${p.cost.output_per_mtok}/M out
                      </div>
                    )}
                    {p.cost.per_image !== undefined && <div>${p.cost.per_image} / image</div>}
                    {p.cost.per_1k_chars !== undefined && (
                      <div>${p.cost.per_1k_chars} / 1k chars</div>
                    )}
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    {p.key_configured ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                        <Key className="w-3 h-3" />
                        Configured
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-500 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                        Missing
                      </span>
                    )}
                  </td>

                  <td className="py-3 px-4 font-mono text-xs whitespace-nowrap">
                    {p.stats ? (
                      <div className="space-y-0.5 text-[11px] text-muted-foreground">
                        <div>
                          Pass: <strong className="text-foreground">{p.stats.pass_rate}%</strong> ·{" "}
                          {p.stats.avg_latency_ms}ms avg
                        </div>
                        <div>{p.stats.calls_7d} calls · err: {p.stats.error_rate}%</div>
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>

                  <td className="py-3 px-4 text-right whitespace-nowrap">
                    <span
                      className={`inline-block w-2.5 h-2.5 rounded-full ${
                        p.enabled ? "bg-emerald-500" : "bg-zinc-600"
                      }`}
                      title={p.enabled ? "Enabled" : "Disabled"}
                    />
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
