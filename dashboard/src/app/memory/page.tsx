"use client";

import { useCallback, useEffect, useState } from "react";
import { Brain, Search, History, Pencil, Trash2, X } from "lucide-react";
import {
  editFact,
  errMessage,
  factRevisions,
  forgetFact,
  listFacts,
  searchFacts,
  type FactItem,
} from "@/lib/api-settings";
import { formatRelativeTime } from "@/lib/utils";
import { Badge, btn, btnDanger, btnPrimary, Empty, ErrorBox, inputCls, Loading } from "@/components/new/ui";

const SCOPES = ["all", "global", "agent", "project", "task"];

function ScopeTag({ f }: { f: FactItem }) {
  return (
    <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-muted text-foreground">
      {f.scope}
      {f.scope_id ? `/${f.scope_id}` : ""}
    </span>
  );
}

function HistoryDrawer({ fact, onClose }: { fact: FactItem; onClose: () => void }) {
  const [rows, setRows] = useState<FactItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    factRevisions(fact.id)
      .then((r) => live && setRows(r.items))
      .catch((e) => live && setError(errMessage(e)));
    return () => {
      live = false;
    };
  }, [fact.id]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Fact history">
      <button className="absolute inset-0 bg-black/40" onClick={onClose} aria-label="Close history" />
      <aside className="relative w-full max-w-md h-full bg-card border-l border-border overflow-y-auto p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <History className="w-4 h-4" /> History
          </h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-secondary" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>
        {error && <ErrorBox message={error} />}
        {!rows && !error && <Loading />}
        {rows && rows.length === 0 && <Empty>No revisions.</Empty>}
        {rows && (
          <ol className="space-y-3 border-l border-border pl-4">
            {rows.map((r) => (
              <li key={r.id} className="space-y-1">
                <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                  <Badge tone={r.current ? "ok" : "muted"}>{r.current ? "current" : "expired"}</Badge>
                  {r.valid_from && <span>{formatRelativeTime(r.valid_from)}</span>}
                  {r.source_id && <span className="font-mono">by {r.source_id}</span>}
                </div>
                <p className="text-xs text-foreground whitespace-pre-wrap break-words">{r.content}</p>
              </li>
            ))}
          </ol>
        )}
      </aside>
    </div>
  );
}

function FactCard({
  fact,
  onChanged,
  onHistory,
}: {
  fact: FactItem;
  onChanged: () => void;
  onHistory: (f: FactItem) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fact.content);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>, done: () => void) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      done();
      onChanged();
    } catch (e) {
      setErr(errMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className={`rounded-xl border p-3.5 space-y-2 ${fact.current ? "border-border bg-card/60" : "border-border/60 bg-card/30"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={fact.current ? "ok" : "muted"}>{fact.current ? "current" : "expired"}</Badge>
        <ScopeTag f={fact} />
        {fact.valid_from && <span className="text-[11px] text-muted-foreground">since {formatRelativeTime(fact.valid_from)}</span>}
        {fact.valid_to && <span className="text-[11px] text-muted-foreground">ended {formatRelativeTime(fact.valid_to)}</span>}
      </div>

      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={4}
            maxLength={4000}
            className={`${inputCls} font-mono`}
            aria-label="Edit fact"
          />
          <p className="text-[11px] text-muted-foreground">Saving creates a new fact that supersedes this one. The old text stays in history.</p>
          <div className="flex gap-2">
            <button
              className={btnPrimary}
              disabled={busy || !draft.trim() || draft === fact.content}
              onClick={() => run(() => editFact(fact.id, draft.trim()), () => setEditing(false))}
            >
              {busy ? "Saving..." : "Save"}
            </button>
            <button className={btn} onClick={() => { setEditing(false); setDraft(fact.content); }} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className={`text-xs whitespace-pre-wrap break-words ${fact.current ? "text-foreground" : "text-muted-foreground line-through decoration-muted-foreground/40"}`}>
          {fact.content}
        </p>
      )}

      {confirm && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-xs">
          <span className="flex-1">Forget this fact? It is expired, not deleted, and stays in history.</span>
          <div className="flex gap-2">
            <button className={btnDanger} disabled={busy} onClick={() => run(() => forgetFact(fact.id), () => setConfirm(false))}>
              {busy ? "..." : "Forget"}
            </button>
            <button className={btn} disabled={busy} onClick={() => setConfirm(false)}>
              Keep
            </button>
          </div>
        </div>
      )}

      {err && <ErrorBox message={err} />}

      {!editing && !confirm && (
        <div className="flex flex-wrap gap-2 pt-1">
          {fact.current && (
            <button className={btn} onClick={() => { setDraft(fact.content); setEditing(true); }}>
              <Pencil className="w-3 h-3" /> Edit
            </button>
          )}
          <button className={btn} onClick={() => onHistory(fact)}>
            <History className="w-3 h-3" /> History
          </button>
          {fact.current && (
            <button className={`${btn} text-rose-500`} onClick={() => setConfirm(true)}>
              <Trash2 className="w-3 h-3" /> Forget
            </button>
          )}
        </div>
      )}
    </li>
  );
}

export default function MemoryPage() {
  const [facts, setFacts] = useState<FactItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState("all");
  const [showExpired, setShowExpired] = useState(false);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<FactItem | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    setError(null);
    try {
      if (query) {
        // Search only returns current facts; apply the scope filter locally.
        const r = await searchFacts(query);
        setFacts(r.items.filter((f) => scope === "all" || f.scope === scope));
      } else {
        setFacts((await listFacts(scope, showExpired)).items);
      }
    } catch (e) {
      setError(errMessage(e));
      setFacts(null);
    }
  }, [query, scope, showExpired]);

  useEffect(() => {
    setFacts(null);
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Brain className="w-5 h-5 text-blue-500" />
          <span>Memory</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Facts the agents have learned. Editing supersedes a fact and forgetting expires it, so history is always kept.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search current facts"
            aria-label="Search facts"
            className={`${inputCls} pl-9`}
          />
        </div>
        <select value={scope} onChange={(e) => setScope(e.target.value)} aria-label="Scope" className={`${inputCls} sm:w-40`}>
          {SCOPES.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All scopes" : s}
            </option>
          ))}
        </select>
        <label className={`flex items-center gap-2 text-xs ${query ? "opacity-50" : ""}`}>
          <input type="checkbox" checked={showExpired} disabled={!!query} onChange={(e) => setShowExpired(e.target.checked)} />
          Show expired
        </label>
      </div>

      {error && <ErrorBox message={error} onRetry={load} />}
      {!facts && !error && <Loading label="Loading facts" />}
      {facts && facts.length === 0 && (
        <Empty>{query ? `No current facts match "${query}".` : "No facts yet. Agents save facts here as they learn."}</Empty>
      )}
      {facts && facts.length > 0 && (
        <ul className="space-y-3">
          {facts.map((f) => (
            <FactCard key={f.id} fact={f} onChanged={load} onHistory={setHistory} />
          ))}
        </ul>
      )}

      {history && <HistoryDrawer fact={history} onClose={() => setHistory(null)} />}
    </div>
  );
}
