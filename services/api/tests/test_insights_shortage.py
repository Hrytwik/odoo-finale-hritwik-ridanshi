"""Spec §8.2, hand-worked (today is 10 Oct 2026)."""
import datetime as dt
from fractions import Fraction as F

from app.modules.insights.engine.shortage import Demand, forecast, round_up, spinning_window

TODAY = dt.date(2026, 10, 10)


def test_the_worked_case_cotton_falls_below_on_the_12th():
    demands = [Demand("ORD-A", F(200), spinning_window(F(1, 2))), Demand("ORD-B", F(400), spinning_window(F(5, 2)))]
    assert [d.window_days for d in demands] == [1, 3]
    result = forecast(F(800), F(300), demands, 5, TODAY)          # stock at the end of each day: 466.67, 333.33, 200
    assert (result.free_kg, result.falls_below_on, result.order_by, result.overdue_days) == (
        200, dt.date(2026, 10, 12), dt.date(2026, 10, 7), 3)
    assert result.suggested_kg == 100


def test_the_contracts_own_example_suggests_750():
    result = forecast(F(100), F(300), [Demand("X", F("517.5"), 1)], 5, TODAY)
    assert (result.free_kg, result.suggested_kg) == (F(-835, 2), 750)
    assert (result.falls_below_on, result.order_by, result.overdue_days) == (TODAY, dt.date(2026, 10, 5), 5)


def test_a_type_that_never_falls_short_is_not_reported():
    assert forecast(F(800), F(300), [Demand("A", F(100), 2)], 5, TODAY) is None
    assert forecast(F(800), F(300), [], 5, TODAY) is None
    assert forecast(F(300), F(300), [], 5, TODAY) is None                          # exactly at the level is not below it


def test_already_below_the_level_means_today_even_with_no_orders():
    result = forecast(F(100), F(300), [], 5, TODAY)
    assert (result.falls_below_on, result.suggested_kg, result.order_by) == (TODAY, 200, dt.date(2026, 10, 5))


def test_no_supplier_means_no_order_by_date():
    result = forecast(F(100), F(300), [], None, TODAY)
    assert (result.order_by, result.overdue_days, result.falls_below_on) == (None, 0, TODAY)


def test_an_order_by_date_in_the_future_is_not_overdue():
    result = forecast(F(1000), F(300), [Demand("A", F(800), 8)], 2, TODAY)         # 100 kg a day: 900, 800, ... 300 on day 7
    assert result.falls_below_on == dt.date(2026, 10, 17)                          # day 7 ends AT 300 (not below), day 8 at 200
    assert result.order_by == dt.date(2026, 10, 15) and result.overdue_days == 0


def test_windows_and_rounding():
    assert spinning_window(F(0)) == 1 and spinning_window(F(1)) == 1 and spinning_window(F(11, 10)) == 2
    assert spinning_window(None) == 1                                              # cannot spin: all at once
    assert [round_up(F(x), 50) for x in (0, 1, 50, 51, 100, 717.5)] == [0, 50, 50, 100, 100, 750]


def test_stock_only_goes_down_so_it_is_reported_exactly_when_free_is_below_the_level():
    import random
    rng = random.Random(3)
    for _ in range(300):
        demands = [Demand(f"O{i}", F(rng.randint(0, 600)), rng.randint(1, 6)) for i in range(rng.randint(0, 4))]
        on_hand, level = F(rng.randint(0, 1500)), F(rng.randint(0, 500))
        result = forecast(on_hand, level, demands, 3, TODAY)
        free = on_hand - sum((d.outstanding_kg for d in demands), F(0))
        assert (result is not None) == (free < level)
        if result is not None:
            assert result.falls_below_on is not None and result.suggested_kg >= level - free
