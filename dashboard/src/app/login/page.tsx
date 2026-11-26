"use client";

import { useState, type FormEvent } from "react";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (res.ok) {
        window.location.assign("/");
        return;
      }
      const body = await res.json().catch(() => null);
      setError(body?.error?.message ?? "login failed");
    } catch {
      setError("could not reach the server");
    } finally {
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-xl border border-border bg-card p-6 shadow-sm">
        <div className="space-y-1.5">
          <div className="w-8 h-8 rounded-lg bg-foreground text-background flex items-center justify-center text-xs font-bold font-mono">
            a0
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-foreground">Sign in to agent0</h1>
        </div>
        <label className="block space-y-1.5">
          <span className="text-xs text-muted-foreground">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            autoFocus
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
        {error && (
          <p role="alert" className="text-xs text-red-500">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy || !password}
          className="w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          {busy ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
