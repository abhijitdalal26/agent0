"use client";

import { useState } from "react";
import { Settings, MessageSquare, Shield, DollarSign, Bell, Check, Save } from "lucide-react";

export default function SettingsPage() {
  const [dailyCap, setDailyCap] = useState("25.00");
  const [notifyLevel, setNotifyLevel] = useState("milestones");
  const [saved, setSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Settings className="w-5 h-5 text-blue-500" />
          <span>Platform Settings & Channel Gateway</span>
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground">
          Configure notification dispatch channels, operator allowlists, and global budget caps.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Connected Channels */}
        <div className="rounded-xl border border-border bg-card/60 p-5 space-y-4">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-blue-500" />
            <span>Connected Communication Channels</span>
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Telegram */}
            <div className="p-4 rounded-lg border border-border bg-card space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-foreground">Telegram Bot</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/15 text-emerald-500 border border-emerald-500/30">
                  Online & Polling
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Listening for /task, /status, and routing inline Approve/Reject action buttons.
              </p>
              <div className="text-[11px] font-mono text-muted-foreground">
                Bot Username: <strong className="text-foreground">@Agent0HarnessBot</strong>
              </div>
            </div>

            {/* Slack */}
            <div className="p-4 rounded-lg border border-border bg-card space-y-2 opacity-60">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-xs text-foreground">Slack App</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-muted text-muted-foreground">
                  Planned (Phase 4)
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                Slack-bolt integration for channel task creation and ephemeral approval prompts.
              </p>
              <div className="text-[11px] font-mono text-muted-foreground">
                Status: Not configured
              </div>
            </div>
          </div>
        </div>

        {/* Global Budgets */}
        <div className="rounded-xl border border-border bg-card/60 p-5 space-y-4">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-emerald-500" />
            <span>Global Spend Caps & Guardrails</span>
          </h2>

          <div className="max-w-md space-y-2">
            <label className="text-xs font-medium text-foreground block">
              Daily Hard Spend Cap (USD)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground text-xs font-mono">
                $
              </span>
              <input
                type="number"
                step="5.00"
                value={dailyCap}
                onChange={(e) => setDailyCap(e.target.value)}
                className="w-full text-xs font-mono pl-7 pr-3 py-2 rounded-lg border border-input bg-background text-foreground"
              />
            </div>
            <p className="text-[11px] text-muted-foreground">
              Runs will automatically pause and emit a <code>budget.exceeded</code> alert when daily consumption reaches this threshold.
            </p>
          </div>
        </div>

        {/* Notification Defaults */}
        <div className="rounded-xl border border-border bg-card/60 p-5 space-y-4">
          <h2 className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-2">
            <Bell className="w-4 h-4 text-purple-400" />
            <span>Default Notification Level</span>
          </h2>

          <div className="space-y-2">
            {[
              { id: "milestones", title: "Milestones Only", desc: "Notify on start, human approvals, verifier verdicts, and failures." },
              { id: "everything", title: "Everything", desc: "Notify on every tool call and model completion." },
              { id: "final_only", title: "Final Result Only", desc: "Only notify when the entire task reaches Succeeded or Failed." },
            ].map((opt) => (
              <label
                key={opt.id}
                className="flex items-start gap-3 p-3 rounded-lg border border-border hover:bg-secondary/40 cursor-pointer text-xs"
              >
                <input
                  type="radio"
                  name="notifyLevel"
                  checked={notifyLevel === opt.id}
                  onChange={() => setNotifyLevel(opt.id)}
                  className="mt-0.5 text-blue-600"
                />
                <div>
                  <span className="font-semibold text-foreground">{opt.title}</span>
                  <p className="text-muted-foreground text-[11px]">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end">
          <button
            type="submit"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-lg shadow-sm shadow-blue-500/30 transition-all"
          >
            {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            <span>{saved ? "Settings Saved" : "Save Changes"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
