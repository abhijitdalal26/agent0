import pytest

from agent0.config import Settings
from agent0.policy import BudgetExceeded, BudgetMeter, daily_cap_reason


class _Usage:
    def __init__(self, total: float) -> None:
        self.total = total
        self.since = None

    async def total_since(self, since):
        self.since = since
        return self.total


class _Repos:
    def __init__(self, total: float) -> None:
        self.usage = _Usage(total)


async def test_daily_cap_off_without_setting_or_repos():
    assert await daily_cap_reason(Settings(daily_budget_usd=None), _Repos(999)) is None
    assert await daily_cap_reason(Settings(daily_budget_usd=1.0), None) is None


async def test_daily_cap_reason():
    under = await daily_cap_reason(Settings(daily_budget_usd=10.0), _Repos(9.99))
    assert under is None
    over = await daily_cap_reason(Settings(daily_budget_usd=10.0), _Repos(10.0))
    assert over is not None and "daily budget cap" in over


def test_steps():
    m = BudgetMeter(max_steps=2)
    m.step()
    m.step()
    with pytest.raises(BudgetExceeded) as e:
        m.step()
    assert e.value.kind == "steps"


def test_usd():
    m = BudgetMeter(max_usd=0.10)
    m.charge(0.06)
    with pytest.raises(BudgetExceeded) as e:
        m.charge(0.06)
    assert e.value.kind == "usd"
    assert m.usd == pytest.approx(0.12)


def test_elapsed():
    now = [100.0]
    m = BudgetMeter(max_minutes=1)
    m._clock = lambda: now[0]
    m._started = 100.0
    m.check()
    now[0] += 61
    with pytest.raises(BudgetExceeded) as e:
        m.check()
    assert e.value.kind == "minutes"
    assert m.elapsed_s == 61
