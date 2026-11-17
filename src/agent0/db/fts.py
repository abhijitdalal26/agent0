from __future__ import annotations

import re

_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)


def or_tsquery(text: str, max_terms: int = 24) -> str:
    """OR-joined to_tsquery input built only from alphanumerics, so arbitrary text is safe."""
    seen: list[str] = []
    for word in _WORD.findall(text.lower()):
        if word not in seen:
            seen.append(word)
        if len(seen) >= max_terms:
            break
    return " | ".join(seen)


def vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vec) + "]"
