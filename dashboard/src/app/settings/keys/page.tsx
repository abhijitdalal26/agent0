"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { KeyRound, ArrowLeft, ShieldCheck, Server } from "lucide-react";
import {
  deleteSecret,
  errMessage,
  listProfiles,
  listSecrets,
  putSecret,
  secretErrorMessage,
  testSecret,
  type ProfileLite,
  type SecretItem,
} from "@/lib/api-settings";
import { formatRelativeTime } from "@/lib/utils";
import { Badge, btn, btnDanger, btnPrimary, Empty, ErrorBox, inputCls, Loading } from "@/components/new/ui";
import { PageHeader } from "@/components/ui";

type Feedback = { tone: "ok" | "bad"; text: string } | null;

function KeyRow({
  item,
  providers,
  onChanged,
}: {
  item: SecretItem;
  providers: string[];
  onChanged: (next: SecretItem) => void;
}) {
  // The secret value lives only in this uncontrolled input's DOM node. It is read once on submit
  // and the field is cleared immediately. It is never put in React state, storage, logs or a URL.
  const inputRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);
  const [fb, setFb] = useState<Feedback>(null);

  const fromEnv = item.source === "env";
  const stored = item.source === "store";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const el = inputRef.current;
    if (!el) return;
    const value = el.value;
    el.value = "";
    if (!value.trim()) {
      setFb({ tone: "bad", text: "Enter a key value." });
      return;
    }
    setBusy("save");
    setFb(null);
    try {
      const next = await putSecret(item.name, value);
      onChanged(next);
      setEditing(false);
      setFb({ tone: "ok", text: "Saved." });
    } catch (err) {
      setFb({ tone: "bad", text: secretErrorMessage(err, item.name) });
    } finally {
      setBusy(null);
    }
  }

  async function test() {
    setBusy("test");
    setFb(null);
    try {
      const r = await testSecret(item.name);
      setFb({ tone: r.ok ? "ok" : "bad", text: r.message || (r.ok ? "Key works." : "Test failed.") });
    } catch (err) {
      setFb({ tone: "bad", text: secretErrorMessage(err, item.name) });
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("remove");
    setFb(null);
    try {
      onChanged(await deleteSecret(item.name));
      setConfirmRemove(false);
    } catch (err) {
      setFb({ tone: "bad", text: secretErrorMessage(err, item.name) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <li className="rounded-xl border border-border bg-card/60 p-4 space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="font-mono text-xs font-semibold text-foreground break-all">{item.name}</div>
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
            <span>Used by</span>
            {providers.length === 0 ? (
              <span className="italic">no model profile</span>
            ) : (
              providers.map((p) => (
                <span key={p} className="font-mono px-1.5 py-0.5 rounded bg-muted text-foreground">
                  {p}
                </span>
              ))
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            {fromEnv && (
              <>
                <Badge tone="info">from environment</Badge>
                <span className="text-muted-foreground">read-only, managed on the server</span>
              </>
            )}
            {stored && (
              <>
                <Badge tone="ok">configured</Badge>
                <span className="font-mono text-foreground">{item.last4 ? `••••${item.last4}` : "••••••••"}</span>
                {item.updated_at && <span className="text-muted-foreground">updated {formatRelativeTime(item.updated_at)}</span>}
              </>
            )}
            {!item.configured && <Badge tone="warn">missing</Badge>}
          </div>
        </div>

        {!fromEnv && !editing && !confirmRemove && (
          <div className="flex flex-wrap gap-2 shrink-0">
            <button className={btn} onClick={() => { setEditing(true); setFb(null); }}>
              {stored ? "Replace" : "Set"}
            </button>
            {stored && (
              <button className={btn} onClick={test} disabled={busy !== null}>
                {busy === "test" ? "Testing..." : "Test"}
              </button>
            )}
            {stored && (
              <button className={`${btn} text-rose-500`} onClick={() => { setConfirmRemove(true); setFb(null); }}>
                Remove
              </button>
            )}
          </div>
        )}
        {fromEnv && (
          <div className="shrink-0">
            <button className={btn} onClick={test} disabled={busy !== null}>
              {busy === "test" ? "Testing..." : "Test"}
            </button>
          </div>
        )}
      </div>

      {editing && (
        <form onSubmit={submit} className="flex flex-col sm:flex-row gap-2" autoComplete="off">
          <input
            ref={inputRef}
            type="password"
            name={`secret-${item.name}`}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            autoFocus
            placeholder="Paste key value"
            aria-label={`Value for ${item.name}`}
            className={`${inputCls} font-mono flex-1`}
          />
          <div className="flex gap-2">
            <button type="submit" className={btnPrimary} disabled={busy !== null}>
              {busy === "save" ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              className={btn}
              onClick={() => {
                if (inputRef.current) inputRef.current.value = "";
                setEditing(false);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {confirmRemove && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-xs">
          <span className="flex-1 text-foreground">
            Remove the stored value for <span className="font-mono">{item.name}</span>? Agents using it will stop working until you set it again.
          </span>
          <div className="flex gap-2">
            <button className={btnDanger} onClick={remove} disabled={busy !== null}>
              {busy === "remove" ? "Removing..." : "Yes, remove"}
            </button>
            <button className={btn} onClick={() => setConfirmRemove(false)} disabled={busy !== null}>
              Keep
            </button>
          </div>
        </div>
      )}

      {fb && (
        <div
          role={fb.tone === "bad" ? "alert" : "status"}
          className={`text-xs rounded-lg px-3 py-2 border break-words ${
            fb.tone === "ok"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
              : "border-rose-500/30 bg-rose-500/10 text-rose-500"
          }`}
        >
          {fb.text}
        </div>
      )}
    </li>
  );
}

export default function KeysPage() {
  const [items, setItems] = useState<SecretItem[] | null>(null);
  const [profiles, setProfiles] = useState<ProfileLite[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, p] = await Promise.all([listSecrets(), listProfiles().catch(() => ({ items: [] as ProfileLite[] }))]);
      setItems(s.items);
      setProfiles(p.items);
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const providersFor = (name: string) => {
    const set = new Set<string>();
    for (const p of profiles) if (p.key_env === name) set.add(p.provider);
    if (name === "AGENT0_TELEGRAM_BOT_TOKEN") set.add("telegram");
    return [...set].sort();
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="space-y-3">
        <Link href="/settings" className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-3 h-3" /> Settings
        </Link>
        <PageHeader title="API keys" description="Provider and channel credentials. Values are write-only: once saved they are encrypted on the server and only the last four characters are ever shown." />
      </div>

      <div className="grid sm:grid-cols-2 gap-3 text-[11px] text-muted-foreground">
        <div className="flex gap-2 p-3 rounded-lg border border-border bg-card/40">
          <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-500" />
          <span>Keys are sent to the server over the dashboard proxy and are never stored in this browser.</span>
        </div>
        <div className="flex gap-2 p-3 rounded-lg border border-border bg-card/40">
          <Server className="w-4 h-4 shrink-0 text-blue-400" />
          <span>
            Storage needs <span className="font-mono">AGENT0_SECRET_KEY</span> on the server. Generate one with{" "}
            <span className="font-mono">agent0 secrets-keygen</span>.
          </span>
        </div>
      </div>

      {error && <ErrorBox message={error} onRetry={load} />}
      {!items && !error && <Loading label="Loading keys" />}
      {items && items.length === 0 && <Empty>The server reports no configurable keys.</Empty>}
      {items && items.length > 0 && (
        <ul className="space-y-3">
          {items.map((it) => (
            <KeyRow
              key={it.name}
              item={it}
              providers={providersFor(it.name)}
              onChanged={(next) => setItems((prev) => (prev ? prev.map((x) => (x.name === next.name ? next : x)) : prev))}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
