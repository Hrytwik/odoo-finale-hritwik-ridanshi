"""Spec §8.1, hand-worked. Capacities per day: spinning 200 kg, weaving 100 m, dyeing 150 m; today is 10 Oct 2026."""
import datetime as dt
import random
from fractions import Fraction as F

import pytest
from app.modules.insights.engine.schedule import (
    EffRun, OpenOrder, StageCapacity, all_etas, make_plan, observed_efficiency, queue_order,
)

TODAY = dt.date(2026, 10, 10)
CONFIRMED = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
CAP = {"spinning": F(200), "weaving": F(100), "dyeing": F(150)}


def order(code, deadline_day, spin, weave, dye, passed=False, confirmed=CONFIRMED):
    return OpenOrder(code, dt.date(2026, 10, deadline_day), confirmed,
                     {"spinning": F(spin), "weaving": F(weave), "dyeing": F(dye)}, passed)


def trio(b_deadline=25):
    return [order("ORD-A", 14, 100, 300, 300), order("ORD-B", b_deadline, 400, 200, 200), order("ORD-C", 30, 0, 100, 100)]


def stages(weaving_shifts=2, weaving_per_day=100):
    """Three 8-hour shifts. Spinning (200 kg a day) and dyeing (150 m a day) run all three; weaving runs `weaving_shifts`
    of them and makes `weaving_per_day` metres a day at that setting."""
    shifts = (F(8), F(8), F(8))
    return {"spinning": StageCapacity(F(200, 24), shifts, 3),
            "weaving": StageCapacity(F(weaving_per_day, 8 * weaving_shifts), shifts, weaving_shifts),
            "dyeing": StageCapacity(F(150, 24), shifts, 3)}


def test_the_worked_case():
    plan = make_plan(trio(), CAP, TODAY)
    assert plan.finish["ORD-A"] == {"spinning": F(1, 2), "weaving": 3, "dyeing": 3}
    assert plan.added["ORD-A"] == {"spinning": F(1, 2), "weaving": F(5, 2), "dyeing": 0}
    assert plan.finish["ORD-B"] == {"spinning": F(5, 2), "weaving": 5, "dyeing": 5}
    assert plan.finish["ORD-C"] == {"spinning": 0, "weaving": 6, "dyeing": 6}              # no spinning left: passes straight through
    assert plan.delivery == {"ORD-A": dt.date(2026, 10, 15), "ORD-B": dt.date(2026, 10, 17), "ORD-C": dt.date(2026, 10, 18)}


def test_a_late_order_names_its_bottleneck_and_the_shift_that_would_fix_it():
    eta = all_etas(trio(), stages(weaving_shifts=2), TODAY)["ORD-A"]                        # weaving: 100 m a day on 2 of 3 shifts
    assert (eta.delivery, eta.days_late, eta.bottleneck) == (dt.date(2026, 10, 15), 1, "weaving")
    assert eta.stage_dates == {"spinning": dt.date(2026, 10, 11), "weaving": dt.date(2026, 10, 13), "dyeing": dt.date(2026, 10, 13)}
    assert [(w.kind, w.label, w.delivery, w.days_late) for w in eta.what_ifs] == [
        ("add_shift", "Add a third shift on weaving", dt.date(2026, 10, 14), 0)]       # already first, so no move-to-front


def test_moving_an_order_to_the_front_names_the_orders_it_harms():
    etas = all_etas(trio(b_deadline=16), stages(weaving_shifts=3), TODAY)
    b = etas["ORD-B"]
    assert (b.delivery, b.days_late, b.bottleneck) == (dt.date(2026, 10, 17), 1, "spinning")            # a tie, the earlier stage wins
    assert [(w.kind, w.delivery, w.days_late) for w in b.what_ifs] == [("move_to_front", dt.date(2026, 10, 14), 0)]
    assert b.what_ifs[0].label == "Move ORD-B to the front of every queue (ORD-A would be 3 days late)"


def test_an_on_time_order_has_no_bottleneck_and_no_what_ifs():
    eta = all_etas(trio(), stages(), TODAY)["ORD-B"]
    assert (eta.days_late, eta.bottleneck, eta.what_ifs) == (0, None, [])


def test_the_ordinal_labels_and_the_no_add_shift_when_every_shift_already_runs():
    full = stages(weaving_shifts=3)
    assert not full["weaving"].can_add_shift and stages(weaving_shifts=2)["weaving"].can_add_shift
    late = all_etas([order("ORD-A", 11, 100, 300, 300)], full, TODAY)["ORD-A"]
    assert late.days_late > 0 and all(w.kind != "add_shift" for w in late.what_ifs)


def test_the_qc_day_is_skipped_when_everything_has_passed():
    done = [order("ORD-P", 30, 0, 0, 0, passed=True), order("ORD-Q", 30, 0, 0, 0)]
    plan = make_plan(done, CAP, TODAY)
    assert (plan.delivery["ORD-P"], plan.delivery["ORD-Q"]) == (dt.date(2026, 10, 11), dt.date(2026, 10, 12))


def test_ties_go_to_the_earlier_confirmed_order_then_to_the_code():
    early = CONFIRMED
    late = CONFIRMED + dt.timedelta(days=1)
    queue = queue_order([order("ORD-9", 20, 1, 1, 1, confirmed=late), order("ORD-2", 20, 1, 1, 1, confirmed=late),
                         order("ORD-5", 20, 1, 1, 1, confirmed=early), order("ORD-1", 19, 1, 1, 1, confirmed=late)])
    assert [o.code for o in queue] == ["ORD-1", "ORD-5", "ORD-2", "ORD-9"]


def test_a_stage_with_work_and_no_capacity_makes_the_date_unknown_for_that_order_and_those_behind_it():
    no_loom = {**CAP, "weaving": F(0)}
    plan = make_plan(trio(), no_loom, TODAY)
    assert plan.delivery["ORD-A"] is None and plan.delivery["ORD-B"] is None and plan.delivery["ORD-C"] is None
    assert plan.finish["ORD-A"]["spinning"] == F(1, 2)                                  # earlier stages are still known
    ahead = [order("ORD-X", 12, 100, 0, 0), *trio()]
    assert make_plan(ahead, no_loom, TODAY).delivery["ORD-X"] is not None                  # nothing to weave: not stuck
    assert all_etas(trio(), {**stages(), "weaving": StageCapacity(F(0), (F(8),) * 3, 2)}, TODAY)["ORD-A"] is None   # a loom-less stage


def test_capacity_is_rated_output_times_efficiency_times_hours():
    loom = StageCapacity(F(2 * 25) * F(4, 5), (F(8), F(8), F(8)), 2)           # two looms of 25 m/h at 0.8
    assert loom.per_day() == 640 and loom.per_day(3) == 960 and loom.per_day(1) == 320


def test_observed_efficiency():
    runs = [EffRun("weaving", F(5), F(25), F(100)), EffRun("weaving", F(5), F(25), F(100))]
    assert observed_efficiency(runs)["weaving"] == F(4, 5)                                # 200 / 250
    assert observed_efficiency(runs)["spinning"] == F(4, 5)                               # no history: the default
    assert observed_efficiency([EffRun("weaving", F(5), F(25), F(500))])["weaving"] == 1  # capped at 1
    assert observed_efficiency([EffRun("weaving", F(1, 2), F(25), F(1))])["weaving"] == F(4, 5)   # under an hour: the default
    assert observed_efficiency([EffRun("weaving", F(3), F(25), F(0))])["weaving"] == 0    # a real, bad result stays bad


def test_property_more_capacity_never_delays_anyone_and_the_front_never_hurts_the_mover():
    rng = random.Random(8)
    for _ in range(300):
        orders = [OpenOrder(f"O{i}", dt.date(2026, 10, rng.randint(11, 30)), CONFIRMED + dt.timedelta(hours=i),
                            {"spinning": F(rng.randint(0, 500)), "weaving": F(rng.randint(0, 400)), "dyeing": F(rng.randint(0, 400))})
                  for i in range(rng.randint(1, 6))]
        cap = {"spinning": F(rng.randint(50, 300)), "weaving": F(rng.randint(30, 200)), "dyeing": F(rng.randint(30, 200))}
        base = make_plan(orders, cap, TODAY)
        faster = make_plan(orders, {k: v * F(3, 2) for k, v in cap.items()}, TODAY)
        for o in orders:
            assert faster.delivery[o.code] <= base.delivery[o.code]
            fin = base.finish[o.code]
            assert fin["spinning"] <= fin["weaving"] <= fin["dyeing"]                         # a stage never ends before the last
            assert make_plan(orders, cap, TODAY, front=o.code).delivery[o.code] <= base.delivery[o.code]


def test_a_what_if_that_does_not_change_the_date_is_not_offered():
    """100 m to weave at 100 m a day is exactly one day; with a third shift (150 m a day) it is two thirds of a day, which
    rounds up to the same one day, so adding a shift would not help and must not be suggested."""
    only = [order("ORD-A", 12, 0, 100, 0)]
    eta = all_etas(only, stages(weaving_shifts=2), TODAY)["ORD-A"]
    assert (eta.delivery, eta.days_late, eta.bottleneck) == (dt.date(2026, 10, 13), 1, "weaving")
    assert eta.what_ifs == []


def test_what_ifs_can_be_left_out_or_limited_to_one_order():
    cheap = all_etas(trio(b_deadline=16), stages(weaving_shifts=3), TODAY, with_what_ifs=False)
    assert cheap["ORD-B"].days_late == 1 and cheap["ORD-B"].what_ifs == []
    one = all_etas(trio(b_deadline=14), stages(weaving_shifts=2), TODAY, only="ORD-B")
    assert one["ORD-A"].days_late == 1 and one["ORD-A"].what_ifs == []                      # late too, but not asked about
    assert one["ORD-B"].days_late == 3 and [w.kind for w in one["ORD-B"].what_ifs] == ["move_to_front"]
