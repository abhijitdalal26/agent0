"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { ArrowLeft, Save, Bot, Shield, Check, History, Sparkles } from "lucide-react";
import { getAgent, updateAgent, getModelProfiles } from "@/lib/api";
import type { AgentDefinition, ModelProfile } from "@/types";

export default function AgentDetailPage({ params }: { params: Promise<{ name: string }> }) {
  const resolvedParams = use(params);
  const agentName = resolvedParams.name;

  const [agent, setAgent] = useState<AgentDefinition | null>(null);
  const [modelProfiles, setModelProfiles] = useState<ModelProfile[]>([]);
  const [instructions, setInstructions] = useState("");
  const [selectedProfile, setSelectedProfile] = useState("");
  const [tools, setTools] = useState<AgentDefinition["tools"]>([]);
  const [maxUsd, setMaxUsd] = useState<number>(1.0);
  const [maxSteps, setMaxSteps] = useState<number>(30);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([getAgent(agentName), getModelProfiles("chat")]).then(([a, profiles]) => {
      if (a) {
        setAgent(a);
        setInstructions(a.instructions);
        setSelectedProfile(a.model_profile);
        setTools(a.tools || []);
        setMaxUsd(a.budgets?.max_usd || 1.0);
        setMaxSteps(a.budgets?.max_steps || 30);
      }
      setModelProfiles(profiles);
    });
  }, [agentName]);

  const handleToolPermissionChange = (
    toolIndex: number,
    newPermission: "safe" | "needs_approval" | "forbidden"
  ) => {
    const updated = [...tools];
    updated[toolIndex].permission = newPermission;
    setTools(updated);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await updateAgent(agentName, {
        instructions,
        model_profile: selectedProfile,
        tools,
        budgets: { max_usd: maxUsd, max_steps: maxSteps },
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to update agent:", err);
    } finally {
      setSaving(false);
    }
  };

  if (!agent) {
    return (
      <div className="py-20 text-center space-y-2">
        <p className="text-muted-foreground text-xs">Loading agent specification...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-border">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
            <Link href="/agents" className="hover:text-foreground flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Agents</span>
            </Link>
            <span>/</span>
            <span className="text-foreground">{agent.name}</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <span>Agent: {agent.name}</span>
          </h1>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-sm shadow-blue-500/30 transition-all disabled:opacity-50"
        >
          {savedSuccess ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          <span>{savedSuccess ? "Saved (v+1)" : saving ? "Saving..." : "Save Configuration"}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Instructions Editor */}
        <div className="lg:col-span-8 space-y-4">
          <div className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
                  Agent System Instructions (AGENTS.md / Markdown)
                </h3>
                <p className="text-[11px] text-muted-foreground">
                  The primary role definition and behavioral constraints passed in model context.
                </p>
              </div>
            </div>

            <textarea
              rows={16}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="w-full text-xs font-mono p-3 rounded-lg border border-input bg-zinc-950 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-ring resize-y leading-relaxed"
            />
          </div>

          {/* Version History */}
          {agent.versions && (
            <div className="rounded-xl border border-border bg-card/40 p-4 space-y-2">
              <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-blue-500" />
                <span>Version History</span>
              </h3>
              <div className="divide-y divide-border text-xs font-mono">
                {agent.versions.map((ver) => (
                  <div key={ver.version} className="py-2 flex items-center justify-between text-muted-foreground">
                    <span>Version {ver.version}</span>
                    <span>{ver.updated_at}</span>
                    <span className="text-foreground">{ver.author}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Model profile, Tool permissions, Budgets */}
        <div className="lg:col-span-4 space-y-4">
          {/* Model Profile Selector */}
          <div className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Assigned Model Profile
            </h3>
            <select
              value={selectedProfile}
              onChange={(e) => setSelectedProfile(e.target.value)}
              className="w-full text-xs px-2.5 py-2 rounded-lg border border-input bg-background text-foreground focus:outline-none"
            >
              {modelProfiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.provider} · {p.tags.join(", ")})
                </option>
              ))}
            </select>
          </div>

          {/* Budgets */}
          <div className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
              Enforced Budgets
            </h3>
            <div className="space-y-2 text-xs">
              <div>
                <label className="text-muted-foreground block mb-1">Max USD per Run</label>
                <input
                  type="number"
                  step="0.1"
                  value={maxUsd}
                  onChange={(e) => setMaxUsd(parseFloat(e.target.value) || 0)}
                  className="w-full font-mono text-xs px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                />
              </div>
              <div>
                <label className="text-muted-foreground block mb-1">Max Steps before Halt</label>
                <input
                  type="number"
                  value={maxSteps}
                  onChange={(e) => setMaxSteps(parseInt(e.target.value) || 1)}
                  className="w-full font-mono text-xs px-2.5 py-1.5 rounded border border-input bg-background text-foreground"
                />
              </div>
            </div>
          </div>

          {/* Tool Permissions Matrix */}
          <div className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
            <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-blue-500" />
              <span>Tool Permissions</span>
            </h3>
            <div className="space-y-2">
              {tools.map((tool, idx) => (
                <div
                  key={tool.name}
                  className="p-2 rounded-lg border border-border bg-card/40 flex items-center justify-between text-xs"
                >
                  <div className="font-mono text-foreground">{tool.name}</div>
                  <select
                    value={tool.permission}
                    onChange={(e) =>
                      handleToolPermissionChange(idx, e.target.value as any)
                    }
                    className={`text-[11px] font-mono px-2 py-1 rounded border focus:outline-none ${
                      tool.permission === "safe"
                        ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                        : tool.permission === "needs_approval"
                        ? "bg-amber-500/10 text-amber-500 border-amber-500/20"
                        : "bg-rose-500/10 text-rose-500 border-rose-500/20"
                    }`}
                  >
                    <option value="safe">safe</option>
                    <option value="needs_approval">needs_approval</option>
                    <option value="forbidden">forbidden</option>
                  </select>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
