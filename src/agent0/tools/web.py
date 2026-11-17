from __future__ import annotations

import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 1_000_000
MAX_REDIRECTS = 5
_SKIP = {"script", "style", "noscript", "template", "svg", "head"}
_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "pre"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _Text()
    parser.feed(html)
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def check_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "only http(s) URLs are allowed"
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".internal", ".local")):
        return "local addresses are blocked"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    if not ip.is_global:
        return "private or local addresses are blocked"
    return None


async def fetch_text(
    url: str, transport: httpx.AsyncBaseTransport | None = None, timeout_s: float = 20
) -> str:
    async with httpx.AsyncClient(transport=transport, timeout=timeout_s, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            if (problem := check_url(url)) is not None:
                raise ValueError(problem)
            async with client.stream("GET", url, headers={"User-Agent": "agent0/0.1"}) as resp:
                if resp.is_redirect and (loc := resp.headers.get("location")):
                    url = urljoin(url, loc)
                    continue
                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    size += len(chunk)
                    if size >= MAX_BYTES:
                        break
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                body = b"".join(chunks)[:MAX_BYTES].decode(resp.encoding or "utf-8", errors="replace")
                status = resp.status_code
                break
        else:
            raise ValueError("too many redirects")
    if ctype and not (ctype.startswith("text/") or "json" in ctype or "xml" in ctype):
        return f"HTTP {status}: non-text content ({ctype}), not shown"
    if "html" in ctype or body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        body = html_to_text(body)
    return f"HTTP {status}\n{body}"
