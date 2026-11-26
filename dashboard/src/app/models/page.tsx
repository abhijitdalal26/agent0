"use client";

import { useEffect, useState } from "react";
import {
  Key,
  Zap,
  Plus,
  Video,
  Image as ImageIcon,
  Volume2,
  Mic,
  Eye,
  Edit2,
} from "lucide-react";
import { getModelProfiles, getRouterPreview } from "@/lib/api";
import type { ModelProfile, Capability } from "@/types";
import { EmptyState, PageHeader, Skeleton } from "@/components/ui";
import { AddEditProfileModal } from "@/components/AddEditProfileModal";

const CAPABILITY_TABS: { id: Capability | "all"; label: string; icon?: any }[] = [
  { id: "all", label: "All Models" },
  { id: "chat", label: "Chat & Tools" },
  { id: "vision", label: "Vision" },
  { id: "image_gen", label: "Image Gen" },
  { id: "video_gen", label: "Video Gen" },
  { id: "tts", label: "Voice / TTS" },
  { id: "stt", label: "Speech-to-Text" },
  { id: "embedding", label: "Embeddings" },
];

export default function ModelsPage() {
  const [all, setAll] = useState<ModelProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [previewState, setPreviewState] = useState<"loading" | "ok" | "none">("loading");
  const [selectedTab, setSelectedTab] = useState<Capability | "all">("all");
  const [routerCapability, setRouterCapability] = useState<Capability>("chat");
  const [routerPrefer, setRouterPrefer] = useState<"cheap" | "fast" | "smart">("fast");
  const [routerPreview, setRouterPreview] = useState<{ profile: ModelProfile; reason: string } | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<ModelProfile | null>(null);

  useEffect(() => {
    getModelProfiles()
      .then((p) => {
        setAll(p);
        setLoadError(false);
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    let live = true;
    setPreviewState("loading");
    getRouterPreview(routerCapability, routerPrefer)
      .then((r) => {
        if (!live) return;
        setRouterPreview(r?.profile ? r : null);
        setPreviewState(r?.profile ? "ok" : "none");
      })
      .catch(() => {
        if (!live) return;
        setRouterPreview(null);
        setPreviewState("none");
      });
    return () => {
      live = false;
    };
  }, [routerCapability, routerPrefer]);

  const profiles = selectedTab === "all" ? all : all.filter((p) => p.capability === selectedTab);
  const count = (id: Capability | "all") => (id === "all" ? all.length : all.filter((p) => p.capability === id).length);

  const handleSaveProfile = (newProfile: Partial<ModelProfile> & { apiKey?: string }) => {
    setAll((prev) => {
      const idx = prev.findIndex((p) => p.id === newProfile.id);
      if (idx !== -1) {
        const updated = [...prev];
        updated[idx] = { ...updated[idx], ...newProfile } as ModelProfile;
        return updated;
      }
      return [newProfile as ModelProfile, ...prev];
    });
  };

  const getCapabilityBadge = (cap: Capability) => {
    switch (cap) {
      case "image_gen":
        return <span className="text-emerald-400 font-mono flex items-center gap-1"><ImageIcon className="w-3 h-3" /> image</span>;
      case "video_gen":
        return <span className="text-cyan-400 font-mono flex items-center gap-1"><Video className="w-3 h-3" /> video</span>;
      case "tts":
        return <span className="text-purple-400 font-mono flex items-center gap-1"><Volume2 className="w-3 h-3" /> voice</span>;
      case "stt":
        return <span className="text-amber-400 font-mono flex items-center gap-1"><Mic className="w-3 h-3" /> stt</span>;
      case "vision":
        return <span className="text-blue-400 font-mono flex items-center gap-1"><Eye className="w-3 h-3" /> vision</span>;
      case "chat":
      default:
        return <span className="text-foreground font-mono">chat</span>;
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Models"
        description="Provider profiles, credentials and the routing policy agents use."
      >
        <button
          onClick={() => {
            setEditingProfile(null);
            setIsModalOpen(true);
          }}
          className="inline-flex items-center justify-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Add profile</span>
        </button>
      </PageHeader>

      {/* Router Preview */}
      <div className="p-4 rounded-xl border border-border bg-card/60 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="text-sm font-semibold text-foreground">
              Router preview
            </h3>
          </div>
          <span className="text-[11px] text-muted-foreground">
            Agents ask for a capability, not a model.
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
              <option value="chat">chat (Text & Code)</option>
              <option value="vision">vision (Multimodal)</option>
              <option value="image_gen">image_gen (Image Assets)</option>
              <option value="video_gen">video_gen (Video Clips)</option>
              <option value="tts">tts (Voice Synthesis)</option>
              <option value="stt">stt (Speech-to-Text)</option>
              <option value="embedding">embedding (Vectors)</option>
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

        {previewState === "none" && (
          <div className="p-3 rounded-lg bg-card border border-dashed border-border text-xs text-muted-foreground">
            No enabled profile with a configured key can serve <span className="font-mono">{routerCapability}</span>. Add a profile or set its API key.
          </div>
        )}
        {previewState === "loading" && <div className="h-14 rounded-lg bg-muted/50 animate-pulse" />}
        {previewState === "ok" && routerPreview && (
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
              {routerPreview.profile.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {routerPreview.profile.tags.map((t) => (
                    <span key={t} className="px-1.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-400">{t}</span>
                  ))}
                </div>
              )}
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
            <span className="ml-1.5 font-mono text-[10px] text-muted-foreground">{count(tab.id)}</span>
          </button>
        ))}
      </div>

      {/* Model Profiles Table */}
      {loading ? (
        <Skeleton rows={4} />
      ) : loadError ? (
        <EmptyState title="Could not load model profiles" hint="Check the API connection and reload." />
      ) : profiles.length === 0 ? (
        <EmptyState
          title={selectedTab === "all" ? "No model profiles yet" : "No profiles for this capability"}
          hint="Add a model profile and its API key so agents can use it."
          action={<button onClick={() => { setEditingProfile(null); setIsModalOpen(true); }} className="text-xs text-blue-500 hover:underline">Add model</button>}
        />
      ) : (
      <div className="rounded-xl border border-border bg-card/40 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 border-b border-border text-muted-foreground font-mono text-[11px] uppercase">
              <tr>
                <th className="py-3 px-4">Profile & Model</th>
                <th className="py-3 px-4">Provider</th>
                <th className="py-3 px-4">Capability</th>
                <th className="py-3 px-4">Tags</th>
                <th className="py-3 px-4">Cost Structure</th>
                <th className="py-3 px-4">API Credential</th>
                <th className="py-3 px-4">7d Benchmarks</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {profiles.map((p) => (
                <tr key={p.id} className="hover:bg-secondary/30 transition-colors">
                  <td className="py-3 px-4">
                    <div className="font-semibold text-foreground font-mono">
                      {p.name}
                      {!p.enabled && <span className="ml-2 px-1.5 rounded text-[10px] bg-zinc-500/15 text-zinc-500 font-sans">disabled</span>}
                    </div>
                    <div className="text-[11px] text-muted-foreground font-mono">{p.model}</div>
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    <span className="px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono text-[11px]">
                      {p.provider}
                    </span>
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    {getCapabilityBadge(p.capability)}
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
                    {p.cost.per_video !== undefined && <div>${p.cost.per_video} / video</div>}
                    {p.cost.per_1k_chars !== undefined && (
                      <div>${p.cost.per_1k_chars} / 1k chars</div>
                    )}
                  </td>

                  <td className="py-3 px-4 whitespace-nowrap">
                    {p.key_configured ? (
                      <div className="flex items-center gap-1.5 font-mono text-[11px] text-emerald-500">
                        <span className="inline-flex items-center gap-1 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20 font-medium">
                          <Key className="w-3 h-3" />
                          <span>{p.key_env_var || "KEY_SET"}</span>
                        </span>
                      </div>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-500 bg-rose-500/10 px-2 py-0.5 rounded-full border border-rose-500/20">
                        Missing Key
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
                    <button
                      onClick={() => {
                        setEditingProfile(p);
                        setIsModalOpen(true);
                      }}
                      className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary inline-flex items-center gap-1"
                      title="Edit Profile & Credentials"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                      <span className="text-[11px] font-mono">Edit</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}

      {/* Add / Edit Profile Modal */}
      <AddEditProfileModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveProfile}
        initialProfile={editingProfile}
      />
    </div>
  );
}
