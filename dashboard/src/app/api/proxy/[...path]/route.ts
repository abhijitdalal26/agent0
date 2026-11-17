import { NextRequest, NextResponse } from "next/server";
import { handleMock } from "@/mocks/server";

// Server-side proxy to the agent0 backend. The backend URL and API key exist only in server env
// (AGENT0_API_URL / AGENT0_API_KEY) and are never exposed to the browser.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ path: string[] }> };

const API_URL = (process.env.AGENT0_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const API_KEY = process.env.AGENT0_API_KEY || "";

// Only these request headers go upstream. Browser cookies and Authorization are never forwarded.
const FORWARD_REQUEST_HEADERS = ["content-type", "accept", "last-event-id"];
// Only these response headers come back. No set-cookie, no upstream CSP, etc.
const FORWARD_RESPONSE_HEADERS = ["content-type", "content-disposition", "content-length", "retry-after", "etag"];

function error(status: number, code: string, message: string): NextResponse {
  return NextResponse.json({ error: { code, message } }, { status });
}

function safeSegments(segments: string[] | undefined, rawPathname: string): string[] | null {
  if (!segments || segments.length === 0) return null;
  if (rawPathname.includes("..")) return null;
  for (const s of segments) {
    if (!s || s === "." || s.includes("..") || /[\\/?#\0]/.test(s)) return null;
  }
  return segments;
}

function sameOrigin(req: NextRequest): boolean {
  if (req.method === "GET") return true;
  const origin = req.headers.get("origin");
  if (!origin) return true;
  try {
    return new URL(origin).host === req.headers.get("host");
  } catch {
    return false;
  }
}

async function handle(req: NextRequest, ctx: Ctx): Promise<Response> {
  const segments = safeSegments((await ctx.params).path, req.nextUrl.pathname);
  if (!segments) return error(400, "bad_path", "invalid path");
  if (!sameOrigin(req)) return error(403, "forbidden", "cross-origin request rejected");

  // EventSource cannot set headers on a new connection, so the SSE client passes its resume point
  // as ?last_event_id=; it becomes the Last-Event-ID header and is not forwarded as a query param.
  const params = new URLSearchParams(req.nextUrl.searchParams);
  const resumeId = params.get("last_event_id");
  params.delete("last_event_id");
  const lastEventId = req.headers.get("last-event-id") || resumeId;
  const search = params.size ? `?${params.toString()}` : "";
  const body = req.method === "GET" || req.method === "DELETE" ? undefined : await req.text();

  let res: Response;
  if (process.env.AGENT0_MOCK === "1") {
    res = await handleMock({
      method: req.method,
      segments,
      searchParams: params,
      body,
      lastEventId,
      signal: req.signal,
    });
  } else {
    const headers = new Headers();
    for (const name of FORWARD_REQUEST_HEADERS) {
      const v = req.headers.get(name);
      if (v) headers.set(name, v);
    }
    if (lastEventId) headers.set("last-event-id", lastEventId);
    if (API_KEY) headers.set("authorization", `Bearer ${API_KEY}`);
    const target = `${API_URL}/api/v1/${segments.map(encodeURIComponent).join("/")}${search}`;
    try {
      res = await fetch(target, {
        method: req.method,
        headers,
        body: body || undefined,
        redirect: "manual",
        cache: "no-store",
        signal: req.signal, // client disconnect aborts the upstream (SSE) request
      });
    } catch {
      return error(502, "upstream_unreachable", "could not reach the agent0 backend");
    }
  }

  const out = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const v = res.headers.get(name);
    if (v) out.set(name, v);
  }
  const isSse = (res.headers.get("content-type") || "").includes("text/event-stream");
  out.set("cache-control", isSse ? "no-cache, no-transform" : "no-store");
  if (isSse) out.set("x-accel-buffering", "no");
  // Artifacts are untrusted content served from our origin: forbid sniffing and script execution.
  out.set("x-content-type-options", "nosniff");
  out.set("content-security-policy", "default-src 'none'; img-src 'self' data:; media-src 'self'; sandbox");

  // Status and body (including the JSON error envelope) are passed through; body is streamed.
  return new Response(res.body, { status: res.status, headers: out });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
