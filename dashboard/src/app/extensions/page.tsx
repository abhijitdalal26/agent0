"use client";

import { useEffect, useState } from "react";
import { Layers, Wrench, Sparkles, Server, CheckCircle2, AlertCircle, Play, Code } from "lucide-react";
import { getExtensions, testMcpConnection } from "@/lib/api";
import type { Extension } from "@/types";
import { EmptyState } from "@/components/ui";

export default function ExtensionsPage() {
  const [extensions, setExtensions] = useState<Extension[]>([]);
  const [activeTab, setActiveTab] = useState<"skill" | "mcp" | "plugin">("skill");
  const [selectedExt, setSelectedExt] = useState<Extension | null>(null);
  const [testResult, setTestResult] = useState<{ loading: boolean; message?: string }>({ loading: false });

  useEffect(() => {
    getExtensions(activeTab)
      .then((data) => {
        setExtensions(data);
        setSelectedExt(data[0] ?? null);
      })
      .catch(() => setExtensions([]));
  }, [activeTab]);

  const handleTestConnection = async (id: string) => {
    try {
      setTestResult({ loading: true });
      const res = await testMcpConnection(id);
      setTestResult({ loading: false, message: `${res.message} (${res.latency_ms}ms)` });
    } catch (err) {
      setTestResult({ loading: false, message: "Connection test failed." });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Layers className="w-5 h-5 text-blue-500" />
          <span>Extensions: Skills, MCP & Plugins</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Dynamic capability loader: on-demand agent skills, MCP server toolsets, and domain packs.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-2">
        <button
          onClick={() => setActiveTab("skill")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "skill"
              ? "bg-secondary text-foreground font-semibold shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Agent Skills
        </button>
        <button
          onClick={() => setActiveTab("mcp")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "mcp"
              ? "bg-secondary text-foreground font-semibold shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          MCP Servers
        </button>
        <button
          onClick={() => setActiveTab("plugin")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            activeTab === "plugin"
              ? "bg-secondary text-foreground font-semibold shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Plugins & Packs
        </button>
      </div>

      {/* Master-Detail Layout */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left List */}
        <div className="md:col-span-5 space-y-2">
          {extensions.length === 0 && (
            <EmptyState
              title={`No ${activeTab === "skill" ? "skills" : activeTab === "mcp" ? "MCP servers" : "plugins"} found`}
              hint={activeTab === "skill" ? "Drop a SKILL.md folder into the skills directory." : activeTab === "mcp" ? "Declare servers in config/mcp.yaml." : "Install a plugin pack to see it here."}
            />
          )}
          {extensions.map((ext) => {
            const isSelected = selectedExt?.id === ext.id;
            return (
              <div
                key={ext.id}
                onClick={() => {
                  setSelectedExt(ext);
                  setTestResult({ loading: false });
                }}
                className={`p-4 rounded-xl border text-xs cursor-pointer transition-all space-y-2 ${
                  isSelected
                    ? "bg-card border-blue-500/50 shadow-sm"
                    : "bg-card/40 border-border hover:bg-card/80"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-foreground font-mono">{ext.name}</span>
                  {ext.status === "connected" && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                      Connected
                    </span>
                  )}
                  {ext.runs_count !== undefined && (
                    <span className="text-[11px] font-mono text-muted-foreground">
                      {ext.runs_count} runs
                    </span>
                  )}
                </div>

                <p className="text-muted-foreground line-clamp-2 leading-relaxed">
                  {ext.description}
                </p>

                {ext.source_path && (
                  <div className="text-[10px] font-mono text-muted-foreground/60 truncate">
                    {ext.source_path}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Right Detail Pane */}
        <div className="md:col-span-7">
          {selectedExt ? (
            <div className="p-5 rounded-xl border border-border bg-card/60 space-y-4">
              <div className="flex items-start justify-between pb-3 border-b border-border">
                <div>
                  <h3 className="font-bold text-foreground text-sm font-mono">{selectedExt.name}</h3>
                  <span className="text-xs text-muted-foreground uppercase font-mono">
                    Kind: {selectedExt.kind}
                  </span>
                </div>

                {selectedExt.kind === "mcp" && (
                  <button
                    onClick={() => handleTestConnection(selectedExt.id)}
                    disabled={testResult.loading}
                    className="px-3 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>{testResult.loading ? "Pinging..." : "Test Connection"}</span>
                  </button>
                )}
              </div>

              {testResult.message && (
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-mono flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{testResult.message}</span>
                </div>
              )}

              {/* Rendered SKILL.md */}
              {selectedExt.kind === "skill" && selectedExt.content_markdown && (
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase">
                    Rendered SKILL.md
                  </span>
                  <pre className="p-4 rounded-lg bg-zinc-950 text-zinc-300 font-mono text-xs whitespace-pre-wrap border border-zinc-800 leading-relaxed max-h-96 overflow-y-auto">
                    {selectedExt.content_markdown}
                  </pre>
                </div>
              )}

              {/* MCP Toolset */}
              {selectedExt.kind === "mcp" && selectedExt.tools && (
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase">
                    Registered MCP Tools ({selectedExt.tools.length})
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    {selectedExt.tools.map((t) => (
                      <div
                        key={t}
                        className="p-2 rounded bg-muted/40 font-mono text-xs text-foreground flex items-center gap-1.5 border border-border"
                      >
                        <Wrench className="w-3.5 h-3.5 text-blue-400" />
                        <span>{t}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Plugin Bundles */}
              {selectedExt.kind === "plugin" && selectedExt.bundles && (
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-muted-foreground uppercase">
                    Pack Manifest Bundles
                  </span>
                  <div className="space-y-1.5 font-mono text-xs">
                    {selectedExt.bundles.map((b) => (
                      <div key={b} className="p-2 rounded bg-muted/40 text-foreground border border-border">
                        {b}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="p-12 text-center text-muted-foreground text-xs border border-dashed rounded-xl">
              Select an extension from the list to view configuration.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
