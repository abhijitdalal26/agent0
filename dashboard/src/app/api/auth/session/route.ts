import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Behind the session middleware. Lets the UI show a "mock mode" badge without any NEXT_PUBLIC_* flag.
export async function GET() {
  return NextResponse.json({ authenticated: true, mock: process.env.AGENT0_MOCK === "1" });
}
