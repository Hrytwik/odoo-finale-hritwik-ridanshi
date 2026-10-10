"""Spec §7.2, hand-worked: shift A is 06:00-14:00 (8 hours) and the daily wage is 800."""
import datetime as dt
from fractions import Fraction as F

from app.modules.costing.engine.labour import split_labour
from app.modules.costing.engine.records import Shift
from tests.costing_records import A, B, C, SHIFTS, at, present, run, worker

NOW = at(30, 12)


def split(attendance, runs, *workers):
    return split_labour(attendance, {w.id: w for w in workers}, SHIFTS, runs, NOW)


def test_present_with_a_four_hour_run_leaves_the_rest_idle():
    labour = split([present(1, 3)], [run(1, 1, at(3, 6), at(3, 10))], worker(1))
    assert labour.per_run == {1: 400}
    assert (labour.idle, labour.support) == (400, 0)


def test_half_day_pays_half_and_has_half_the_hours():
    short = split([present(1, 3, status="half_day")], [run(1, 1, at(3, 6), at(3, 8))], worker(1))
    assert short.per_run == {1: 200} and short.idle == 200            # pay 400, paid hours 4, run 2 hours
    long = split([present(1, 3, status="half_day")], [run(1, 1, at(3, 6), at(3, 12))], worker(1))
    assert long.per_run == {1: 400} and long.idle == 0                # 6 hours is more than the 4 paid


def test_one_weaver_on_three_looms_shares_the_pay_three_ways_and_nothing_is_idle():
    runs = [run(i, 1, at(3, 6), at(3, 14), machine=i) for i in (1, 2, 3)]
    labour = split([present(1, 3)], runs, worker(1))
    assert labour.per_run == {1: F(800, 3), 2: F(800, 3), 3: F(800, 3)}
    assert sum(labour.per_run.values()) == 800 and labour.idle == 0


def test_a_run_across_a_shift_change_takes_pay_from_both_shifts():
    both = split([present(1, 3, A), present(1, 3, B)], [run(1, 1, at(3, 12), at(3, 16))], worker(1))
    assert both.per_run == {1: 400} and both.idle == 1200 and both.uncovered == {}      # 200 + 200 of 1,600 paid
    only_a = split([present(1, 3, A)], [run(1, 1, at(3, 12), at(3, 16))], worker(1))
    assert only_a.per_run == {1: 200}
    assert only_a.uncovered == {1: 2}                                                   # 14:00-16:00 has no attendance


def test_leftover_pay_goes_to_idle_for_an_operator_and_to_support_staff_for_everyone_else():
    labour = split([present(1, 3), present(2, 3), present(3, 3)], [],
                   worker(1, "operator"), worker(2, "storekeeper"), worker(3, "supervisor"))
    assert (labour.idle, labour.support) == (800, 1600)


def test_a_supervisor_who_runs_a_machine_for_two_hours_is_costed_for_those_hours():
    labour = split([present(3, 3)], [run(1, 3, at(3, 6), at(3, 8))], worker(3, "supervisor"))
    assert labour.per_run == {1: 200} and labour.support == 600 and labour.idle == 0


def test_a_night_shift_is_dated_by_the_day_it_starts():
    ran_next_morning = run(1, 1, at(11, 2), at(11, 4))
    on_the_10th = split([present(1, 10, C)], [ran_next_morning], worker(1))
    assert on_the_10th.per_run == {1: 200} and on_the_10th.uncovered == {}              # 800 x 2/8
    on_the_11th = split([present(1, 11, C)], [ran_next_morning], worker(1))
    assert on_the_11th.per_run == {} and on_the_11th.uncovered == {1: 2}                # that record starts at 22:00


def test_absent_is_skipped_and_costs_nothing():
    labour = split([present(1, 3, status="absent")], [run(1, 1, at(3, 6), at(3, 10))], worker(1))
    assert labour.records == [] and labour.per_run == {} and labour.uncovered == {1: 4}


def test_a_zero_length_run_costs_nothing_and_raises_no_warning():
    instant = run(1, 1, at(3, 7), at(3, 7))
    assert split([], [instant], worker(1)).uncovered == {}


def test_a_run_still_open_is_costed_up_to_now():
    labour = split_labour([present(1, 3)], {1: worker(1)}, SHIFTS, [run(1, 1, at(3, 6), None)], at(3, 10))
    assert labour.per_run == {1: 400}


def test_the_workers_runs_on_other_orders_share_the_same_pay():
    runs = [run(1, 1, at(3, 6), at(3, 10), order=1), run(2, 1, at(3, 6), at(3, 10), order=2, machine=2)]
    labour = split([present(1, 3)], runs, worker(1))
    assert labour.per_run == {1: 400, 2: 400} and labour.idle == 0                      # H = 8 = paid hours


def test_pay_is_always_fully_accounted_for():
    runs = [run(1, 1, at(3, 6), at(3, 11)), run(2, 1, at(3, 9), at(3, 17), machine=2), run(3, 2, at(3, 14), at(3, 22))]
    labour = split([present(1, 3), present(1, 3, B, "half_day"), present(2, 3, B), present(3, 3, A)], runs,
                   worker(1), worker(2, "inspector"), worker(3))
    assert sum(labour.per_run.values()) + labour.idle + labour.support == labour.pay == 800 + 400 + 800 + 800


def test_two_overlapping_shifts_each_pay_their_own_record_but_coverage_is_counted_once():
    """Shifts A (06:00-14:00) and a custom 12:00-20:00 overlap for two hours. A worker marked present for both is paid
    for both records (the wages page does the same), a 2 h run inside the overlap takes a share from each, and the
    run's hours are covered, not covered twice."""
    late = Shift(9, "L", dt.time(12), dt.time(20))
    labour = split_labour([present(1, 3, A), present(1, 3, late)], {1: worker(1)}, {**SHIFTS, 9: late},
                          [run(1, 1, at(3, 12), at(3, 14))], NOW)
    assert labour.per_run == {1: 400}                     # 800 x 2/8 from each record
    assert labour.pay == 1600 and labour.idle == 1200 and labour.uncovered == {}
