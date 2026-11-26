"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  Bot,
  Brain,
  Calendar,
  Cpu,
  KeyRound,
  Layers,
  LayoutDashboard,
  ListTodo,
  LogOut,
  Menu,
  Receipt,
  Settings,
  ShieldAlert,
  X,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { getOverviewStats } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_GROUPS = [
  {
    label: "Operate",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard },
      { href: "/tasks", label: "Tasks", icon: ListTodo },
      { href: "/approvals", label: "Approvals", icon: ShieldAlert, badgeKey: "approvals" },
      { href: "/activity", label: "Activity", icon: Activity },
    ],
  },
  {
    label: "Fleet",
    items: [
      { href: "/agents", label: "Agents", icon: Bot },
      { href: "/models", label: "Models", icon: Cpu },
      { href: "/extensions", label: "Extensions", icon: Layers },
      { href: "/usage", label: "Usage", icon: Receipt },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/memory", label: "Memory", icon: Brain },
      { href: "/schedules", label: "Schedules", icon: Calendar },
      { href: "/settings", label: "Settings", icon: Settings },
      { href: "/settings/keys", label: "Keys", icon: KeyRound },
    ],
  },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState<number>(0);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    if (pathname === "/login") return;
    getOverviewStats()
      .then((stats) => setPendingApprovals(stats.waiting_approval))
      .catch(() => {});
    fetch("/api/auth/session", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => setIsMock(!!s?.mock))
      .catch(() => {});
  }, [pathname]);

  useEffect(() => setMobileOpen(false), [pathname]);

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.location.assign("/login");
  };

  if (pathname === "/login") {
    return <div className="min-h-screen bg-background text-foreground">{children}</div>;
  }

  const nav = (onNavigate?: () => void) => (
    <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-5">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/70">
            {group.label}
          </div>
          <div className="space-y-0.5">
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  className={cn(
                    "relative flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-[13px] transition-colors",
                    active
                      ? "bg-secondary text-foreground font-medium"
                      : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-full bg-blue-500" />
                  )}
                  <Icon className={cn("w-4 h-4 shrink-0", active ? "text-foreground" : "text-muted-foreground/80")} />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badgeKey === "approvals" && pendingApprovals > 0 && (
                    <span className="px-1.5 py-px rounded-full text-[10px] font-mono font-semibold bg-amber-500/15 text-amber-600 dark:text-amber-400">
                      {pendingApprovals}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );

  const footer = (
    <div className="border-t border-border/60 px-3 py-3 space-y-2">
      {isMock && (
        <div className="flex items-center gap-1.5 px-2 text-[11px] font-mono text-amber-600 dark:text-amber-400">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
          Mock data
        </div>
      )}
      <div className="flex items-center justify-between px-1">
        <span className="text-[11px] font-mono text-muted-foreground/60">v0.1</span>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <button
            onClick={logout}
            className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
            aria-label="Log out"
            title="Log out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 w-56 flex-col border-r border-border/60 bg-card/40">
        <Link href="/" className="flex items-center gap-2.5 px-4 h-14 border-b border-border/60 shrink-0">
          <div className="w-6 h-6 rounded-md bg-foreground text-background flex items-center justify-center text-[11px] font-bold font-mono">
            a0
          </div>
          <span className="text-sm font-semibold tracking-tight">agent0</span>
        </Link>
        {nav()}
        {footer}
      </aside>

      {/* Mobile top bar */}
      <header className="lg:hidden sticky top-0 z-40 flex items-center justify-between h-14 px-4 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-foreground text-background flex items-center justify-center text-[11px] font-bold font-mono">
            a0
          </div>
          <span className="text-sm font-semibold tracking-tight">agent0</span>
          {isMock && (
            <span className="ml-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              MOCK
            </span>
          )}
        </Link>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-2 text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-30 pt-14">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-x-0 top-14 bottom-0 bg-card border-r border-border/60 flex flex-col">
            {nav(() => setMobileOpen(false))}
            {footer}
          </div>
        </div>
      )}

      <main className="lg:pl-56">
        <div className="max-w-[1400px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">{children}</div>
      </main>
    </div>
  );
}
