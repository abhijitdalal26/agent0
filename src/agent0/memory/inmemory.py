from __future__ import annotations

from agent0.core.types import utcnow
from agent0.memory.base import Fact, FactVerdict, Recall, RunSummary
from agent0.memory.fusion import rank_by_keywords, take_within_budget


def _in_scope(fact: Fact, scope: str, scope_id: str | None) -> bool:
    if fact.scope == "global":
        return True
    return fact.scope == scope and fact.scope_id == scope_id


class InMemoryMemoryStore:
    def __init__(self, max_chars: int = 2000, max_facts: int = 8, max_runs: int = 3) -> None:
        self.facts: dict[str, Fact] = {}
        self.runs: dict[str, RunSummary] = {}
        self.max_chars = max_chars
        self.max_facts = max_facts
        self.max_runs = max_runs

    def current_facts(self) -> list[Fact]:
        return [f for f in self.facts.values() if f.valid_to is None]

    async def recall(self, query: str, scope: str = "global", scope_id: str | None = None) -> Recall:
        candidates = [f for f in self.current_facts() if _in_scope(f, scope, scope_id)]
        facts = rank_by_keywords(query, candidates, lambda f: f.content)[: self.max_facts]
        runs = rank_by_keywords(query, self.runs.values(), lambda r: r.summary)[: self.max_runs]
        facts = take_within_budget(facts, lambda f: f.content, self.max_chars)
        used = sum(len(f.content) + 3 for f in facts)
        runs = take_within_budget(runs, lambda r: r.summary, max(self.max_chars - used, 0))
        return Recall(facts=facts, past_runs=runs)

    async def save_run(self, summary: RunSummary) -> None:
        self.runs[summary.run_id] = summary

    async def apply(self, fact: Fact, verdict: FactVerdict, target_id: str | None = None) -> None:
        if verdict == "repeats":
            return
        if verdict == "new":
            self.facts.setdefault(fact.id, fact)
            return
        if target_id is None:
            raise ValueError(f"verdict {verdict!r} needs a target_id")
        target = self.facts.get(target_id)
        if target is not None and target.valid_to is None:
            target.valid_to = utcnow()
            if verdict == "changes":
                target.superseded_by = fact.id
        if verdict == "changes":
            self.facts.setdefault(fact.id, fact)

    async def similar_facts(self, content: str, limit: int = 5) -> list[Fact]:
        return rank_by_keywords(content, self.current_facts(), lambda f: f.content)[:limit]
