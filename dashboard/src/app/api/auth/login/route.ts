import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE, createSessionToken, sessionCookieOptions } from "@/lib/session";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// In-memory failed-attempt limiter (per server instance). Per-client plus a global bucket,
// because x-forwarded-for is only trustworthy behind a proxy that sets it.
const WINDOW_MS = 15 * 60 * 1000;
const MAX_PER_CLIENT = 5;
const MAX_GLOBAL = 50;
const failures = new Map<string, number[]>();

function recent(key: string, now: number): number[] {
  const hits = (failures.get(key) ?? []).filter((t) => now - t < WINDOW_MS);
  if (hits.length) failures.set(key, hits);
  else failures.delete(key);
  return hits;
}

function retryAfter(key: string, max: number, now: number): number {
  const hits = recent(key, now);
  return hits.length >= max ? Math.ceil((WINDOW_MS - (now - hits[0])) / 1000) : 0;
}

function sha256(s: string): Buffer {
  return createHash("sha256").update(s).digest();
}

function clientKey(req: NextRequest): string {
  return `ip:${req.headers.get("x-forwarded-for")?.split(",")[0].trim() || "unknown"}`;
}

export async function POST(req: NextRequest) {
  const expected = process.env.DASHBOARD_PASSWORD;
  if (!expected) {
    return NextResponse.json(
      { error: { code: "not_configured", message: "DASHBOARD_PASSWORD is not set on the server" } },
      { status: 503 },
    );
  }

  const now = Date.now();
  const key = clientKey(req);
  const wait = Math.max(retryAfter(key, MAX_PER_CLIENT, now), retryAfter("global", MAX_GLOBAL, now));
  if (wait > 0) {
    return NextResponse.json(
      { error: { code: "rate_limited", message: "too many attempts, try again later" } },
      { status: 429, headers: { "Retry-After": String(wait) } },
    );
  }

  let password = "";
  try {
    const body = await req.json();
    if (typeof body?.password === "string") password = body.password;
  } catch {
    /* treated as an empty password */
  }

  // Compare fixed-length digests so neither length nor content leaks through timing.
  const ok = timingSafeEqual(sha256(password), sha256(expected));
  if (!ok) {
    for (const k of [key, "global"]) failures.set(k, [...recent(k, now), now]);
    return NextResponse.json({ error: { code: "invalid_credentials", message: "incorrect password" } }, { status: 401 });
  }

  failures.delete(key);
  const token = await createSessionToken();
  if (!token) {
    return NextResponse.json({ error: { code: "not_configured", message: "session unavailable" } }, { status: 503 });
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
  return res;
}
