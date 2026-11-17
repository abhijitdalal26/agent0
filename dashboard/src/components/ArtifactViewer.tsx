"use client";

import { useEffect, useState } from "react";
import { Code, Download, Eye, FileText, Image as ImageIcon, Music, Video } from "lucide-react";
import type { Artifact } from "@/types";
import { Markdown } from "./Markdown";
import { EmptyState } from "./ui";
import { artifactSrc } from "./data";

const bytes = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`);
const ext = (p: string) => (p.includes(".") ? p.split(".").pop()!.toLowerCase() : "");
const AUDIO_MIME: Record<string, string> = { wav: "audio/wav", mp3: "audio/mpeg", ogg: "audio/ogg", m4a: "audio/mp4" };

function KindIcon({ kind }: { kind: Artifact["kind"] }) {
  const c = "w-4 h-4";
  if (kind === "image") return <ImageIcon className={`${c} text-emerald-500`} />;
  if (kind === "audio") return <Music className={`${c} text-purple-500`} />;
  if (kind === "video") return <Video className={`${c} text-cyan-500`} />;
  if (kind === "json") return <Code className={`${c} text-amber-500`} />;
  return <FileText className={`${c} text-blue-500`} />;
}

function Preview({ art }: { art: Artifact }) {
  const src = artifactSrc(art.url);
  const e = ext(art.path);
  const kind: Artifact["kind"] = art.kind === "other" ? (e === "md" ? "markdown" : e === "json" ? "json" : e === "txt" || e === "log" || e === "csv" ? "text" : art.kind) : art.kind;
  const textual = kind === "markdown" || kind === "text" || kind === "json";
  const [text, setText] = useState<string | null>(art.content_preview ?? null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
    if (art.content_preview != null) return setText(art.content_preview);
    setText(null);
    if (!textual) return;
    let live = true;
    fetch(src)
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      .then((t) => live && setText(t))
      .catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [art.id, art.content_preview, src, textual]);

  if (kind === "image") {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={art.path} className="rounded-lg max-h-80 max-w-full mx-auto object-contain border border-border" />;
  }
  if (kind === "audio") {
    return (
      <audio controls preload="metadata" className="w-full">
        <source src={src} type={AUDIO_MIME[e] ?? "audio/mpeg"} />
      </audio>
    );
  }
  if (kind === "video") return <video controls className="w-full max-h-80 rounded-lg bg-black" src={src} />;
  if (kind === "pdf") return <p className="text-xs text-muted-foreground">PDF preview unavailable inline. Use Download to open it.</p>;
  if (!textual) return <p className="text-xs text-muted-foreground">No inline preview for this file type. Use Download.</p>;
  if (failed) return <p className="text-xs text-rose-500">Could not load file contents.</p>;
  if (text == null) return <div className="h-16 rounded bg-muted/50 animate-pulse" />;
  if (kind === "markdown") return <div className="max-h-80 overflow-auto"><Markdown source={text} /></div>;
  let body = text;
  if (kind === "json") {
    try { body = JSON.stringify(JSON.parse(text), null, 2); } catch {}
  }
  return <pre className="p-2.5 rounded bg-muted/60 font-mono text-[11px] whitespace-pre-wrap break-words max-h-80 overflow-auto border border-border">{body || "Empty file"}</pre>;
}

export function ArtifactViewer({ artifacts }: { artifacts: Artifact[] }) {
  const [selId, setSelId] = useState<string | null>(null);
  const sel = artifacts.find((a) => a.id === selId) ?? artifacts[0];

  return (
    <div className="bg-card/50 rounded-xl border border-border p-3 sm:p-4 space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide flex items-center gap-1.5 pb-3 border-b border-border">
        <Eye className="w-4 h-4 text-blue-500" />Artifacts ({artifacts.length})
      </h3>

      {artifacts.length === 0 ? (
        <EmptyState title="No artifacts yet" hint="Files the agent writes in its sandbox show up here with a preview." />
      ) : (
        <>
          <div className="flex flex-wrap gap-1.5">
            {artifacts.map((a) => (
              <button
                key={a.id}
                onClick={() => setSelId(a.id)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-mono flex items-center gap-2 border transition-colors max-w-full ${
                  sel?.id === a.id ? "bg-secondary text-foreground border-border font-semibold" : "bg-card/60 text-muted-foreground border-border hover:bg-secondary/60"
                }`}
              >
                <KindIcon kind={a.kind} />
                <span className="truncate max-w-[140px]">{a.path.split("/").pop()}</span>
                <span className="text-[10px] opacity-60">{bytes(a.size)}</span>
              </button>
            ))}
          </div>

          {sel && (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="font-mono text-muted-foreground truncate">{sel.path}</span>
                <a href={artifactSrc(sel.url)} download target="_blank" rel="noreferrer" className="text-[11px] font-medium text-blue-500 hover:underline flex items-center gap-1 shrink-0">
                  <Download className="w-3.5 h-3.5" />Download
                </a>
              </div>
              <Preview art={sel} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
