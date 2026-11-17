"use client";

import { useEffect, useState } from "react";
import { Brain, Search, FileText, Globe, Bot, FolderGit2, Save, Trash2, History, Check } from "lucide-react";
import { getMemoryDocs } from "@/lib/api";
import type { MemoryDoc } from "@/types";
import { formatRelativeTime } from "@/lib/utils";

export default function MemoryPage() {
  const [docs, setDocs] = useState<MemoryDoc[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<MemoryDoc | null>(null);
  const [search, setSearch] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all");
  const [editorContent, setEditorContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    getMemoryDocs(scopeFilter, search).then((data) => {
      setDocs(data);
      if (data.length > 0 && (!selectedDoc || !data.some((d) => d.id === selectedDoc.id))) {
        setSelectedDoc(data[0]);
        setEditorContent(data[0].content);
      }
    });
  }, [scopeFilter, search]);

  const handleSelectDoc = (doc: MemoryDoc) => {
    setSelectedDoc(doc);
    setEditorContent(doc.content);
    setSavedSuccess(false);
  };

  const handleSave = () => {
    if (!selectedDoc) return;
    setSaving(true);
    setTimeout(() => {
      selectedDoc.content = editorContent;
      selectedDoc.revision += 1;
      selectedDoc.updated_at = new Date().toISOString();
      setSaving(false);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 2500);
    }, 400);
  };

  const handleDelete = () => {
    if (!selectedDoc) return;
    if (confirm(`Delete memory doc '${selectedDoc.path}'?`)) {
      const remaining = docs.filter((d) => d.id !== selectedDoc.id);
      setDocs(remaining);
      if (remaining.length > 0) handleSelectDoc(remaining[0]);
      else setSelectedDoc(null);
    }
  };

  const getScopeIcon = (scope: MemoryDoc["scope"]) => {
    switch (scope) {
      case "global":
        return <Globe className="w-3.5 h-3.5 text-blue-400" />;
      case "agent":
        return <Bot className="w-3.5 h-3.5 text-purple-400" />;
      case "project":
        return <FolderGit2 className="w-3.5 h-3.5 text-emerald-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Brain className="w-5 h-5 text-blue-500" />
          <span>Long-Term Memory & Context Documents</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Scoped instruction docs, regulatory rules, learned facts, and project guidelines injected at plan time.
        </p>
      </div>

      {/* Filter and Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents by path or content..."
            className="w-full text-xs pl-9 pr-3 py-2 rounded-lg border border-input bg-card/60 text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
        </div>

        <select
          value={scopeFilter}
          onChange={(e) => setScopeFilter(e.target.value)}
          className="text-xs px-2.5 py-2 rounded-lg border border-input bg-card/60 text-foreground focus:outline-none"
        >
          <option value="all">All Scopes</option>
          <option value="global">Global Scope</option>
          <option value="agent">Agent Scope</option>
          <option value="project">Project Scope</option>
        </select>
      </div>

      {/* Main Layout: Docs Tree / List + Editor */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Left Doc Selector */}
        <div className="md:col-span-4 space-y-2">
          {docs.map((doc) => {
            const isSelected = selectedDoc?.id === doc.id;
            return (
              <div
                key={doc.id}
                onClick={() => handleSelectDoc(doc)}
                className={`p-3.5 rounded-xl border text-xs cursor-pointer transition-all space-y-1.5 ${
                  isSelected
                    ? "bg-card border-blue-500/50 shadow-sm"
                    : "bg-card/40 border-border hover:bg-card/70"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 font-mono text-[11px] text-foreground font-semibold">
                    {getScopeIcon(doc.scope)}
                    <span>{doc.scope}</span>
                    {doc.scope_id && <span className="text-muted-foreground">({doc.scope_id})</span>}
                  </div>
                  <span className="text-[10px] font-mono text-muted-foreground">
                    rev {doc.revision}
                  </span>
                </div>

                <div className="font-mono text-xs text-foreground truncate">{doc.path}</div>

                <div className="text-[10px] text-muted-foreground font-mono">
                  Updated {formatRelativeTime(doc.updated_at)}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Editor */}
        <div className="md:col-span-8">
          {selectedDoc ? (
            <div className="rounded-xl border border-border bg-card/60 p-4 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-foreground text-sm">
                      {selectedDoc.path}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-muted text-muted-foreground uppercase">
                      rev {selectedDoc.revision}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Scope: {selectedDoc.scope}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleDelete}
                    className="p-2 text-rose-500 hover:text-rose-400 rounded-lg border border-border hover:bg-secondary transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>

                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-sm shadow-blue-500/30 transition-all disabled:opacity-50"
                  >
                    {savedSuccess ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                    <span>{savedSuccess ? "Saved (rev+1)" : saving ? "Saving..." : "Save Changes"}</span>
                  </button>
                </div>
              </div>

              <textarea
                rows={18}
                value={editorContent}
                onChange={(e) => setEditorContent(e.target.value)}
                className="w-full text-xs font-mono p-3 rounded-lg border border-input bg-zinc-950 text-zinc-200 focus:outline-none focus:ring-1 focus:ring-ring resize-y leading-relaxed"
              />
            </div>
          ) : (
            <div className="p-16 text-center text-muted-foreground text-xs border border-dashed rounded-xl">
              Select a memory document from the list.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
