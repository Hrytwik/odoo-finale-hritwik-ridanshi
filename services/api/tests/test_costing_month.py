"""Spec §7.5, hand-worked: the month of October 2026 with one order."""
import datetime as dt
import random
from fractions import Fraction as F

from app.modules.costing.engine.labour import split_labour
from app.modules.costing.engine.month import machine_hours, month_costs, month_window
from app.modules.costing.engine.records import Downtime, WriteOff, YarnMove
from app.modules.costing.engine.runs import run_costs
from tests.costing_records import A, B, C, SHIFTS, at, issue, link, machine, present, roll, run, worker

OCT = month_window(2026, 10)
NOW = at(31, 20, month=10)


def october(runs, machines, moves, writeoffs, attendance, workers, now=NOW):
    labour = split_labour(attendance, {w.id: w for w in workers}, SHIFTS, runs, now)
    return month_costs(*OCT[:2], OCT[2], runs, machines, moves, writeoffs, labour, now), labour


def test_the_worked_month_reconciles_to_27_540():
    spin = run(1, 1, at(3, 6), at(3, 10), stage="spinning", machine=1)             # 4 h at 55 = 220
    weave = run(2, 2, at(5, 8), at(5, 20), stage="weaving", machine=2)             # 12 h at 60 = 720, no attendance
    machines = {1: machine(1, "spinning", rate=55), 2: machine(2, "weaving", rate=60)}
    moves = [issue(1, 120, 250, at(3, 8)), YarnMove(1, F(20), F(250), at(4, 9))]
    writeoffs = [WriteOff(F(-5), F(250), at(12, 10))]
    costs, labour = october([spin, weave], machines, moves, writeoffs, [present(1, 3), present(3, 3)],
                            [worker(1), worker(2), worker(3, "storekeeper")])
    assert costs.yarn == 25000 and costs.machine == 940 and costs.writeoffs == 1250
    assert costs.wages == 1600 and costs.idle == 400 and costs.support == 800
    assert costs.per_order[1] == {"yarn": 25000, "machine": 940, "labour": 400}
    assert costs.order_total == 26340
    assert costs.order_total + costs.idle + costs.support == costs.yarn + costs.wages + costs.machine == 27540
    assert labour.uncovered == {2: 12}                                              # the weaving run: a warning


def test_a_run_over_the_month_end_counts_each_part_in_its_own_month():
    night = run(1, 1, at(31, 22), at(1, 4, month=11), machine=1)                    # 22:00 31 Oct to 04:00 1 Nov
    machines = {1: machine(1, rate=60)}
    now = at(15, 12, month=11)
    october_costs, _ = october([night], machines, [], [], [], [worker(1)], now)
    first, after, span = month_window(2026, 11)
    labour = split_labour([], {1: worker(1)}, SHIFTS, [night], now)
    november = month_costs(first, after, span, [night], machines, [], [], labour, now)
    assert october_costs.machine == 120 and november.machine == 240


def test_a_pay_record_counts_in_the_month_it_is_dated_even_if_the_run_ends_in_the_next():
    night = run(1, 1, at(31, 22), at(1, 4, month=11), machine=1)
    attendance = [present(1, 31, C)]                                                # pay 800 for 22:00-06:00
    costs, labour = october([night], {1: machine(1)}, [], [], attendance, [worker(1)], at(15, 12, month=11))
    assert costs.wages == 800 and costs.per_order[1]["labour"] == 600 and costs.idle == 200   # 6 of 8 hours


def test_an_open_run_is_costed_only_up_to_now():
    open_run = run(1, 1, at(31, 10), None, machine=1)
    costs, _ = october([open_run], {1: machine(1, rate=60)}, [], [], [], [worker(1)], at(31, 12))
    assert costs.machine == 120


def test_machine_hours_split_into_running_idle_and_down_inside_shift_time():
    m = machine(1, "weaving", rate=60, rated=20, created=at(1, 0))
    runs = [run(1, 1, at(2, 6), at(2, 14), machine=1)]
    downs = [Downtime(1, at(2, 14), at(2, 20))]
    span = (at(2, 0), at(3, 0))
    h = machine_hours(m, runs, downs, [], [], list(SHIFTS.values()), span, at(31, 0))
    assert (h.running, h.down, h.idle) == (8, 6, 10)                                # shifts A+B+C cover all 24 h
    assert h.running + h.down + h.idle == 24


def test_a_machine_is_counted_only_from_the_day_it_was_created():
    m = machine(1, created=at(30, 12))
    h = machine_hours(m, [], [], [], [], list(SHIFTS.values()), OCT[2], at(31, 12))
    assert h.idle == 24                                                              # 12:00 on the 30th to 12:00 on the 31st


def test_an_open_downtime_runs_up_to_now_and_hours_outside_shift_time_are_ignored():
    day_only = [A]                                                                   # 06:00-14:00 only
    m = machine(1, created=at(1, 0))
    h = machine_hours(m, [], [Downtime(1, at(10, 10), None)], [], [], day_only, (at(10, 0), at(11, 0)), at(10, 12))
    assert (h.down, h.idle, h.running) == (2, 4, 0)                                  # 06:00-10:00 idle, 10:00-12:00 down


def test_output_by_stage():
    spin_m, loom_m, dye_m = machine(1, "spinning"), machine(2, "weaving"), machine(3, "dyeing")
    spin = run(1, 1, at(3, 6), at(3, 10), stage="spinning", machine=1, output_kg=118)
    weave = run(2, 1, at(5, 8), at(5, 20), machine=2)
    dyed = run(3, 1, at(6, 8), at(6, 12), stage="dyeing", machine=3)
    rolls = [roll(1, 600, made=at(5, 12)), roll(2, 400, made=at(5, 13))]
    links = [link(1, 2), link(2, 2), link(1, 3, "dye")]
    out = lambda mach: machine_hours(mach, [spin, weave, dyed], [], rolls, links, list(SHIFTS.values()), OCT[2], NOW).output  # noqa: E731
    assert (out(spin_m), out(loom_m), out(dye_m)) == (118, 1000, 600)


def test_property_the_month_always_reconciles_and_the_months_add_up_to_the_whole():
    rng = random.Random(61)
    for _ in range(200):
        workers = [worker(i, rng.choice(["operator", "operator", "inspector", "storekeeper"]), rng.choice([700, 800, 900]))
                   for i in range(1, 5)]
        machines = {1: machine(1, "spinning", rate=rng.randint(0, 90)), 2: machine(2, "weaving", rate=rng.randint(0, 90))}
        runs = []
        for i in range(1, rng.randint(2, 8)):
            day, hour = rng.randint(1, 28), rng.randint(0, 20)
            length = rng.randint(0, 40)
            start = at(day, hour) if rng.random() < 0.9 else at(28, 22)
            end = start + dt.timedelta(hours=length) if rng.random() < 0.85 else None
            runs.append(run(i, rng.randint(1, 4), start, end, order=rng.randint(1, 3), machine=rng.choice([1, 2, None])))
        moves = [issue(r.id, rng.randint(1, 50), rng.choice([200, 250, 300]), r.start) for r in runs if rng.random() < 0.5]
        attendance = [present(w.id, d, rng.choice([A, B, C]), rng.choice(["present", "half_day", "absent"]))
                      for w in workers for d in rng.sample(range(1, 29), 6)]
        costs, labour = october(runs, machines, moves, [], attendance, workers, at(31, 23))
        yarn_all = sum((-m.kg * m.cost_per_kg for m in moves), F(0))
        assert costs.yarn == yarn_all                                                # every issue sits inside October
        assert costs.order_total + costs.idle + costs.support == costs.yarn + costs.wages + costs.machine
        # a pay record never loses a rupee: allocated + idle + support = pay
        assert sum(labour.per_run.values()) + labour.idle + labour.support == labour.pay


def test_pay_records_dated_outside_the_month_are_left_out():
    attendance = [present(1, 30, A, month=9), present(1, 15, A), present(1, 1, A, month=11)]
    costs, labour = october([], {}, [], [], attendance, [worker(1)])
    assert costs.wages == 800 and costs.idle == 800                                  # only the 15th
    assert labour.pay == 2400                                                        # the split itself sees all three


def test_yarn_issues_and_write_offs_outside_the_month_are_left_out():
    spin = run(1, 1, at(3, 6), at(3, 10), stage="spinning", machine=1)
    moves = [issue(1, 10, 100, at(30, 9, month=9)), issue(1, 20, 100, at(3, 8)), issue(1, 40, 100, at(1, 0, month=11))]
    writeoffs = [WriteOff(F(-1), F(250), at(30, 9, month=9)), WriteOff(F(-2), F(250), at(12, 9)),
                 WriteOff(F(-4), F(250), at(1, 0, month=11))]
    costs, _ = october([spin], {1: machine(1)}, moves, writeoffs, [], [worker(1)])
    assert costs.yarn == 2000 and costs.writeoffs == 500                              # only 20 kg and 2 kg


def test_hours_are_never_counted_twice_if_a_run_and_a_downtime_overlap():
    m = machine(1, created=at(1, 0))
    overlapping = run(1, 1, at(10, 6), at(10, 10), machine=1)
    h = machine_hours(m, [overlapping], [Downtime(1, at(10, 8), at(10, 12))], [], [], list(SHIFTS.values()),
                      (at(10, 0), at(11, 0)), at(12, 0))
    assert (h.running, h.down, h.idle) == (2, 4, 18) and h.running + h.down + h.idle == 24
