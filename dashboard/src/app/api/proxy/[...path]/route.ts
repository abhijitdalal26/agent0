import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.HARNESS_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const API_KEY = process.env.HARNESS_API_KEY || "";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, await params);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, await params);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, await params);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(req, await params);
}

async function handleProxy(req: NextRequest, params: { path: string[] }) {
  const path = params.path.join("/");
  const searchParams = req.nextUrl.searchParams.toString();
  const targetUrl = `${API_BASE}/${path}${searchParams ? `?${searchParams}` : ""}`;

  const headers: Record<string, string> = {
    "Content-Type": req.headers.get("Content-Type") || "application/json",
  };

  // Securely attach bearer auth token server-side (never exposed to client browser bundle)
  if (API_KEY) {
    headers["Authorization"] = `Bearer ${API_KEY}`;
  }

  const options: RequestInit = {
    method: req.method,
    headers,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    const bodyText = await req.text();
    if (bodyText) {
      options.body = bodyText;
    }
  }

  try {
    const res = await fetch(targetUrl, options);
    const contentType = res.headers.get("content-type") || "";

    if (contentType.includes("text/event-stream")) {
      return new Response(res.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    const data = await res.text();
    return new NextResponse(data, {
      status: res.status,
      headers: {
        "Content-Type": contentType || "application/json",
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: { code: "PROXY_ERROR", message: err.message || "Failed to reach backend API" } },
      { status: 502 }
    );
  }
}
