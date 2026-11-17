"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Settings, MessageSquare, DollarSign, Bell, KeyRound, ChevronRight } from "lucide-react";
import { errMessage, listSecrets, TELEGRAM_SECRET, type SecretItem } from "@/lib/api-settings";
import { Badge, ErrorBox, Loading } from "@/components/new/ui";

const LEVELS = [
  { id: "final_only", title: "Final only", desc: "Notify when a task reaches succeeded or failed." },
  { id: "milestones", title: "Milestones", desc: "Also notify on approvals, verifier verdicts and failures. This is the default." },
  { id: "everything", title: "Everything", desc: "Notify on every step." },
];

const card = "rounded-xl border border-border bg-card/60 p-4 sm:p-5 space-y-3";
const h2 = "text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2";

export default function SettingsPage() {
  const [telegram, setTelegram] = useState<SecretItem | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await listSecrets();
      setTelegram(s.items.find((i) => i.name === TELEGRAM_SECRET) ?? null);
    } catch (e) {
      setError(errMessage(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Settings className="w-5 h-5 text-blue-500" />
          <span>Settings</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">Channels, notification defaults and credentials.</p>
      </div>

      <Link
        href="/settings/keys"
        className="flex items-center justify-between gap-3 rounded-xl border border-border bg-card/60 p-4 hover:bg-secondary/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <KeyRound className="w-5 h-5 text-blue-500" />
          <div>
            <div className="text-sm font-semibold text-foreground">API keys</div>
            <div className="text-xs text-muted-foreground">Set, test and remove provider and channel credentials.</div>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-muted-foreground" />
      </Link>

      <section className={card}>
        <h2 className={h2}>
          <MessageSquare className="w-4 h-4 text-blue-500" /> Channels
        </h2>
        {error && <ErrorBox message={error} onRetry={load} />}
        {telegram === undefined && !error && <Loading />}
        {telegram !== undefined && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 rounded-lg border border-border bg-card">
            <div>
              <div className="text-xs font-semibold text-foreground">Telegram bot</div>
              <p className="text-[11px] text-muted-foreground">
                {telegram?.configured
                  ? `Token ${telegram.source === "env" ? "comes from the server environment" : "is stored"}. The bot starts when the server runs with Telegram enabled.`
                  : "No bot token. Add one under API keys to enable /task, /status and inline approvals."}
              </p>
            </div>
            {telegram?.configured ? <Badge tone="ok">configured</Badge> : <Badge tone="warn">not configured</Badge>}
          </div>
        )}
        <p className="text-[11px] text-muted-foreground">
          Status reflects whether a token is present. The dashboard cannot see whether the bot process is currently polling.
        </p>
      </section>

      <section className={card}>
        <h2 className={h2}>
          <Bell className="w-4 h-4 text-purple-400" /> Default notify level
        </h2>
        <ul className="space-y-2">
          {LEVELS.map((l) => (
            <li key={l.id} className={`p-3 rounded-lg border text-xs ${l.id === "milestones" ? "border-blue-500/40 bg-blue-500/5" : "border-border"}`}>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-foreground">{l.title}</span>
                <span className="font-mono text-[10px] text-muted-foreground">{l.id}</span>
                {l.id === "milestones" && <Badge tone="info">default</Badge>}
              </div>
              <p className="text-[11px] text-muted-foreground">{l.desc}</p>
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-muted-foreground">
          Read-only. The level is chosen per task when it is created; the server has no endpoint to change a global default.
        </p>
      </section>

      <section className={card}>
        <h2 className={h2}>
          <DollarSign className="w-4 h-4 text-emerald-500" /> Daily budget
        </h2>
        <p className="text-xs text-muted-foreground">
          The daily spend cap is configured on the server, not from the dashboard. Current consumption against the cap is on the{" "}
          <Link href="/usage" className="underline text-foreground">
            Usage
          </Link>{" "}
          page.
        </p>
      </section>
    </div>
  );
}
