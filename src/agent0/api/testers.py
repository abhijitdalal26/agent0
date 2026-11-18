from __future__ import annotations

import httpx

from agent0.models.base import ModelProfile
from agent0.secrets import TELEGRAM_SECRET

_TIMEOUT = 10.0


async def default_tester(name: str, value: str, profile: ModelProfile | None) -> tuple[bool, str]:
    provider = profile.provider if profile else None
    if name == TELEGRAM_SECRET:
        url, headers = f"https://api.telegram.org/bot{value}/getMe", {}
    elif provider == "groq":
        url, headers = "https://api.groq.com/openai/v1/models", {"Authorization": f"Bearer {value}"}
    elif provider == "google":
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"
        headers = {"x-goog-api-key": value}
    elif provider == "openai_compat" and profile and profile.settings.get("base_url"):
        url = f"{profile.settings['base_url'].rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {value}"}
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
