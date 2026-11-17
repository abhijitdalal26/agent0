import pytest

from agent0.policy import BudgetExceeded, BudgetMeter


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
