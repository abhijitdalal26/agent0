from __future__ import annotations

import httpx

from agent0.secrets import TELEGRAM_SECRET

_TIMEOUT = 10.0


async def default_tester(name: str, value: str, provider: str | None) -> tuple[bool, str]:
    if name == TELEGRAM_SECRET:
        url, headers = f"https://api.telegram.org/bot{value}/getMe", {}
    elif provider == "groq":
        url, headers = "https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {value}"}
    elif provider == "google":
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
        headers = {"x-goog-api-key": value}
    else:
        return False, f"no test is available for provider {provider!r}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"request failed: {type(exc).__name__}"
    if resp.is_success:
        return True, "key accepted"
    return False, f"provider rejected the key (HTTP {resp.status_code})"
