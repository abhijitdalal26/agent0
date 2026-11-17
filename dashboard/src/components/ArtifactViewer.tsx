"use client";

import { useState } from "react";
import { Download, FileText, Image as ImageIcon, Music, Code, Eye, ExternalLink } from "lucide-react";
import type { Artifact } from "@/types";

interface ArtifactViewerProps {
  artifacts: Artifact[];
}

export function ArtifactViewer({ artifacts }: ArtifactViewerProps) {
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(
    artifacts.length > 0 ? artifacts[0] : null
  );

  if (artifacts.length === 0) {
    return (
      <div className="bg-card/50 rounded-xl border border-border p-4 text-center text-muted-foreground text-xs">
        No artifacts generated yet.
      </div>
    );
  }

  const formatBytes = (bytes: number) => {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${bytes} B`;
  };

  const getKindIcon = (kind: Artifact["kind"]) => {
    switch (kind) {
      case "image":
        return <ImageIcon className="w-4 h-4 text-emerald-400" />;
      case "audio":
        return <Music className="w-4 h-4 text-purple-400" />;
      case "markdown":
      case "text":
        return <FileText className="w-4 h-4 text-blue-400" />;
      case "json":
        return <Code className="w-4 h-4 text-amber-400" />;
      default:
        return <FileText className="w-4 h-4 text-zinc-400" />;
    }
  };

  return (
    <div className="bg-card/50 rounded-xl border border-border p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border">
        <div>
          <h3 className="text-xs font-semibold text-foreground tracking-wide uppercase flex items-center gap-1.5">
            <Eye className="w-4 h-4 text-blue-500" />
            <span>Produced Artifacts ({artifacts.length})</span>
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Sandboxed outputs, graphics, models, and synthesized media.
          </p>
        </div>
      </div>

      {/* Artifact Pills / Selector */}
      <div className="flex flex-wrap gap-1.5">
        {artifacts.map((art) => {
          const isSelected = selectedArtifact?.id === art.id;
          return (
            <button
              key={art.id}
              onClick={() => setSelectedArtifact(art)}
              className={`px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center gap-2 border transition-all ${
                isSelected
                  ? "bg-secondary text-foreground border-border font-semibold shadow-sm"
                  : "bg-card/60 text-muted-foreground border-border hover:bg-secondary/60 hover:text-foreground"
              }`}
            >
              {getKindIcon(art.kind)}
              <span className="truncate max-w-[140px]">{art.path.split("/").pop()}</span>
              <span className="text-[10px] text-muted-foreground opacity-60">
                {formatBytes(art.size)}
              </span>
            </button>
          );
        })}
      </div>

      {/* Preview Box */}
      {selectedArtifact && (
        <div className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 text-zinc-200 space-y-3">
          <div className="flex items-center justify-between text-xs pb-2 border-b border-zinc-800">
            <div className="flex items-center gap-2 font-mono">
              <span className="text-zinc-400">{selectedArtifact.path}</span>
              <span className="text-[10px] uppercase px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300 font-bold">
                {selectedArtifact.kind}
              </span>
            </div>

            <a
              href={selectedArtifact.url}
              download
              target="_blank"
              rel="noreferrer"
              className="text-[11px] font-medium text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download</span>
            </a>
          </div>

          {/* Inline Media Rendering */}
          <div className="overflow-hidden">
            {selectedArtifact.kind === "image" && (
              <div className="flex flex-col items-center">
                <img
                  src={selectedArtifact.url}
                  alt={selectedArtifact.path}
                  className="rounded-lg max-h-72 object-cover border border-zinc-800 shadow-md"
                />
                <span className="text-[11px] text-zinc-500 font-mono mt-2">
                  1080x1080 PNG Asset (Inline Inspection)
                </span>
              </div>
            )}

            {selectedArtifact.kind === "audio" && (
              <div className="py-4 px-2 flex flex-col items-center gap-2">
                <audio controls className="w-full max-w-md">
                  <source src={selectedArtifact.url} type="audio/mpeg" />
                  Your browser does not support audio playback.
                </audio>
                <span className="text-[11px] text-zinc-400 font-mono">
                  Synthesized Speech / Audio Preview
                </span>
              </div>
            )}

            {(selectedArtifact.kind === "markdown" ||
              selectedArtifact.kind === "text" ||
              selectedArtifact.kind === "json") && (
              <pre className="p-3 rounded bg-zinc-900/80 font-mono text-[11px] whitespace-pre-wrap max-h-64 overflow-y-auto text-zinc-300 border border-zinc-800">
                {selectedArtifact.content_preview || "Empty document"}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
