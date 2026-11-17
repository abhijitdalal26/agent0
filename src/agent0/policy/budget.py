from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from pydantic import PrivateAttr

from agent0.core.types import Budget


class BudgetExceeded(Exception):
    def __init__(self, kind: str, limit: float, used: float) -> None:
        super().__init__(f"budget exceeded: {kind} {used:.4g} > {limit:.4g}")
        self.kind = kind
        self.limit = limit
        self.used = used


class BudgetMeter(Budget):
    _steps: int = PrivateAttr(default=0)
    _usd: float = PrivateAttr(default=0.0)
    _clock: Callable[[], float] = PrivateAttr(default=time.monotonic)
    _started: float = PrivateAttr(default=0.0)

    def model_post_init(self, __context: Any) -> None:
        self._started = self._clock()

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def usd(self) -> float:
        return self._usd

    @property
    def elapsed_s(self) -> float:
        return self._clock() - self._started

    def check(self) -> None:
        if self._steps > self.max_steps:
            raise BudgetExceeded("steps", self.max_steps, self._steps)
        if self._usd > self.max_usd:
            raise BudgetExceeded("usd", self.max_usd, self._usd)
        if self.elapsed_s > self.max_minutes * 60:
            raise BudgetExceeded("minutes", self.max_minutes, self.elapsed_s / 60)

    def step(self) -> None:
        self._steps += 1
        self.check()

    def charge(self, usd: float) -> None:
        self._usd += usd
        self.check()
