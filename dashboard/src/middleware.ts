import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

// Public: the login page, the login/logout endpoints, and static assets (excluded by the matcher).
const PUBLIC_PATHS = new Set(["/login", "/api/auth/login", "/api/auth/logout"]);

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.has(pathname)) return NextResponse.next();

  if (await verifySessionToken(req.cookies.get(SESSION_COOKIE)?.value)) return NextResponse.next();

  // API callers get a 401 JSON body (a redirect to an HTML page is useless to fetch/EventSource);
  // page navigations are redirected to /login.
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: { code: "unauthorized", message: "login required" } }, { status: 401 });
  }
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|woff2?)$).*)"],
};
