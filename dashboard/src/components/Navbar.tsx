"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  Bot,
  Brain,
  Calendar,
  CheckCircle2,
  Cpu,
  Layers,
  LayoutDashboard,
  ListTodo,
  Menu,
  Receipt,
  Settings,
  ShieldAlert,
  X,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { getOverviewStats } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/tasks", label: "Tasks", icon: ListTodo },
  { href: "/approvals", label: "Approvals", icon: ShieldAlert, badgeKey: "approvals" },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/models", label: "Models", icon: Cpu },
  { href: "/usage", label: "Usage", icon: Receipt },
  { href: "/extensions", label: "Extensions", icon: Layers },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/schedules", label: "Schedules", icon: Calendar },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState<number>(1);
  const isMock = process.env.NEXT_PUBLIC_MOCK === "1";

  useEffect(() => {
    getOverviewStats().then((stats) => {
      setPendingApprovals(stats.waiting_approval);
    });
  }, [pathname]);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-card/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        {/* Brand / Logo */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-sm shadow-blue-500/30 group-hover:scale-105 transition-transform">
              0
            </div>
            <span className="font-semibold text-sm tracking-tight text-foreground flex items-center gap-1.5">
              agent0
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground uppercase">
                harness
              </span>
            </span>
          </Link>

          {isMock && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              MOCK MODE
            </span>
          )}
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
                  isActive
                    ? "bg-secondary text-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                }`}
              >
                <Icon className="w-3.5 h-3.5 opacity-80" />
                <span>{item.label}</span>
                {item.badgeKey === "approvals" && pendingApprovals > 0 && (
                  <span className="ml-0.5 px-1.5 py-0.2 rounded-full text-[10px] font-mono font-bold bg-amber-500 text-zinc-950">
                    {pendingApprovals}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Actions right */}
        <div className="flex items-center gap-2">
          <ThemeToggle />

          {/* Mobile hamburger button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-secondary"
            aria-label="Toggle Navigation Menu"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="lg:hidden border-b border-border bg-card px-4 pt-2 pb-4 space-y-1 animate-in slide-in-from-top-2 duration-150">
          {isMock && (
            <div className="mb-2 px-2 py-1 text-[11px] font-mono text-amber-500 bg-amber-500/10 rounded border border-amber-500/20 inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              Running in Mock Mode (fixtures active)
            </div>
          )}
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-secondary text-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                {item.badgeKey === "approvals" && pendingApprovals > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500 text-zinc-950">
                    {pendingApprovals} pending
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </header>
  );
}
