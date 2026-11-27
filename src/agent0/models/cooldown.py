from __future__ import annotations

import time
from collections.abc import Callable

_BASE_COOLDOWN_S = 60.0
_MAX_COOLDOWN_S = 1800.0


class CooldownTracker:
    """Per-profile rate-limit memory. A profile that 429s is demoted by the
    router until its cooldown expires, so retries don't keep picking a
    provider whose quota is exhausted."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._until: dict[str, float] = {}
        self._strikes: dict[str, int] = {}

    def cooling(self, profile: str) -> float:
        """Seconds left on the profile's cooldown; 0 when available."""
        until = self._until.get(profile)
        if until is None:
            return 0.0
        left = until - self._clock()
        if left <= 0:
            self._until.pop(profile, None)
            self._strikes.pop(profile, None)
            return 0.0
        return left

    def record(self, profile: str, retry_after_s: float | None = None) -> float:
        """Note a rate-limit failure; returns the cooldown applied."""
        strikes = self._strikes.get(profile, 0) + 1
        self._strikes[profile] = strikes
        delay = (
            retry_after_s
            if retry_after_s is not None
            else min(_BASE_COOLDOWN_S * 2 ** (strikes - 1), _MAX_COOLDOWN_S)
        )
        delay = min(delay, _MAX_COOLDOWN_S)
        self._until[profile] = self._clock() + delay
        return delay

    def reset(self) -> None:
        self._until.clear()
        self._strikes.clear()


_DEFAULT = CooldownTracker()


def default_tracker() -> CooldownTracker:
    return _DEFAULT
