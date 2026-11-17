// Browser and server components call the backend only through the Next.js proxy (/api/proxy),
// which attaches the API key server-side. Never call the backend URL directly from the browser.
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function proxyUrl(path: string): string {
  return `/api/proxy/${path.replace(/^\/+/, "")}`;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(proxyUrl(path), {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    cache: "no-store",
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(res.status, err.code ?? "http_error", err.message ?? res.statusText);
  }
  return body as T;
}
