from __future__ import annotations

MAX_CHARS = 4000


def truncate(text: str, limit: int = MAX_CHARS, hint: str = "") -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.7)
    tail = limit - head
    omitted = len(text) - limit
    note = f"\n[... {omitted} of {len(text)} chars omitted{'; ' + hint if hint else ''} ...]\n"
    return text[:head] + note + text[-tail:], True
