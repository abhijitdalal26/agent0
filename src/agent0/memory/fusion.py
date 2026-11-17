from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Hashable, Iterable, Sequence

_TOKEN = re.compile(r"[^\W_]{3,}", re.UNICODE)


def rrf[T: Hashable](rankings: Iterable[Sequence[T]], k: int = 60) -> list[tuple[T, float]]:
    """Reciprocal-rank fusion: score(d) = sum over rankings of 1 / (k + rank). Ties keep first-seen order."""
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def keyword_score(query: str, text: str) -> float:
    q = set(tokens(query))
    if not q:
        return 0.0
    counts = Counter(tokens(text))
    hits = sum(1 for t in q if t in counts)
    return hits / len(q) + 0.01 * sum(min(counts[t], 3) for t in q)


def rank_by_keywords[T](query: str, items: Iterable[T], text_of: Callable[[T], str]) -> list[T]:
    scored = [(keyword_score(query, text_of(i)), n, i) for n, i in enumerate(items)]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [i for _, _, i in scored]


def take_within_budget[T](items: Iterable[T], text_of: Callable[[T], str], budget: int) -> list[T]:
    out: list[T] = []
    used = 0
    for item in items:
        cost = len(text_of(item)) + 3
        if used + cost > budget and out:
            break
        if used + cost > budget:
            continue
        out.append(item)
        used += cost
    return out
