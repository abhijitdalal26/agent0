// Session cookie helpers. Web Crypto only, so this runs in Edge middleware and Node route handlers.
// Cookie value: "<expiry-epoch-seconds>.<hex HMAC-SHA256 of the expiry>". Server-only: never import from client code.

export const SESSION_COOKIE = "agent0_session";
export const SESSION_TTL_SECONDS = 12 * 60 * 60;

const enc = new TextEncoder();

function secretMaterial(): string | null {
  const secret = process.env.DASHBOARD_SESSION_SECRET || process.env.DASHBOARD_PASSWORD;
  return secret ? `agent0-dashboard-session:${secret}` : null;
}

async function hmacKey(usage: KeyUsage): Promise<CryptoKey | null> {
  const material = secretMaterial();
  if (!material) return null;
  return crypto.subtle.importKey("raw", enc.encode(material), { name: "HMAC", hash: "SHA-256" }, false, [usage]);
}

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

function fromHex(hex: string): Uint8Array | null {
  if (!/^[0-9a-f]+$/i.test(hex) || hex.length % 2 !== 0) return null;
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export async function createSessionToken(now = Date.now()): Promise<string | null> {
  const key = await hmacKey("sign");
  if (!key) return null;
  const exp = String(Math.floor(now / 1000) + SESSION_TTL_SECONDS);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(exp));
  return `${exp}.${toHex(sig)}`;
}

export async function verifySessionToken(token: string | undefined | null, now = Date.now()): Promise<boolean> {
  if (!token) return false;
  const dot = token.indexOf(".");
  if (dot < 1) return false;
  const exp = token.slice(0, dot);
  const sig = fromHex(token.slice(dot + 1));
  if (!/^\d{1,12}$/.test(exp) || !sig) return false;
  const key = await hmacKey("verify");
  if (!key) return false; // no DASHBOARD_PASSWORD configured: fail closed
  // subtle.verify compares in constant time.
  const ok = await crypto.subtle.verify("HMAC", key, sig as BufferSource, enc.encode(exp));
  return ok && Number(exp) * 1000 > now;
}

export function sessionCookieOptions(maxAge: number = SESSION_TTL_SECONDS) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
