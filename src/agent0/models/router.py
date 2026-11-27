from __future__ import annotations

from dataclasses import dataclass

from agent0.core.types import Capability
from agent0.models.base import ModelProfile, NoProfileAvailable, Preference
from agent0.models.cooldown import CooldownTracker, default_tracker
from agent0.models.registry import ModelRegistry

# (tag, cost, context) weights per preference
_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "cheap": (3.0, 2.0, 0.25),
    "fast": (3.0, 0.5, 0.0),
    "smart": (3.0, 0.0, 1.0),
}


def unit_cost(p: ModelProfile) -> float:
    c = p.cost
    return c.input_per_mtok + c.output_per_mtok + c.per_image + c.per_1k_chars + c.per_minute


def _norm(values: list[float], v: float, higher_is_better: bool) -> float:
    lo, hi = min(values), max(values)
    if hi == lo:
        return 1.0
    x = (v - lo) / (hi - lo)
    return x if higher_is_better else 1.0 - x


@dataclass(frozen=True)
class Ranked:
    profile: ModelProfile
    score: float
    tag_match: bool
    cost_score: float
    context_score: float


class Router:
    def __init__(self, registry: ModelRegistry, cooldowns: CooldownTracker | None = None) -> None:
        self.registry = registry
        self.cooldowns = cooldowns if cooldowns is not None else default_tracker()

    def rank(
        self,
        capability: Capability | str,
        prefer: Preference = "cheap",
        exclude_provider: str | None = None,
        needs_context: int | None = None,
    ) -> list[Ranked]:
        cap = Capability(capability)
        if prefer not in _WEIGHTS:
            raise ValueError(f"unknown preference {prefer!r}; use one of: {', '.join(_WEIGHTS)}")
        cands = [
            p
            for p in self.registry.available(cap)
            if p.provider != exclude_provider
            and (needs_context is None or (p.context_window or 0) >= needs_context)
        ]
        if not cands:
            raise NoProfileAvailable(
                f"no available profile for capability={cap.value} "
                f"exclude_provider={exclude_provider} needs_context={needs_context}"
            )
        w_tag, w_cost, w_ctx = _WEIGHTS[prefer]
        costs = [unit_cost(p) for p in cands]
        ctxs = [float(p.context_window or 0) for p in cands]
        out: list[Ranked] = []
        for p in cands:
            tag = prefer in p.tags
            cs = _norm(costs, unit_cost(p), higher_is_better=False)
            xs = _norm(ctxs, float(p.context_window or 0), higher_is_better=True)
            out.append(Ranked(p, w_tag * tag + w_cost * cs + w_ctx * xs, tag, cs, xs))
        out.sort(key=lambda r: (-r.score, r.profile.name))
        # Rate-limited profiles sink to the bottom but stay eligible: when every
        # candidate is cooling, the least-bad one still gets picked.
        out.sort(key=lambda r: self.cooldowns.cooling(r.profile.name) > 0)
        return out

    def pick(
        self,
        capability: Capability | str,
        prefer: Preference = "cheap",
        exclude_provider: str | None = None,
        needs_context: int | None = None,
    ) -> ModelProfile:
        return self.rank(capability, prefer, exclude_provider, needs_context)[0].profile

    def explain(
        self,
        capability: Capability | str,
        prefer: Preference = "cheap",
        exclude_provider: str | None = None,
        needs_context: int | None = None,
    ) -> str:
        try:
            ranked = self.rank(capability, prefer, exclude_provider, needs_context)
        except NoProfileAvailable as e:
            return str(e)
        best = ranked[0]
        p = best.profile
        parts = [
            f"{p.name} ({p.provider}/{p.model}) for {Capability(capability).value}, prefer={prefer}",
            f"score {best.score:.2f}: tag '{prefer}' {'yes' if best.tag_match else 'no'}, "
            f"cost {best.cost_score:.2f}, context {best.context_score:.2f}",
            f"{len(ranked)} candidate(s)",
        ]
        if exclude_provider:
            parts.append(f"excluded provider {exclude_provider}")
        if needs_context:
            parts.append(f"needs context >= {needs_context}")
        cooling = [r.profile.name for r in ranked if self.cooldowns.cooling(r.profile.name) > 0]
        if cooling:
            parts.append(f"cooled down: {', '.join(cooling)}")
        if len(ranked) > 1:
            parts.append(f"runner-up {ranked[1].profile.name} ({ranked[1].score:.2f})")
        return "; ".join(parts)
