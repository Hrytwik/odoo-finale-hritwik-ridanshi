# B6 — Costing (true cost per metre, month-end) Implementation Plan

> **Summary:** Replaces the example data behind `GET /costing/rolls/{code}`, `GET /costing/orders/{code}` and `GET /reports/month` with a real, tested costing engine: yarn + machine hours + operators' wages split by hours actually worked, handed to rolls and orders, rejected rolls' cost moved onto good rolls, and a month report (profit, cash, machines) that reconciles to the rupee. Cost is visible to owner and accountant only; the roll passport's `cost` becomes real for them. One additive contract field: `ProfitPanel.support_staff`.
> **Last updated:** 2026-10-10 22:22 IST (Tasks 1-3 done and verified: the engine is complete; Tasks 4-6 still to do)

> **How this plan is executed:** inline, one task at a time (atomic-workflow): test first, the full suite twice at each boundary, the important behaviours mutation-checked. Steps use checkbox (`- [ ]`) syntax.

**Goal:** the owner can scan a roll and see its true cost per metre, open an order and see where its money went, and close the month with profit, cash and machine figures that reconcile exactly.

**Architecture:** a pure engine (`costing/engine/`, exact `fractions.Fraction` arithmetic, no database, no clock) takes plain records built by `costing/loader.py` and returns per-run, per-roll, per-order and per-month figures; `costing/service.py` rounds to the paisa and shapes the existing response models; `costing/router.py` serves them. Nothing is stored, locked or published (read-only, no migration).

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2, PostgreSQL, pytest (`uv run python -m pytest -p no:warnings -o addopts=`). No new dependencies.

**Spec:** `docs/specs/2026-10-10-textile-mill-design.md` §7 (the whole costing method, with hand-worked numbers) and rule R18 (cost visibility). Read §7 first; this plan implements it exactly.

## Status

Written 2026-10-10 21:31 IST after the design was approved section by section (spec §7). **What was verified before this plan was shown:** the engine (Tasks 1-3: `records`, `intervals`, `labour`, `runs`, `allocation`, `month`) and its 36 tests were written and run in a scratch folder outside the repository (36 passed); 14 deliberate breaks of the engine were each caught by a test, after three weak tests were strengthened (the wages month filter, the write-off month filter and the run-versus-downtime overlap each survived the first time). **What was NOT run yet:** `loader.py`, `service.py`, the router, the passport change, `costing_world.py` and the API tests (Tasks 4-5) have only been compile-checked; run them in a scratch copy first (atomic-workflow step 3) and expect small fixes. Tasks 4-6 are still to do.

Task 1 done and verified (2026-10-10 22:16 IST): the engine's `records`, `intervals` and `labour` modules and 16 tests (4 interval, 12 labour) added exactly as written in this plan; they failed first with `ModuleNotFoundError`, then passed; the six planned mutations of `labour.py` (divisor ignoring paid hours, idle and support swapped, everyone treated as an operator, an open run not capped at now, a half day paying in full, uncovered hours never reported) were each caught by a test and the file was restored afterwards; full suite 1,062 passed, twice (1,046 + 16); the interface Task 2 consumes (`labour.run_interval`, `intervals.hours`, the `records` classes) exists with the names the plan uses. No contract, database or route change.

Task 2 done and verified (2026-10-10 22:19 IST): `engine/runs.py` and `engine/allocation.py` and 8 tests (the worked order at 17.50 and 18.33 a metre and 17.8125 per good metre, a run with no rolls going into the pool, no good roll, a roll dyed in two runs, a hand-mended rework, each final condition alone, run costs, and a 300-case property check that the good rolls always carry exactly the order total); they failed first (collection error) then passed; the five planned mutations (no reject redistribution, runs without rolls dropped, pool not spread, final ignoring open runs, a yarn return added instead of netted) were each caught and the files restored; full suite 1,070 passed, twice (1,062 + 8).

Task 3 done and verified (2026-10-10 22:22 IST): `engine/month.py` and 12 tests (the worked month reconciling at 27,540, a run over the month end splitting 120 and 240, a pay record counting in the month it is dated, an open run costed only up to now, machine hours split into running, idle and down inside shift time, the creation-date start, an open downtime, output by stage, the outside-the-month cases for pay, yarn and write-offs, a run overlapping a downtime never counted twice, and a 200-case property check that the month always reconciles); they failed first (collection error) then passed; all seven planned mutations were each caught (the four that survived in the scratch run, now covered by their own tests, included) and the file was restored; full suite 1,082 passed, twice (1,070 + 12). The engine is complete (36 engine tests).

## Global Constraints

- Quantities and money are exact inside the engine (`fractions.Fraction`); `Decimal` only at the rounding edge; floats only in the JSON. Money is rounded half up to the paisa (`app.core.money.q_money`); a displayed total is the sum of its rounded parts.
- Costing is **read-only**: no locks, no events, no migration, no new table.
- Roles: costing endpoints and the passport `cost` are owner and accountant only (R18); every other role, including buyers, gets 403 on the routes and `cost: null` on the passport.
- Time: every date and shift window is IST (`Asia/Kolkata`); a night shift is dated by the day it starts; code that needs "now" takes it as a parameter (`floor.service.db_now(db)` at the edge), the engine never reads a clock.
- `contracts/openapi.json` stays byte-identical **except** the one deliberate addition `ProfitPanel.support_staff` (Task 5; then `npm run contracts`, and a note to Ridanshi).
- Numeric request fields, error codes and the standard error shape are unchanged (this work adds no request bodies).
- Tests that need dates use fixed past dates (September 2026) so they do not depend on when they run.
- Commit messages: plain imperative subject, no trailers. Never `git push` (Hritwik pushes). Run the project's authorship scan on the staged diff before every commit.
- Hritwik's dev database `everest` and his servers are not touched; live checks use a throwaway database on port 8123 (never 8000/3000).

## Hand-worked numbers (the tests assert these)

**Labour** (shift A 06:00-14:00 = 8 h, wage 800): 4 h run → 400 + idle 400; half day (pay 400, 4 paid hours) with a 2 h run → 200 + idle 200, with a 6 h run → 400 + 0; one weaver on three looms for 8 h each → 266.666… each, idle 0; present for A and B with one run 12:00-16:00 → 200 + 200 (a warning for 2 uncovered hours if B is not marked); supervisor with a 2 h run → run 200, support staff 600; a night shift dated the 10th pays a run at 02:00-04:00 on the 11th.

**Rolls and orders** (rolls R1 1,000 m, R2 600 m, R3 400 m rejected; pool 20,000; weaving run 6,000 for all three; dye run 2,000 for all three; rework run 500 on R2): before redistribution R1 14,000, R2 8,900, R3 5,600 (sum 28,500); R3's 5,600 goes 3,500 to R1 and 2,100 to R2; R1 17,500 = **17.50/m**, R2 11,000 = **18.33/m**, order **17.8125** per good metre; at 25 a metre revenue 40,000, profit **11,500**.

**October engine month** (one order): yarn 120 kg issued − 20 kg returned at 250 = 25,000; machine 4 h × 55 + 12 h × 60 = 940; Ravi (operator, 800, runs the 4 h spinning run) 400 allocated + 400 idle; Kiran (storekeeper, 800, no runs) 800 support staff; wages 1,600; order cost 26,340; 26,340 + 400 + 800 = **27,540** = 25,000 + 1,600 + 940. A run 22:00 on 31 Oct to 04:00 on 1 Nov at 60/h: 120 in October, 240 in November.

**September API world** (`tests/costing_world.py`; shift A only): 100 kg issued 3 Sep at 250 = **25,000**; spinning run 06-10 at 55 = 220, weaving run 10-14 at 60 = 240, dye run 14-16 at 90 = 180 → machine **640**; Ravi (800) 06-10 → labour 400 + idle 400; Suresh (900) 10-14 → labour 450 + idle 450; Kiran (storekeeper, 800) → support **800**; Lakshmi runs the dye machine with no attendance → no labour and a warning; labour **850**; order cost **26,490**; two rolls of 500 m, R2 rejected: R1 parts yarn 12,500 + machine 320 + labour 425, reject share 13,245, total **26,490**, **52.98/m**; R2 total 13,245 (26.49/m); order revenue 500 × 100 = 50,000, profit **23,510**. Month: invoiced 50,000 − yarn 25,000 − wages 2,500 − machine 640 − write-off (2 kg × 250) 500 = **21,360**; idle labour 850; support staff 800; 26,490 + 850 + 800 = 28,140 = 25,000 + 2,500 + 640. Cash: received 20,000, paid suppliers 40,000, paid wages 1,000, net **−21,000**; receivables 50,000 − 20,000 = **30,000**; payables 100,000 − 40,000 = **60,000**. Machines (240 shift hours in September): spinning 4 running / 236 idle, lost 236 × 20 = 4,720 kg, output 95 kg; weaving 4 / 236, lost 236 × 28 = 6,608 m, output 1,000 m; dyeing 0 running (14:00-16:00 is outside shift time) / 240 idle, lost 240 × 45 = 10,800 m, output 1,000 m.

## Review Focus (inputs the spec implies but no task would otherwise test)

1. **An order with no runs or rolls, or whose only roll is rejected:** nothing divides by zero; `cost_per_good_metre` is null and the whole cost is `unabsorbed`. Task 4 (API tests) and Task 2 (engine).
2. **Rounding:** thirds (266.666…), exact ties (0.005 rounds up), and a total equal to the sum of its rounded parts. Task 4 (`test_costing_rounding.py`).
3. **A run over a month end or a midnight shift change:** each part counts in its own month; a pay record counts in the month it is dated. Task 3.
4. **A run still open, an attendance record or a run in the future:** never costed beyond now, flagged provisional. Tasks 1, 3, 4.
5. **A month with nothing in it, a future month, a malformed month:** zeros or 422, never a crash. Task 5.

---

## File Structure

```
services/api/
  app/modules/costing/
    engine/__init__.py      the engine package (docstring only)
    engine/records.py       plain records the engine works on
    engine/intervals.py     exact time-interval maths (hours, merge, intersect, subtract, measure)
    engine/labour.py        shift windows and the labour split (spec 7.2)
    engine/runs.py          what one run costs: yarn, machine, labour (7.1)
    engine/allocation.py    runs -> rolls -> order, rejects, final/provisional (7.3)
    engine/month.py         month window, costs incurred in a month, machine hours (7.5)
    loader.py               database rows -> engine records (no arithmetic)
    service.py              rounding and response shapes: order_cost, roll_cost, roll_cost_for, month_report
    router.py               the three real handlers (examples.py is deleted in Task 5)
    schemas.py              + ProfitPanel.support_staff
  app/modules/passport/service.py   cost filled in for owner and accountant
  tests/
    costing_records.py              short builders for engine records
    costing_world.py                the hand-worked September 2026 mill, built with the factories
    test_costing_intervals.py       Task 1
    test_costing_labour.py          Task 1
    test_costing_allocation.py      Task 2
    test_costing_month.py           Task 3
    test_costing_rounding.py        Task 4
    test_costing_api.py             Task 4
    test_costing_month_api.py       Task 5
    test_costing_speed.py           Task 5
contracts/openapi.json, contracts/types.ts   regenerated once, in Task 5
docs/HRITWIK_TEAM_NOTES.md, docs/plans/README.md, this file, the spec header   synced at the end of each task
```

**Dependency order:** Task 1 → Task 2 → Task 3 (the engine, no database); Task 4 needs 1 and 2; Task 5 needs 3 and 4; Task 6 last.

**Run commands** (from the repository root): one file `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_labour.py -q`; the whole suite `cd services/api && uv run python -m pytest -p no:warnings -o addopts=`. Baseline before this work: **1,046 passed**.

---

### Task 1: Engine foundations and the labour split

**Files:**
- Create: `services/api/app/modules/costing/engine/__init__.py`, `records.py`, `intervals.py`, `labour.py`
- Create: `services/api/tests/costing_records.py`, `tests/test_costing_intervals.py`, `tests/test_costing_labour.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure Python: `datetime`, `fractions`, `zoneinfo`).
- Produces (later tasks rely on these exact names): `records.{Shift, Worker, Attendance, Machine, Run, Roll, RollRun, YarnMove, WriteOff, Downtime}`; `intervals.{Interval, hours, merge, intersect, subtract, measure, overlap_hours}`; `labour.{IST, FACTOR, shift_window(day, shift) -> (start, end), run_interval(run, now) -> (start, end), RecordSplit, Labour(.records, .uncovered, .per_run, .idle, .support, .pay), split_labour(attendance, workers: dict[int, Worker], shifts: dict[int, Shift], runs, now) -> Labour}`; test builders `costing_records.{A, B, C, SHIFTS, at, worker, present, run, machine, roll, link, issue}`.

- [ ] **Step 1: Write the test builders and the failing tests**

`services/api/tests/costing_records.py`:

```python
"""Short builders for the engine's plain records, so a test reads like the hand-worked case it asserts."""
import datetime as dt
from fractions import Fraction

from app.modules.costing.engine.labour import IST
from app.modules.costing.engine.records import (
    Attendance, Machine, Roll, RollRun, Run, Shift, Worker, YarnMove,
)

A = Shift(1, "A", dt.time(6), dt.time(14))        # 8 hours
B = Shift(2, "B", dt.time(14), dt.time(22))       # 8 hours
C = Shift(3, "C", dt.time(22), dt.time(6))        # 8 hours, crosses midnight
SHIFTS = {s.id: s for s in (A, B, C)}


def at(day: int, hour: int, minute: int = 0, month: int = 10) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, tzinfo=IST)


def worker(id: int, role: str = "operator", wage: int = 800) -> Worker:
    return Worker(id, role, Fraction(wage))


def present(worker_id: int, day: int, shift: Shift = A, status: str = "present", month: int = 10) -> Attendance:
    return Attendance(worker_id, dt.date(2026, month, day), shift.id, status)


def run(id: int, operator: int, start: dt.datetime, end: dt.datetime | None, order: int = 1, stage: str = "weaving",
        machine: int | None = 1, output_kg=None) -> Run:
    return Run(id, order, machine, stage, operator, start, end, None if output_kg is None else Fraction(output_kg))


def machine(id: int = 1, stage: str = "weaving", rate: int = 60, rated: int = 20,
            created: dt.datetime | None = None) -> Machine:
    return Machine(id, f"M-{id}", f"Machine {id}", stage, Fraction(rated), Fraction(rate), created or at(1, 0, month=9))


def roll(id: int, metres: int, rejected: bool = False, settled: bool = True, order: int = 1,
         made: dt.datetime | None = None) -> Roll:
    return Roll(id, order, Fraction(metres), rejected, settled, made or at(5, 12))


def link(roll_id: int, run_id: int, purpose: str = "produce") -> RollRun:
    return RollRun(roll_id, run_id, purpose)


def issue(run_id: int, kg: int, cost: int, when: dt.datetime | None = None) -> YarnMove:
    return YarnMove(run_id, Fraction(-kg), Fraction(cost), when or at(3, 8))
```

`services/api/tests/test_costing_intervals.py`:

```python
"""The time-interval helpers behind the shift windows and machine hours."""
import datetime as dt
from fractions import Fraction as F

from app.modules.costing.engine.intervals import hours, intersect, measure, merge, overlap_hours, subtract
from tests.costing_records import at


def test_hours_are_exact_down_to_the_microsecond():
    assert hours(dt.timedelta(hours=8)) == 8
    assert hours(dt.timedelta(minutes=20)) == F(1, 3)
    assert hours(dt.timedelta(microseconds=1)) == F(1, 3600 * 10**6)


def test_merge_joins_overlapping_and_touching_intervals_and_drops_empty_ones():
    assert merge([(at(1, 8), at(1, 10)), (at(1, 9), at(1, 12)), (at(1, 12), at(1, 13)), (at(1, 15), at(1, 15))]) \
        == [(at(1, 8), at(1, 13))]
    assert merge([(at(1, 15), at(1, 16)), (at(1, 8), at(1, 9))]) == [(at(1, 8), at(1, 9)), (at(1, 15), at(1, 16))]


def test_intersect_and_subtract():
    xs, ys = [(at(1, 8), at(1, 12)), (at(1, 14), at(1, 18))], [(at(1, 10), at(1, 15))]
    assert intersect(xs, ys) == [(at(1, 10), at(1, 12)), (at(1, 14), at(1, 15))]
    assert subtract(xs, ys) == [(at(1, 8), at(1, 10)), (at(1, 15), at(1, 18))]
    assert subtract(xs, []) == xs and subtract([], ys) == [] and intersect(xs, []) == []


def test_measure_and_overlap():
    assert measure([(at(1, 8), at(1, 10)), (at(1, 14), at(1, 15))]) == 3
    assert overlap_hours((at(1, 8), at(1, 12)), (at(1, 10), at(1, 20))) == 2
    assert overlap_hours((at(1, 8), at(1, 10)), (at(1, 10), at(1, 20))) == 0         # touching is not overlapping
```

`services/api/tests/test_costing_labour.py`:

```python
"""Spec §7.2, hand-worked: shift A is 06:00-14:00 (8 hours) and the daily wage is 800."""
from fractions import Fraction as F

from app.modules.costing.engine.labour import split_labour
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
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_intervals.py tests/test_costing_labour.py -q`
Expected: collection errors, `ModuleNotFoundError: No module named 'app.modules.costing.engine'`.

- [ ] **Step 3: Write the engine foundations**

`services/api/app/modules/costing/engine/__init__.py`:

```python
"""The costing engine: pure functions on plain records, with no database and no clock ("now" is always passed in).
All arithmetic is exact (fractions.Fraction); rounding to the paisa happens once, at the edge, in costing/service.py."""
```

`services/api/app/modules/costing/engine/records.py`:

```python
"""Plain records the engine works on. The loader (costing/loader.py) builds them from database rows."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class Shift:
    id: int
    name: str
    start: dt.time
    end: dt.time          # earlier than or equal to start means the shift crosses midnight


@dataclass(frozen=True)
class Worker:
    id: int
    role: str             # 'operator' leftovers are idle labour, every other role's are support staff
    daily_wage: Fraction


@dataclass(frozen=True)
class Attendance:
    worker_id: int
    day: dt.date          # the day the shift STARTS
    shift_id: int
    status: str           # present / half_day / absent


@dataclass(frozen=True)
class Machine:
    id: int
    code: str
    name: str
    stage: str
    rated: Fraction       # rated output per hour (kg for spinning, metres otherwise)
    rate: Fraction        # running cost per hour
    created_at: dt.datetime


@dataclass(frozen=True)
class Run:
    id: int
    order_id: int
    machine_id: int | None
    stage: str            # spinning / weaving / dyeing / rework
    operator_id: int
    start: dt.datetime
    end: dt.datetime | None
    output_kg: Fraction | None = None


@dataclass(frozen=True)
class Roll:
    id: int
    order_id: int
    metres: Fraction
    rejected: bool        # latest verdict is reject
    settled: bool         # not woven, dyeing, awaiting QC, awaiting rework or in rework
    made_at: dt.datetime


@dataclass(frozen=True)
class RollRun:
    roll_id: int
    run_id: int
    purpose: str          # produce / dye / rework


@dataclass(frozen=True)
class YarnMove:
    run_id: int
    kg: Fraction          # signed: an issue is negative, a return positive
    cost_per_kg: Fraction
    at: dt.datetime


@dataclass(frozen=True)
class WriteOff:
    kg: Fraction          # a negative stock adjustment (stored negative)
    cost_per_kg: Fraction
    at: dt.datetime


@dataclass(frozen=True)
class Downtime:
    machine_id: int
    start: dt.datetime
    end: dt.datetime | None
```

`services/api/app/modules/costing/engine/intervals.py`:

```python
"""Time intervals as (start, end) pairs of aware datetimes, measured in exact hours."""
import datetime as dt
from fractions import Fraction

Interval = tuple[dt.datetime, dt.datetime]
_MICROS_PER_HOUR = 3600 * 10**6


def hours(delta: dt.timedelta) -> Fraction:
    micros = (delta.days * 86400 + delta.seconds) * 10**6 + delta.microseconds
    return Fraction(micros, _MICROS_PER_HOUR)


def merge(intervals: list[Interval]) -> list[Interval]:
    """Sorted, with overlapping or touching intervals joined and empty ones dropped."""
    out: list[Interval] = []
    for lo, hi in sorted(i for i in intervals if i[1] > i[0]):
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def intersect(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    """Both lists must already be merged."""
    out: list[Interval] = []
    i = j = 0
    while i < len(xs) and j < len(ys):
        lo, hi = max(xs[i][0], ys[j][0]), min(xs[i][1], ys[j][1])
        if hi > lo:
            out.append((lo, hi))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    """What is in xs but not in ys. Both lists must already be merged."""
    out: list[Interval] = []
    for lo, hi in xs:
        cur = lo
        for ylo, yhi in ys:
            if yhi <= cur or ylo >= hi:
                continue
            if ylo > cur:
                out.append((cur, ylo))
            cur = max(cur, yhi)
        if cur < hi:
            out.append((cur, hi))
    return out


def measure(intervals: list[Interval]) -> Fraction:
    return sum((hours(hi - lo) for lo, hi in intervals), Fraction(0))


def overlap_hours(a: Interval, b: Interval) -> Fraction:
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    return hours(hi - lo) if hi > lo else Fraction(0)
```

`services/api/app/modules/costing/engine/labour.py`:

```python
"""Spec §7.2: split each attendance record's pay across the runs its worker operated during that shift."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction
from zoneinfo import ZoneInfo

from .intervals import Interval, hours, intersect, measure, merge, overlap_hours
from .records import Attendance, Run, Shift, Worker

IST = ZoneInfo("Asia/Kolkata")
FACTOR = {"present": Fraction(1), "half_day": Fraction(1, 2)}   # absent is skipped


def shift_window(day: dt.date, shift: Shift) -> Interval:
    """The shift on the day it starts; a shift whose end is not after its start runs into the next day."""
    start = dt.datetime.combine(day, shift.start, tzinfo=IST)
    end = dt.datetime.combine(day, shift.end, tzinfo=IST)
    if end <= start:
        end += dt.timedelta(days=1)
    return start, end


def run_interval(run: Run, now: dt.datetime) -> Interval:
    """A run still open is costed up to now (never beyond)."""
    end = run.end if run.end is not None else now
    return run.start, max(end, run.start)


@dataclass
class RecordSplit:
    day: dt.date
    worker_id: int
    pay: Fraction
    allocated: dict[int, Fraction]      # run id -> share of this record's pay
    idle: Fraction                      # leftover of an operator
    support: Fraction                   # leftover of any other role


@dataclass
class Labour:
    records: list[RecordSplit] = field(default_factory=list)
    uncovered: dict[int, Fraction] = field(default_factory=dict)   # run id -> hours no attendance covers

    @property
    def per_run(self) -> dict[int, Fraction]:
        out: dict[int, Fraction] = {}
        for rec in self.records:
            for run_id, share in rec.allocated.items():
                out[run_id] = out.get(run_id, Fraction(0)) + share
        return out

    @property
    def idle(self) -> Fraction:
        return sum((r.idle for r in self.records), Fraction(0))

    @property
    def support(self) -> Fraction:
        return sum((r.support for r in self.records), Fraction(0))

    @property
    def pay(self) -> Fraction:
        return sum((r.pay for r in self.records), Fraction(0))


def split_labour(attendance: list[Attendance], workers: dict[int, Worker], shifts: dict[int, Shift],
                 runs: list[Run], now: dt.datetime) -> Labour:
    by_operator: dict[int, list[Run]] = {}
    for run in runs:
        by_operator.setdefault(run.operator_id, []).append(run)
    labour = Labour()
    windows: dict[int, list[Interval]] = {}          # worker id -> the windows that were paid
    for rec in attendance:
        factor = FACTOR.get(rec.status)
        if factor is None:
            continue
        worker, window = workers[rec.worker_id], shift_window(rec.day, shifts[rec.shift_id])
        windows.setdefault(rec.worker_id, []).append(window)
        pay = worker.daily_wage * factor
        paid_hours = hours(window[1] - window[0]) * factor
        spent = {run.id: overlap_hours(window, run_interval(run, now)) for run in by_operator.get(worker.id, [])}
        spent = {run_id: h for run_id, h in spent.items() if h > 0}
        divisor = max(sum(spent.values(), Fraction(0)), paid_hours)
        allocated = {run_id: pay * h / divisor for run_id, h in spent.items()}
        leftover = pay - sum(allocated.values(), Fraction(0))
        is_operator = worker.role == "operator"
        labour.records.append(RecordSplit(
            day=rec.day, worker_id=worker.id, pay=pay, allocated=allocated,
            idle=leftover if is_operator else Fraction(0), support=Fraction(0) if is_operator else leftover))
    for run in runs:
        span = run_interval(run, now)
        covered = measure(intersect([span], merge(windows.get(run.operator_id, []))))
        gap = hours(span[1] - span[0]) - covered
        if gap > 0:
            labour.uncovered[run.id] = gap
    return labour
```

- [ ] **Step 4: Run them and watch them pass**

Run the same command. Expected: `16 passed` (4 interval tests, 12 labour tests).

- [ ] **Step 5: Mutation-check the labour split** (a mutation that survives means a weak test: strengthen the test, do not shrug). Apply each change in `labour.py`, run `tests/test_costing_labour.py`, expect the named failure, then revert:
  1. `divisor = max(sum(spent.values(), Fraction(0)), paid_hours)` → `divisor = sum(spent.values(), Fraction(0)) or paid_hours`: `test_half_day_pays_half_and_has_half_the_hours` or the three-looms test fails.
  2. Swap the `idle=` and `support=` expressions: `test_leftover_pay_goes_to_idle_for_an_operator...` fails.
  3. `is_operator = worker.role == "operator"` → `is_operator = True`: the same test fails.
  4. In `run_interval`, make an open run end 30 days after it starts instead of at `now`: `test_a_run_still_open_is_costed_up_to_now` fails.
  5. `"half_day": Fraction(1, 2)` → `Fraction(1)`: `test_half_day_pays_half...` fails.
  6. `if gap > 0:` → `if False:`: the shift-change and absent tests (which expect `uncovered`) fail.

- [ ] **Step 6: Full suite twice**

Run the whole suite twice. Expected both times: **1,062 passed** (1,046 + 16).

- [ ] **Step 7: Sync and commit.** Append a `Task 1 done and verified (<live date and time>): ...` line to this plan's Status section (numbers, mutations, suite count); edit the `Last updated` header; commit.

```bash
git add services/api/app/modules/costing/engine services/api/tests/costing_records.py services/api/tests/test_costing_intervals.py services/api/tests/test_costing_labour.py docs/plans/B6-costing.md
git commit -m "Add the costing engine's time maths and the shift-wage split"
```

---

### Task 2: Run costs and the hand-over from runs to rolls and orders

**Files:**
- Create: `services/api/app/modules/costing/engine/runs.py`, `allocation.py`
- Test: `services/api/tests/test_costing_allocation.py`

**Interfaces:**
- Consumes (Task 1): `records.{Run, Machine, YarnMove, Roll, RollRun}`, `labour.run_interval`, `intervals.hours`.
- Produces: `runs.{RunCost(yarn, machine, labour, hours; .total), run_costs(runs, machines: dict[int, Machine], moves, labour_per_run: dict[int, Fraction], now) -> dict[int, RunCost]}`; `allocation.{PARTS, RollResult(roll_id, metres, rejected, parts, reject_share; .own_total, .total, .per_metre), OrderResult(parts, rolls, reject_cost, good_metres, rejected_metres; .total, .cost_per_good_metre, .unabsorbed), allocate_order(runs, rolls, roll_runs, costs) -> OrderResult, is_final(runs, rolls, good_metres, ordered_metres, cancelled) -> bool}`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_costing_allocation.py`:

```python
"""Spec §7.1 and §7.3, hand-worked: rolls R1 1,000 m, R2 600 m, R3 400 m (rejected)."""
from fractions import Fraction as F

from app.modules.costing.engine.allocation import allocate_order, is_final
from app.modules.costing.engine.records import YarnMove
from app.modules.costing.engine.runs import RunCost, run_costs
from tests.costing_records import at, issue, link, machine, roll, run

R = lambda id, **kw: run(id, 1, at(3, 6), at(3, 10), **kw)       # noqa: E731


def cost(yarn=0, machine=0, labour=0):
    return RunCost(F(yarn), F(machine), F(labour), F(0))


def test_the_worked_order_gives_17_50_and_18_33_a_metre():
    spin, weave, dye_run, mend = R(1, stage="spinning"), R(2), R(3, stage="dyeing"), R(4, stage="rework", machine=None)
    rolls = [roll(1, 1000), roll(2, 600), roll(3, 400, rejected=True)]
    links = [link(r, 2) for r in (1, 2, 3)] + [link(r, 3, "dye") for r in (1, 2, 3)] + [link(2, 4, "rework")]
    costs = {1: cost(15000, 3000, 2000), 2: cost(0, 4000, 2000), 3: cost(0, 1500, 500), 4: cost(0, 300, 200)}
    result = allocate_order([spin, weave, dye_run, mend], rolls, links, costs)
    assert result.total == 28500 and result.good_metres == 1600 and result.rejected_metres == 400
    assert result.reject_cost == 5600 and result.unabsorbed == 0
    r1, r2, r3 = (result.rolls[i] for i in (1, 2, 3))
    assert (r1.own_total, r2.own_total, r3.own_total) == (14000, 8900, 5600)
    assert (r1.reject_share, r2.reject_share, r3.reject_share) == (3500, 2100, 0)
    assert (r1.total, r2.total) == (17500, 11000) and r1.per_metre == F("17.5") and round(float(r2.per_metre), 2) == 18.33
    assert r1.total + r2.total == result.total                       # the good rolls carry the whole order
    assert result.cost_per_good_metre == F(28500, 1600) == F("17.8125")
    assert result.parts["rework"] == 500                             # the rework run is its own part
    assert r2.parts["rework"] == 500 and r1.parts["rework"] == 0


def test_a_run_with_no_rolls_goes_into_the_pool_and_is_spread_by_metres():
    broken = R(1, stage="weaving")                                   # a loom that broke before making a roll
    result = allocate_order([broken], [roll(1, 300), roll(2, 100)], [], {1: cost(machine=400)})
    assert result.rolls[1].parts["machine"] == 300 and result.rolls[2].parts["machine"] == 100


def test_no_good_roll_means_everything_is_unabsorbed_and_there_is_no_cost_per_metre():
    result = allocate_order([R(1, stage="spinning")], [roll(1, 500, rejected=True)], [], {1: cost(yarn=1000)})
    assert result.good_metres == 0 and result.cost_per_good_metre is None and result.unabsorbed == 1000
    nothing_woven = allocate_order([R(1, stage="spinning")], [], [], {1: cost(yarn=1000)})
    assert nothing_woven.total == 1000 and nothing_woven.unabsorbed == 1000 and nothing_woven.rolls == {}


def test_a_roll_dyed_in_two_runs_takes_a_share_of_each():
    first, second = R(1, stage="dyeing"), R(2, stage="dyeing")
    links = [link(1, 1, "dye"), link(2, 1, "dye"), link(1, 2, "dye")]
    result = allocate_order([first, second], [roll(1, 100), roll(2, 100)], links, {1: cost(machine=200), 2: cost(machine=50)})
    assert result.rolls[1].parts["machine"] == 150 and result.rolls[2].parts["machine"] == 100


def test_a_hand_mended_rework_costs_only_labour_and_lands_on_its_roll():
    mend = R(1, stage="rework", machine=None)
    result = allocate_order([mend], [roll(1, 100), roll(2, 100)], [link(2, 1, "rework")], {1: cost(labour=80)})
    assert result.rolls[2].parts["rework"] == 80 and result.rolls[1].parts["rework"] == 0


def test_each_final_condition_alone_keeps_the_cost_provisional():
    done, rolls = [R(1)], [roll(1, 1000)]
    assert is_final(done, rolls, F(1000), F(1000), cancelled=False)
    assert not is_final([R(1), run(2, 1, at(4, 6), None)], rolls, F(1000), F(1000), False)     # a run still open
    assert not is_final(done, [roll(1, 1000, settled=False)], F(1000), F(1000), False)         # a roll in flight
    assert not is_final(done, rolls, F(1000), F(1500), False)                                  # more metres to come
    assert is_final(done, rolls, F(1000), F(1500), cancelled=True)                             # ...unless cancelled


def test_run_costs_use_the_machine_rate_the_lot_cost_and_the_operators_share():
    spin = run(1, 1, at(3, 6), at(3, 10), stage="spinning", machine=1)
    moves = [issue(1, 120, 250), YarnMove(1, F(20), F(250), at(4, 9))]      # 120 kg issued, 20 kg returned
    costs = run_costs([spin], {1: machine(1, "spinning", rate=55)}, moves, {1: F(400)}, at(30, 12))
    assert (costs[1].yarn, costs[1].machine, costs[1].labour, costs[1].hours) == (25000, 220, 400, 4)


def test_property_the_good_rolls_always_carry_exactly_the_order_total():
    import random
    rng = random.Random(6)
    for _ in range(300):
        n = rng.randint(1, 5)
        rolls = [roll(i, rng.randint(50, 900), rejected=rng.random() < 0.3) for i in range(1, n + 1)]
        runs = [R(i, stage=rng.choice(["spinning", "weaving", "dyeing", "rework"]), machine=None if i % 4 == 0 else 1) for i in range(1, 7)]
        links = [link(rl.id, r.id, "produce") for r in runs for rl in rolls if rng.random() < 0.4]
        costs = {r.id: cost(rng.randint(0, 5000), rng.randint(0, 5000), rng.randint(0, 5000)) for r in runs}
        result = allocate_order(runs, rolls, links, costs)
        assert sum(result.parts.values()) == sum(c.total for c in costs.values())
        if result.good_metres > 0:
            assert sum(rr.total for rr in result.rolls.values() if not rr.rejected) == result.total
        else:
            assert result.unabsorbed == result.total
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_allocation.py -q`
Expected: `ModuleNotFoundError: No module named 'app.modules.costing.engine.allocation'`.

- [ ] **Step 3: Write `runs.py` and `allocation.py`**

`services/api/app/modules/costing/engine/runs.py`:

```python
"""Spec §7.1: what one run costs: yarn, machine and labour."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction

from .intervals import hours
from .labour import run_interval
from .records import Machine, Run, YarnMove


@dataclass
class RunCost:
    yarn: Fraction
    machine: Fraction
    labour: Fraction
    hours: Fraction

    @property
    def total(self) -> Fraction:
        return self.yarn + self.machine + self.labour


def run_costs(runs: list[Run], machines: dict[int, Machine], moves: list[YarnMove],
              labour_per_run: dict[int, Fraction], now: dt.datetime) -> dict[int, RunCost]:
    """Yarn: kg issued minus kg returned times the lot's cost per kg (an issue is stored negative).
    Machine: hours times the machine's rate; a run with no machine (hand mending) costs 0 here."""
    yarn: dict[int, Fraction] = {}
    for move in moves:
        yarn[move.run_id] = yarn.get(move.run_id, Fraction(0)) - move.kg * move.cost_per_kg
    out: dict[int, RunCost] = {}
    for run in runs:
        lo, hi = run_interval(run, now)
        h = hours(hi - lo)
        machine = machines[run.machine_id] if run.machine_id is not None else None
        out[run.id] = RunCost(
            yarn=yarn.get(run.id, Fraction(0)), machine=h * machine.rate if machine else Fraction(0),
            labour=labour_per_run.get(run.id, Fraction(0)), hours=h)
    return out
```

`services/api/app/modules/costing/engine/allocation.py`:

```python
"""Spec §7.3: hand each run's cost to the rolls it touched, spread the order pool, move rejected rolls' cost onto good rolls."""
from dataclasses import dataclass, field
from fractions import Fraction

from .records import Roll, RollRun, Run
from .runs import RunCost

PARTS = ("yarn", "machine", "labour", "rework")


def _zero() -> dict[str, Fraction]:
    return {p: Fraction(0) for p in PARTS}


@dataclass
class RollResult:
    roll_id: int
    metres: Fraction
    rejected: bool
    parts: dict[str, Fraction]          # its own runs plus its share of the order pool (before any reject share)
    reject_share: Fraction = Fraction(0)

    @property
    def own_total(self) -> Fraction:
        return sum(self.parts.values(), Fraction(0))

    @property
    def total(self) -> Fraction:
        return self.own_total + self.reject_share

    @property
    def per_metre(self) -> Fraction:
        return self.total / self.metres


@dataclass
class OrderResult:
    parts: dict[str, Fraction] = field(default_factory=_zero)
    rolls: dict[int, RollResult] = field(default_factory=dict)
    reject_cost: Fraction = Fraction(0)
    good_metres: Fraction = Fraction(0)
    rejected_metres: Fraction = Fraction(0)

    @property
    def total(self) -> Fraction:
        return sum(self.parts.values(), Fraction(0))

    @property
    def cost_per_good_metre(self) -> Fraction | None:
        return self.total / self.good_metres if self.good_metres > 0 else None

    @property
    def unabsorbed(self) -> Fraction:
        """Cost that no good roll carries yet: everything, while the order has no non-rejected roll."""
        return self.total if self.good_metres == 0 else Fraction(0)


def _split(amounts: dict[str, Fraction], metres: dict[int, Fraction]) -> dict[int, dict[str, Fraction]]:
    whole = sum(metres.values(), Fraction(0))
    return {rid: {p: a * m / whole for p, a in amounts.items()} for rid, m in metres.items()}


def _add(into: dict[str, Fraction], amounts: dict[str, Fraction]) -> None:
    for part, amount in amounts.items():
        into[part] += amount


def allocate_order(runs: list[Run], rolls: list[Roll], roll_runs: list[RollRun],
                   costs: dict[int, RunCost]) -> OrderResult:
    """`runs`, `rolls` and `roll_runs` are all of ONE order. A run's yarn, machine and labour go to its rolls by
    metres (a rework run's whole cost is the 'rework' part); a run with no rolls goes into the pool, which is spread
    over all the order's rolls by metres. Then the rejected rolls' own totals are spread over the good rolls."""
    result = OrderResult()
    by_id = {r.id: r for r in rolls}
    result.rolls = {r.id: RollResult(r.id, r.metres, r.rejected, _zero()) for r in rolls}
    rolls_of_run: dict[int, dict[int, Fraction]] = {}
    for link in roll_runs:
        if link.roll_id in by_id:
            rolls_of_run.setdefault(link.run_id, {})[link.roll_id] = by_id[link.roll_id].metres
    pool = _zero()
    for run in runs:
        cost = costs[run.id]
        if run.stage == "rework":
            amounts = {**_zero(), "rework": cost.total}
        else:
            amounts = {**_zero(), "yarn": cost.yarn, "machine": cost.machine, "labour": cost.labour}
        _add(result.parts, amounts)
        own = rolls_of_run.get(run.id)
        if own:
            for rid, share in _split(amounts, own).items():
                _add(result.rolls[rid].parts, share)
        else:
            _add(pool, amounts)
    if rolls:
        for rid, share in _split(pool, {r.id: r.metres for r in rolls}).items():
            _add(result.rolls[rid].parts, share)
    good = {r.id: r.metres for r in rolls if not r.rejected}
    result.good_metres = sum(good.values(), Fraction(0))
    result.rejected_metres = sum((r.metres for r in rolls if r.rejected), Fraction(0))
    result.reject_cost = sum((result.rolls[r.id].own_total for r in rolls if r.rejected), Fraction(0))
    if good:
        for rid, share in _split({"x": result.reject_cost}, good).items():
            result.rolls[rid].reject_share = share["x"]
    return result


def is_final(runs: list[Run], rolls: list[Roll], good_metres: Fraction, ordered_metres: Fraction,
             cancelled: bool) -> bool:
    """No run open, every roll settled, and no more rolls coming (the ordered metres are woven, or the order is cancelled)."""
    return (all(r.end is not None for r in runs) and all(r.settled for r in rolls)
            and (cancelled or good_metres >= ordered_metres))
```

- [ ] **Step 4: Run and watch them pass.** Expected: `8 passed`.

- [ ] **Step 5: Mutation-check** (`allocation.py` / `runs.py`; revert after each):
  1. Delete the line `result.rolls[rid].reject_share = share["x"]` (replace with `pass`): `test_the_worked_order_gives_17_50_and_18_33_a_metre` fails.
  2. Replace `_add(pool, amounts)` (in the `else` branch) with `pass`: `test_a_run_with_no_rolls_goes_into_the_pool...` fails.
  3. Change `if rolls:` (before the pool is spread) to `if False:`: the worked-order test and the property test fail.
  4. In `is_final`, delete `all(r.end is not None for r in runs) and `: `test_each_final_condition_alone_keeps_the_cost_provisional` fails.
  5. In `run_costs`, change the yarn line to add `abs(move.kg) * move.cost_per_kg` instead of subtracting `move.kg * ...`: `test_run_costs_use_the_machine_rate...` fails (a return would be added, not netted).

- [ ] **Step 6: Full suite twice.** Expected both times: **1,070 passed**.

- [ ] **Step 7: Sync and commit** (Status line, header, then):

```bash
git add services/api/app/modules/costing/engine services/api/tests/test_costing_allocation.py docs/plans/B6-costing.md
git commit -m "Add run costs and the hand-over of cost to rolls and orders"
```

---

### Task 3: The month: costs incurred in it, and machine hours

**Files:**
- Create: `services/api/app/modules/costing/engine/month.py`
- Test: `services/api/tests/test_costing_month.py`

**Interfaces:**
- Consumes (Tasks 1-2): `labour.{IST, Labour, run_interval, shift_window}`, `intervals.*`, `records.*`.
- Produces: `month.{month_window(year, month) -> (first_day, first_of_next, (start_instant, end_instant)), MonthCosts(per_order: dict[int, dict[str, Fraction]], yarn, machine, wages, idle, support, writeoffs; .order_total), month_costs(first, after, span, runs, machines, moves, writeoffs, labour, now) -> MonthCosts, MachineHours(running, idle, down, output), shift_time(shifts, span), machine_hours(machine, runs, downtimes, rolls, roll_runs, shifts: list[Shift], span, now) -> MachineHours}`. In `month_costs` the keys of `per_order[order_id]` are `"yarn"`, `"machine"`, `"labour"`.

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_costing_month.py`:

```python
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
```

- [ ] **Step 2: Run and watch them fail** (`ModuleNotFoundError: ...engine.month`).

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_month.py -q`

- [ ] **Step 3: Write `month.py`**

`services/api/app/modules/costing/engine/month.py`:

```python
"""Spec §7.5: what was incurred inside one month, and how each machine's hours were spent."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction

from .intervals import Interval, hours, intersect, measure, merge, subtract
from .labour import IST, Labour, run_interval, shift_window
from .records import Downtime, Machine, Roll, RollRun, Run, Shift, WriteOff, YarnMove


def month_window(year: int, month: int) -> tuple[dt.date, dt.date, Interval]:
    """First day, first day of the next month, and the instants 00:00 IST to 00:00 IST."""
    first = dt.date(year, month, 1)
    after = dt.date(year + (month == 12), month % 12 + 1, 1)
    return first, after, (dt.datetime.combine(first, dt.time(), tzinfo=IST), dt.datetime.combine(after, dt.time(), tzinfo=IST))


@dataclass
class MonthCosts:
    per_order: dict[int, dict[str, Fraction]] = field(default_factory=dict)   # order id -> yarn / machine / labour
    yarn: Fraction = Fraction(0)
    machine: Fraction = Fraction(0)
    wages: Fraction = Fraction(0)       # pay of the attendance records dated in the month
    idle: Fraction = Fraction(0)
    support: Fraction = Fraction(0)
    writeoffs: Fraction = Fraction(0)

    @property
    def order_total(self) -> Fraction:
        return sum((sum(p.values(), Fraction(0)) for p in self.per_order.values()), Fraction(0))


def month_costs(first: dt.date, after: dt.date, span: Interval, runs: list[Run], machines: dict[int, Machine],
                moves: list[YarnMove], writeoffs: list[WriteOff], labour: Labour, now: dt.datetime) -> MonthCosts:
    out = MonthCosts()
    order_of = {r.id: r.order_id for r in runs}

    def bucket(order_id: int) -> dict[str, Fraction]:
        return out.per_order.setdefault(order_id, {"yarn": Fraction(0), "machine": Fraction(0), "labour": Fraction(0)})

    for move in moves:
        if span[0] <= move.at < span[1]:
            amount = -move.kg * move.cost_per_kg
            bucket(order_of[move.run_id])["yarn"] += amount
            out.yarn += amount
    for run in runs:
        if run.machine_id is None:
            continue
        lo, hi = run_interval(run, now)
        lo, hi = max(lo, span[0]), min(hi, span[1])
        if hi > lo:
            amount = hours(hi - lo) * machines[run.machine_id].rate
            bucket(run.order_id)["machine"] += amount
            out.machine += amount
    for rec in labour.records:
        if first <= rec.day < after:
            out.wages += rec.pay
            out.idle += rec.idle
            out.support += rec.support
            for run_id, share in rec.allocated.items():
                bucket(order_of[run_id])["labour"] += share
    for off in writeoffs:
        if span[0] <= off.at < span[1]:
            out.writeoffs += -off.kg * off.cost_per_kg
    return out


@dataclass
class MachineHours:
    running: Fraction
    idle: Fraction
    down: Fraction
    output: Fraction


def shift_time(shifts: list[Shift], span: Interval) -> list[Interval]:
    """Every shift window that touches the span, joined together, then cut to the span."""
    day = span[0].astimezone(IST).date() - dt.timedelta(days=1)
    last = span[1].astimezone(IST).date()
    windows = []
    while day <= last:
        windows += [shift_window(day, s) for s in shifts]
        day += dt.timedelta(days=1)
    return intersect(merge(windows), [span])


def machine_hours(machine: Machine, runs: list[Run], downtimes: list[Downtime], rolls: list[Roll],
                  roll_runs: list[RollRun], shifts: list[Shift], span: Interval, now: dt.datetime) -> MachineHours:
    """Hours inside shift time, from the month's start (or the machine's creation) to the month's end (or now)."""
    lo, hi = max(span[0], machine.created_at), min(span[1], now)
    if hi <= lo:
        return MachineHours(Fraction(0), Fraction(0), Fraction(0), Fraction(0))
    allowed = shift_time(shifts, (lo, hi))
    mine = [r for r in runs if r.machine_id == machine.id]
    down = intersect(merge([(d.start, d.end if d.end is not None else now) for d in downtimes
                            if d.machine_id == machine.id]), allowed)
    busy = intersect(merge([run_interval(r, now) for r in mine]), allowed)
    running = subtract(busy, down)
    total, d, r = measure(allowed), measure(down), measure(running)
    return MachineHours(running=r, idle=total - d - r, down=d, output=_output(machine, mine, rolls, roll_runs, (lo, hi)))


def _output(machine: Machine, mine: list[Run], rolls: list[Roll], roll_runs: list[RollRun],
            span: Interval) -> Fraction:
    """Spinning: kg of runs that ended in the span. Weaving: metres of rolls made in it.
    Dyeing: metres of rolls in dye runs that ended in it."""
    def inside(moment: dt.datetime | None) -> bool:
        return moment is not None and span[0] <= moment < span[1]

    if machine.stage == "spinning":
        return sum((r.output_kg or Fraction(0) for r in mine if inside(r.end)), Fraction(0))
    by_run = {r.id: r for r in mine}
    by_roll = {r.id: r for r in rolls}
    total = Fraction(0)
    for link in roll_runs:
        run, roll = by_run.get(link.run_id), by_roll.get(link.roll_id)
        if run is None or roll is None:
            continue
        if machine.stage == "weaving" and link.purpose == "produce" and inside(roll.made_at):
            total += roll.metres
        elif machine.stage == "dyeing" and link.purpose == "dye" and inside(run.end):
            total += roll.metres
    return total
```

- [ ] **Step 4: Run and watch them pass.** Expected: `12 passed`.

- [ ] **Step 5: Mutation-check** (`month.py`; revert after each). The first four **survived** in the scratch run until the tests named below were added, so check them especially:
  1. `if first <= rec.day < after:` → `if True:`: `test_pay_records_dated_outside_the_month_are_left_out` fails.
  2. `if span[0] <= off.at < span[1]:` → `if True:`: `test_yarn_issues_and_write_offs_outside_the_month_are_left_out` fails.
  3. `if span[0] <= move.at < span[1]:` → `if True:`: the same test fails.
  4. `running = subtract(busy, down)` → `running = busy`: `test_hours_are_never_counted_twice_if_a_run_and_a_downtime_overlap` fails.
  5. Delete `lo, hi = max(lo, span[0]), min(hi, span[1])` (in `month_costs`): `test_a_run_over_the_month_end_counts_each_part_in_its_own_month` fails.
  6. `lo, hi = max(span[0], machine.created_at), min(span[1], now)` → `lo, hi = span[0], min(span[1], now)`: `test_a_machine_is_counted_only_from_the_day_it_was_created` fails.
  7. `allowed = shift_time(shifts, (lo, hi))` → `allowed = [(lo, hi)]`: `test_an_open_downtime_runs_up_to_now_and_hours_outside_shift_time_are_ignored` fails.

- [ ] **Step 6: Full suite twice.** Expected both times: **1,082 passed**.

- [ ] **Step 7: Sync and commit** (Status line, header, then):

```bash
git add services/api/app/modules/costing/engine/month.py services/api/tests/test_costing_month.py docs/plans/B6-costing.md
git commit -m "Add the month's costs and the machine hours to the costing engine"
```

---

### Task 4: Roll and order cost through the API, and the passport

**Files:**
- Create: `services/api/app/modules/costing/loader.py`, `services/api/app/modules/costing/service.py`
- Modify: `services/api/app/modules/costing/router.py`, `services/api/app/modules/passport/service.py`
- Test: create `services/api/tests/costing_world.py`, `tests/test_costing_rounding.py`, `tests/test_costing_api.py`; fix any old test that asserted the example roll or order cost (`grep -rn "costing\|reports/month" services/api/tests | grep -v "test_costing"`)

**Interfaces:**
- Consumes (Tasks 1-2): `split_labour`, `run_costs`, `allocate_order`, `is_final`, `PARTS`, `OrderResult`, `Labour`; existing `floor.service.db_now`, `orders.service.get_order_or_404`, `rolls.service.{get_roll_or_404, v_roll_status}`, `core.money.{q_money, q_kg, to_float}`, `core.clock.IST`.
- Produces: `loader.{Bundle, load_order(db, order, now), load_month(db, first, after, span, now)}` (both loaders are written now so Task 5 only adds the month service); `service.{FINANCE, exact, money, two_places, order_cost(db, order_code) -> OrderCost, roll_cost_for(db, roll, now=None) -> RollCost, roll_cost(db, roll_code) -> RollCost}`. The month route keeps answering with example data until Task 5.

- [ ] **Step 1: Write the test world and the failing tests**

`services/api/tests/costing_world.py`:

```python
"""A small September 2026 mill with every figure worked out by hand (docs/plans/B6-costing.md, 'Hand-worked numbers').
All dates are IST and in the past, so the results do not depend on when the test runs."""
import datetime as dt
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models import (
    Attendance, BuyerPayment, Invoice, InvoiceLine, SupplierBill, SupplierPayment, WagePayment, YarnMovement,
)
from tests.factories import (
    dye, make_buyer, make_dispatch, make_inspection, make_lot, make_machine, make_order, make_roll, make_run,
    make_shift, make_user, make_worker, put_on_dispatch,
)

IST = ZoneInfo("Asia/Kolkata")


def at(day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 9, day, hour, minute, tzinfo=IST)


@dataclass
class World:
    order: object
    buyer: object
    r1: object                  # 500 m, passed
    r2: object                  # 500 m, rejected
    runs: dict = field(default_factory=dict)
    machines: dict = field(default_factory=dict)
    workers: dict = field(default_factory=dict)
    invoice: object = None
    bill: object = None


def build_world(db) -> World:
    marker = make_user(db, role="supervisor")
    shift = make_shift(db, name="A")                               # 06:00-14:00, the only shift
    ravi = make_worker(db, role="operator", daily_wage=800)
    suresh = make_worker(db, role="operator", daily_wage=900)
    lakshmi = make_worker(db, role="operator", daily_wage=800)     # runs the dye machine; no attendance is marked
    kiran = make_worker(db, role="storekeeper", daily_wage=800)
    created = at(1, 0)
    spinner = make_machine(db, stage="spinning", running_cost_per_hour=55, rated_output_per_hour=20, created_at=created)
    loom = make_machine(db, stage="weaving", running_cost_per_hour=60, rated_output_per_hour=28, created_at=created)
    dyer = make_machine(db, stage="dyeing", running_cost_per_hour=90, rated_output_per_hour=45, created_at=created)
    buyer = make_buyer(db, name="Sharma Fabrics")
    order = make_order(db, buyer=buyer, qty_metres=500, price_per_metre=100)
    lot = make_lot(db, qty_kg=400, cost_per_kg=250)
    bill = db.scalar(select(SupplierBill).where(SupplierBill.yarn_lot_id == lot.id))
    bill.bill_date, bill.due_date = dt.date(2026, 9, 1), dt.date(2026, 9, 30)

    spin = make_run(db, order, spinner, ravi, started_at=at(3, 6), ended_at=at(3, 10), output_kg=95)
    weave = make_run(db, order, loom, suresh, input_run_id=spin.id, started_at=at(3, 10), ended_at=at(3, 14))
    dyeing = make_run(db, order, dyer, lakshmi, started_at=at(3, 14), ended_at=at(3, 16))
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-100, production_run_id=spin.id, moved_by=marker.id,
                        created_at=at(3, 8)))
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="adjustment", qty_kg=-2, note="count", moved_by=marker.id,
                        created_at=at(12, 10)))
    r1, r2 = make_roll(db, order, weave, 500), make_roll(db, order, weave, 500)
    r1.created_at = r2.created_at = at(3, 13)
    dye(db, r1, dyeing)
    dye(db, r2, dyeing)
    make_inspection(db, r1, "pass", inspected_at=at(4, 9))
    make_inspection(db, r2, "reject", inspected_at=at(4, 9))
    for person in (ravi, suresh, kiran):
        db.add(Attendance(worker_id=person.id, work_date=dt.date(2026, 9, 3), shift_id=shift.id, status="present",
                          marked_by=marker.id))

    dispatch = make_dispatch(db, buyer, state="dispatched", dispatched_at=at(20, 11))
    put_on_dispatch(db, r1, dispatch)
    invoice = Invoice(invoice_no="INV-0001", dispatch_id=dispatch.id, buyer_id=buyer.id, issued_at=at(20, 11),
                      total_amount=50000)
    invoice.lines.append(InvoiceLine(order_id=order.id, metres=500, rate=100, amount=50000))
    db.add(invoice)
    db.flush()
    db.add(BuyerPayment(invoice_id=invoice.id, amount=20000, received_at=dt.date(2026, 9, 22)))
    db.add(SupplierPayment(bill_id=bill.id, amount=40000, paid_at=dt.date(2026, 9, 5)))
    db.add(WagePayment(worker_id=ravi.id, period_start=dt.date(2026, 9, 1), period_end=dt.date(2026, 9, 30),
                       amount=1000, paid_at=dt.date(2026, 9, 25)))
    db.flush()
    return World(order, buyer, r1, r2, {"spin": spin, "weave": weave, "dye": dyeing},
                 {"spin": spinner, "loom": loom, "dye": dyer}, {"ravi": ravi, "suresh": suresh, "lakshmi": lakshmi}, invoice, bill)
```

`services/api/tests/test_costing_rounding.py`:

```python
"""Rounding at the edge: the engine is exact, the response is rounded half up to the paisa."""
from decimal import Decimal
from fractions import Fraction as F

from app.modules.costing.service import money, two_places


def test_money_rounds_half_up_to_the_paisa():
    assert money(F(1, 200)) == Decimal("0.01")                       # exactly half a paisa goes up
    assert money(F(1, 3)) == Decimal("0.33") and money(F(2, 3)) == Decimal("0.67")
    assert money(F(800, 3)) == Decimal("266.67") and money(F(0)) == 0
    assert money(F(-1, 200)) == Decimal("-0.01")


def test_a_total_is_the_sum_of_its_rounded_parts_which_is_why_it_can_differ_from_the_rounded_exact_total():
    third = money(F(800, 3))
    assert third * 3 == Decimal("800.01")                            # three rounded thirds are a paisa over 800
    assert money(F(800)) == Decimal("800.00")


def test_hours_and_quantities_show_two_places():
    assert two_places(F(1, 3)) == 0.33 and two_places(F(5, 3)) == 1.67 and two_places(F(1, 200)) == 0.01
```

`services/api/tests/test_costing_api.py`:

```python
"""B6: the costing endpoints on a hand-worked September 2026 mill (tests/costing_world.py).

Hand-worked (see docs/plans/B6-costing.md):
  yarn 100 kg x 250 = 25,000 | machine 4 h x 55 + 4 h x 60 + 2 h x 90 = 640 | labour: Ravi 400 + Suresh 450 = 850
  order cost 26,490; two rolls of 500 m, R2 rejected, so R1 carries all of it: 26,490 / 500 = 52.98 a metre."""
import datetime as dt

import pytest
from app.core.auth import COOKIE_NAME, create_token
from app.db.models import Attendance
from tests.costing_world import at, build_world
from tests.factories import (
    make_inspection, make_machine, make_order, make_roll, make_run, make_shift, make_user, make_worker,
)


@pytest.fixture
def world(db):
    return build_world(db)


def test_a_rolls_cost_carries_the_rejected_rolls_cost(client, login_as, world):
    login_as("owner")
    r1 = client.get(f"/api/costing/rolls/{world.r1.code}")
    assert r1.status_code == 200
    assert r1.json() == {
        "roll_code": world.r1.code, "parts": {"yarn": 12500.0, "machine": 320.0, "labour": 425.0, "rework": 0.0},
        "reject_share": 13245.0, "total": 26490.0, "per_metre": 52.98, "provisional": False,
    }
    r2 = client.get(f"/api/costing/rolls/{world.r2.code}").json()
    assert (r2["reject_share"], r2["total"], r2["per_metre"]) == (0.0, 13245.0, 26.49)


def test_an_orders_cost_breakdown(client, login_as, world):
    login_as("accountant")
    body = client.get(f"/api/costing/orders/{world.order.code}").json()
    assert body["parts"] == {"yarn": 25000.0, "machine": 640.0, "labour": 850.0, "rework": 0.0}
    assert (body["total"], body["reject_cost"], body["good_metres"], body["rejected_metres"]) == (26490.0, 13245.0, 500.0, 500.0)
    assert (body["cost_per_good_metre"], body["revenue"], body["profit"], body["unabsorbed"]) == (52.98, 50000.0, 23510.0, 0.0)
    assert body["provisional"] is False
    dye_run, dyer = world.runs["dye"], world.machines["dye"]
    assert body["warnings"] == [
        f"Run {dye_run.id} ({dyer.code}, 2026-09-03) has 2.0 hours not covered by its operator's attendance"]


def test_the_cost_is_provisional_while_a_run_is_still_open(client, login_as, db, world):
    make_run(db, world.order, world.machines["dye"], world.workers["lakshmi"], started_at=at(5, 6))
    login_as("owner")
    body = client.get(f"/api/costing/orders/{world.order.code}").json()
    assert body["provisional"] is True
    assert any("is still open" in w for w in body["warnings"])
    assert client.get(f"/api/costing/rolls/{world.r1.code}").json()["provisional"] is True


def test_unknown_roll_and_order_are_404(client, login_as, world):
    login_as("owner")
    assert client.get("/api/costing/rolls/R-9999").status_code == 404
    assert client.get("/api/costing/orders/ORD-9999").status_code == 404


@pytest.mark.parametrize("role", ["store", "supervisor", "qc", "dispatch", "buyer"])
def test_only_owner_and_accountant_may_read_cost(client, login_as, world, role):
    login_as(role)
    for path in (f"/api/costing/rolls/{world.r1.code}", f"/api/costing/orders/{world.order.code}", "/api/reports/month?month=2026-09"):
        assert client.get(path).status_code == 403


def test_the_passport_shows_cost_to_owner_and_accountant_only(client, login_as, db, world):
    for role in ("owner", "accountant"):
        login_as(role)
        assert client.get(f"/api/rolls/{world.r1.code}/passport").json()["cost"]["total"] == 26490.0
    for role in ("store", "supervisor", "qc", "dispatch"):
        login_as(role)
        assert client.get(f"/api/rolls/{world.r1.code}/passport").json()["cost"] is None


def test_a_buyer_never_sees_any_cost_even_for_their_own_roll(client, db, world):
    buyer = make_user(db, role="buyer", buyer_id=world.buyer.id)
    client.cookies.set(COOKIE_NAME, create_token(buyer.id))
    response = client.get(f"/api/rolls/{world.r1.code}/passport")
    assert response.status_code == 200 and response.json()["cost"] is None
    for giveaway in ("per_metre", "reject_share", "parts", "machine", "labour", "yarn"):
        assert giveaway not in response.text




def test_an_order_with_no_runs_and_no_rolls_costs_nothing_and_divides_by_nothing(client, login_as, db):
    order = make_order(db, qty_metres=300, price_per_metre=100)
    login_as("owner")
    body = client.get(f"/api/costing/orders/{order.code}").json()
    assert body["parts"] == {"yarn": 0.0, "machine": 0.0, "labour": 0.0, "rework": 0.0}
    assert (body["total"], body["good_metres"], body["cost_per_good_metre"], body["revenue"], body["profit"]) \
        == (0.0, 0.0, None, 0.0, 0.0)
    assert body["provisional"] is True and body["warnings"] == []


def test_an_order_whose_only_roll_is_rejected_shows_everything_as_unabsorbed(client, login_as, db):
    order = make_order(db, qty_metres=100)
    weave = make_run(db, order, make_machine(db, stage="weaving", running_cost_per_hour=60),
                     started_at=at(3, 10), ended_at=at(3, 12))
    roll = make_roll(db, order, weave, 100)
    make_inspection(db, roll, "reject")
    login_as("owner")
    body = client.get(f"/api/costing/orders/{order.code}").json()
    assert (body["total"], body["cost_per_good_metre"], body["unabsorbed"], body["reject_cost"]) == (120.0, None, 120.0, 120.0)
    assert client.get(f"/api/costing/rolls/{roll.code}").json()["per_metre"] == 1.2          # its own cost, 120 / 100 m


def test_a_workers_pay_is_shared_across_the_runs_of_different_orders(client, login_as, db):
    """One weaver minds two looms for 8 hours each, on two different orders: H = 16 against 8 paid hours, so each run
    gets 800 x 8/16 = 400. An order costed on its own would see only 8 hours and charge itself the whole 800."""
    shift = make_shift(db, name="A")
    marker = make_user(db, role="supervisor")
    weaver = make_worker(db, role="operator", daily_wage=800)
    db.add(Attendance(worker_id=weaver.id, work_date=dt.date(2026, 9, 3), shift_id=shift.id, status="present",
                      marked_by=marker.id))
    orders = [make_order(db), make_order(db)]
    for order in orders:
        make_run(db, order, make_machine(db, stage="spinning", running_cost_per_hour=0), weaver,
                 started_at=at(3, 6), ended_at=at(3, 14))
    login_as("owner")
    for order in orders:
        assert client.get(f"/api/costing/orders/{order.code}").json()["parts"]["labour"] == 400.0
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_rounding.py tests/test_costing_api.py -q`
Expected: the rounding tests fail to import `money`; the API tests fail because the routes still return the example figures (for instance `26490.0 != ...`).

- [ ] **Step 3: Write the loader**

`services/api/app/modules/costing/loader.py`:

```python
"""Reads the rows the costing engine needs and turns them into its plain records (no arithmetic happens here)."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import IST
from app.db.models import (
    Attendance, Machine, MachineDowntime, Order, ProductionRun, Roll, RollRun, Shift, Worker, YarnLot, YarnMovement,
)
from app.modules.costing.engine import records as rec
from app.modules.rolls.service import v_roll_status

# a roll is "settled" once it is not still moving through weaving, dyeing, QC or rework
SETTLED = ("in_store", "rejected", "loading", "dispatched")
PAD = dt.timedelta(days=1)       # a night shift is dated by the day it starts, so look a day either side


@dataclass
class Bundle:
    runs: list[rec.Run] = field(default_factory=list)
    machines: dict[int, rec.Machine] = field(default_factory=dict)
    workers: dict[int, rec.Worker] = field(default_factory=dict)
    shifts: dict[int, rec.Shift] = field(default_factory=dict)
    attendance: list[rec.Attendance] = field(default_factory=list)
    moves: list[rec.YarnMove] = field(default_factory=list)
    writeoffs: list[rec.WriteOff] = field(default_factory=list)
    downtimes: list[rec.Downtime] = field(default_factory=list)
    rolls: list[rec.Roll] = field(default_factory=list)
    roll_runs: list[rec.RollRun] = field(default_factory=list)
    labels: dict[int, str] = field(default_factory=dict)     # run id -> "Run 52 (LOOM-05, 2026-10-08)"


def _frac(value) -> Fraction:
    return Fraction(value)


def _reference_data(db: Session, bundle: Bundle, workers: bool = True) -> None:
    for m in db.scalars(select(Machine)):
        bundle.machines[m.id] = rec.Machine(m.id, m.code, m.name, m.stage, _frac(m.rated_output_per_hour),
                                            _frac(m.running_cost_per_hour), m.created_at)
    for s in db.scalars(select(Shift)):
        bundle.shifts[s.id] = rec.Shift(s.id, s.name, s.start_time, s.end_time)
    if workers:
        for w in db.scalars(select(Worker)):
            bundle.workers[w.id] = rec.Worker(w.id, w.role, _frac(w.daily_wage))


def _runs(db: Session, bundle: Bundle, rows: list[ProductionRun]) -> None:
    for r in rows:
        bundle.runs.append(rec.Run(r.id, r.order_id, r.machine_id, r.stage, r.operator_worker_id, r.started_at,
                                   r.ended_at, _frac(r.output_kg) if r.output_kg is not None else None))
        machine = bundle.machines[r.machine_id].code if r.machine_id else "by hand"
        bundle.labels[r.id] = f"Run {r.id} ({machine}, {r.started_at.astimezone(IST).date()})"


def _attendance(db: Session, bundle: Bundle, lo: dt.date, hi: dt.date, worker_ids: set[int] | None = None) -> None:
    query = select(Attendance).where(Attendance.work_date.between(lo, hi))
    if worker_ids is not None:
        query = query.where(Attendance.worker_id.in_(worker_ids))
    bundle.attendance = [rec.Attendance(a.worker_id, a.work_date, a.shift_id, a.status) for a in db.scalars(query)]


def _rolls(db: Session, bundle: Bundle, roll_rows: list[Roll], with_status: bool) -> None:
    status = {}
    if with_status and roll_rows:
        status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                                 .where(v_roll_status.c.roll_id.in_([r.id for r in roll_rows]))).all())
    bundle.rolls = [rec.Roll(r.id, r.order_id, _frac(r.metres), status.get(r.id) == "rejected",
                             status.get(r.id, "in_store") in SETTLED, r.created_at) for r in roll_rows]
    ids = [r.id for r in roll_rows]
    if ids:
        bundle.roll_runs = [rec.RollRun(link.roll_id, link.run_id, link.purpose)
                            for link in db.scalars(select(RollRun).where(RollRun.roll_id.in_(ids)))]


def _moves(db: Session, bundle: Bundle, where) -> None:
    rows = db.execute(select(YarnMovement, YarnLot.cost_per_kg).join(YarnLot, YarnLot.id == YarnMovement.yarn_lot_id)
                      .where(YarnMovement.kind.in_(("issue", "return")), where))
    bundle.moves = [rec.YarnMove(m.production_run_id, _frac(m.qty_kg), _frac(cost), m.created_at) for m, cost in rows]


def load_order(db: Session, order: Order, now: dt.datetime) -> Bundle:
    """One order, plus the other runs of the same operators in the same hours (a weaver's pay is shared across every
    loom they minded, whatever the order)."""
    bundle = Bundle()
    _reference_data(db, bundle)
    mine = list(db.scalars(select(ProductionRun).where(ProductionRun.order_id == order.id)))
    operators = {r.operator_worker_id for r in mine}
    clause = ProductionRun.order_id == order.id
    if mine:
        lo = min(r.started_at for r in mine) - PAD
        hi = max((r.ended_at or now) for r in mine) + PAD
        clause = or_(clause, (ProductionRun.operator_worker_id.in_(operators)) & (ProductionRun.started_at < hi)
                     & (func.coalesce(ProductionRun.ended_at, now) > lo))
        _attendance(db, bundle, lo.astimezone(IST).date(), hi.astimezone(IST).date(), operators)
    rows = list(db.scalars(select(ProductionRun).where(clause)))
    _runs(db, bundle, rows)
    _moves(db, bundle, YarnMovement.production_run_id.in_([r.id for r in mine] or [0]))
    _rolls(db, bundle, list(db.scalars(select(Roll).where(Roll.order_id == order.id))), with_status=True)
    return bundle


def load_month(db: Session, first: dt.date, after: dt.date, span: tuple[dt.datetime, dt.datetime],
               now: dt.datetime) -> Bundle:
    """Everything that touches the month: runs overlapping it, the month's yarn movements and downtimes, and the
    attendance around the runs."""
    bundle = Bundle()
    _reference_data(db, bundle)
    lo, hi = span[0] - PAD, span[1] + PAD
    in_month = (YarnMovement.created_at >= span[0]) & (YarnMovement.created_at < span[1])
    _moves(db, bundle, in_month)
    moved_runs = {m.run_id for m in bundle.moves}
    overlap = (ProductionRun.started_at < hi) & (func.coalesce(ProductionRun.ended_at, now) > lo)
    rows = list(db.scalars(select(ProductionRun).where(or_(overlap, ProductionRun.id.in_(moved_runs or {0})))))
    _runs(db, bundle, rows)
    starts = [r.started_at for r in rows] + [span[0]]
    ends = [(r.ended_at or now) for r in rows] + [span[1]]
    _attendance(db, bundle, (min(starts) - PAD).astimezone(IST).date(), (max(ends) + PAD).astimezone(IST).date())
    for off in db.scalars(select(YarnMovement).where(YarnMovement.kind == "adjustment", YarnMovement.qty_kg < 0, in_month)):
        cost = db.scalar(select(YarnLot.cost_per_kg).where(YarnLot.id == off.yarn_lot_id))
        bundle.writeoffs.append(rec.WriteOff(_frac(off.qty_kg), _frac(cost), off.created_at))
    for d in db.scalars(select(MachineDowntime).where(MachineDowntime.started_at < span[1],
                                                       func.coalesce(MachineDowntime.ended_at, now) > span[0])):
        bundle.downtimes.append(rec.Downtime(d.machine_id, d.started_at, d.ended_at))
    run_ids = [r.id for r in rows]
    roll_ids = set(db.scalars(select(RollRun.roll_id).where(RollRun.run_id.in_(run_ids or [0]))))
    _rolls(db, bundle, list(db.scalars(select(Roll).where(Roll.id.in_(roll_ids or {0})))), with_status=False)
    return bundle
```

- [ ] **Step 4: Write the service (order and roll cost)**

`services/api/app/modules/costing/service.py`:

```python
"""Costing on request (spec §7): load the rows, run the engine, round to the paisa, shape the response.
Nothing here writes, locks or publishes. Money is rounded half up to the paisa and a total is the sum of its
rounded parts; the engine's own figures stay exact."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from app.core.money import q_kg, q_money, to_float
from app.db.models import Order, Roll
from app.modules.costing import loader
from app.modules.costing.engine.allocation import PARTS, OrderResult, allocate_order, is_final
from app.modules.costing.engine.labour import Labour, split_labour
from app.modules.costing.engine.runs import run_costs
from app.modules.costing.schemas import CostParts, OrderCost, RollCost
from app.modules.floor.service import db_now
from app.modules.orders.service import get_order_or_404
from app.modules.rolls.service import get_roll_or_404

FINANCE = ("owner", "accountant")        # R18: the only roles that see cost
ZERO = Decimal(0)


def exact(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def money(value: Fraction) -> Decimal:
    return q_money(exact(value))


def two_places(value: Fraction) -> float:
    return float(exact(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _parts(parts: dict[str, Fraction]) -> dict[str, Decimal]:
    return {name: money(parts[name]) for name in PARTS}


def _warnings(bundle: loader.Bundle, labour: Labour, run_ids: set[int], now: dt.datetime) -> list[str]:
    out = []
    for run in bundle.runs:
        if run.id not in run_ids:
            continue
        gap = labour.uncovered.get(run.id)
        if gap:
            out.append(f"{bundle.labels[run.id]} has {two_places(gap)} hours not covered by its operator's attendance")
        if run.end is None:
            out.append(f"{bundle.labels[run.id]} is still open, so its cost is provisional")
    return out


class _OrderNumbers:
    """One order, costed: the bundle it was built from, the engine's result and whether it is final."""

    def __init__(self, db: Session, order: Order, now: dt.datetime):
        self.order = order
        self.bundle = loader.load_order(db, order, now)
        b = self.bundle
        self.labour = split_labour(b.attendance, b.workers, b.shifts, b.runs, now)
        costs = run_costs(b.runs, b.machines, b.moves, self.labour.per_run, now)
        self.runs = [r for r in b.runs if r.order_id == order.id]
        self.result: OrderResult = allocate_order(self.runs, b.rolls, b.roll_runs, costs)
        self.final = is_final(self.runs, b.rolls, self.result.good_metres, Fraction(order.qty_metres),
                              order.state == "cancelled")
        self.now = now


def order_cost(db: Session, order_code: str) -> OrderCost:
    order = get_order_or_404(db, order_code)
    n = _OrderNumbers(db, order, db_now(db))
    res = n.result
    parts = _parts(res.parts)
    total = sum(parts.values(), ZERO)
    good = exact(res.good_metres)
    revenue = q_money(good * order.price_per_metre)
    return OrderCost(
        order_code=order.code, parts=CostParts(**{k: to_float(v) for k, v in parts.items()}),
        reject_cost=to_float(money(res.reject_cost)), total=to_float(total),
        good_metres=to_float(q_kg(good)), rejected_metres=to_float(q_kg(exact(res.rejected_metres))),
        cost_per_good_metre=to_float(q_money(total / good)) if good > 0 else None,
        revenue=to_float(revenue), profit=to_float(revenue - total),
        unabsorbed=to_float(total if good == 0 else ZERO), provisional=not n.final,
        warnings=_warnings(n.bundle, n.labour, {r.id for r in n.runs}, n.now),
    )


def roll_cost_for(db: Session, roll: Roll, now: dt.datetime | None = None) -> RollCost:
    n = _OrderNumbers(db, roll.order, now or db_now(db))
    rr = n.result.rolls[roll.id]
    parts = _parts(rr.parts)
    share = money(rr.reject_share)
    total = sum(parts.values(), ZERO) + share
    return RollCost(
        roll_code=roll.code, parts=CostParts(**{k: to_float(v) for k, v in parts.items()}),
        reject_share=to_float(share), total=to_float(total),
        per_metre=to_float(q_money(total / exact(rr.metres))), provisional=not n.final,
    )


def roll_cost(db: Session, roll_code: str) -> RollCost:
    return roll_cost_for(db, get_roll_or_404(db, roll_code))
```

- [ ] **Step 5: Serve the two routes for real (the month route is Task 5)**

Replace `services/api/app/modules/costing/router.py` with:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.costing import examples as ex
from app.modules.costing import service
from app.modules.costing.schemas import MonthReport, OrderCost, RollCost

router = APIRouter(tags=["costing"])
finance = require_roles(*service.FINANCE)
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/costing/rolls/{roll_code}", response_model=RollCost, dependencies=[Depends(finance)])
def roll_cost(roll_code: str, db: Session = Depends(get_db)) -> RollCost:
    return service.roll_cost(db, roll_code)


@router.get("/costing/orders/{order_code}", response_model=OrderCost, dependencies=[Depends(finance)])
def order_cost(order_code: str, db: Session = Depends(get_db)) -> OrderCost:
    return service.order_cost(db, order_code)


@router.get("/reports/month", response_model=MonthReport, dependencies=[Depends(finance)])
def month_report(month: Month) -> MonthReport:
    return ex.MONTH.model_copy(update={"month": month})
```

- [ ] **Step 6: Fill the passport's cost for owner and accountant**

In `services/api/app/modules/passport/service.py`: (a) replace the first sentence pair of the module docstring `Cost is empty until costing (B6). A buyer gets ...` with `Cost is filled in for owner and accountant only (R18). A buyer gets ...`; (b) add `from app.modules.costing import service as costing` to the imports; (c) in `get_passport`, replace `cost=None, dispatch=_dispatch(db, roll),` with:

```python
        cost=costing.roll_cost_for(db, roll) if user.role in costing.FINANCE else None,
        dispatch=_dispatch(db, roll),
```

(`buyer_view` still sets `cost` to `None` for a buyer, so a buyer is covered twice.) Then fix the old tests found by the `grep` in the Files list: an old test that expected the example roll cost on a passport must now expect the real figure or `None` (this repeats what B5 did with its example-data tests).

- [ ] **Step 7: Run and watch them pass**

Run: `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_rounding.py tests/test_costing_api.py -q`
Expected: `3 + 14 = 17 passed` (14 API tests: the parametrised role test counts 5). If a figure is off, root-cause it with `systematic-debugging` (check the world's hand-worked numbers in this plan first), do not bend the expected number.

- [ ] **Step 8: Mutation-check** (revert after each):
  1. `service.py`: add `"store"` to `FINANCE`: `test_only_owner_and_accountant_may_read_cost[store]` and `test_the_passport_shows_cost_to_owner_and_accountant_only` fail.
  2. `passport/service.py`: replace the condition with `True`: the store/supervisor/qc/dispatch passport test fails.
  3. `service.py` `roll_cost_for`: use `Fraction(0)` for the reject share: `test_a_rolls_cost_carries_the_rejected_rolls_cost` fails.
  4. `loader.py` `load_order`: replace `clause = or_(clause, ...)` by leaving `clause` unchanged (load only this order's runs): `test_a_workers_pay_is_shared_across_the_runs_of_different_orders` fails (800 instead of 400).
  5. `service.py` `_OrderNumbers`: set `self.runs = []`: `test_the_cost_is_provisional_while_a_run_is_still_open` fails (the open run is no longer seen), and so do the cost tests.
  6. `service.py` `money`: replace `ROUND_HALF_UP` rounding by truncation (`ROUND_DOWN`) in `q_money` use: `test_money_rounds_half_up_to_the_paisa` fails.

- [ ] **Step 9: Full suite twice.** Expected both times: about **1,099 passed** (1,082 + 17); the contract test is untouched because no shape changed.

- [ ] **Step 10: Re-check the cost-never-leaks rule across the whole API**, not just the two places tested: `grep -rn "RollCost\|cost" services/api/app/modules/*/schemas.py | grep -v "costing"` and confirm no buyer-reachable response model carries a cost field (the portal and buyer passport do not).

- [ ] **Step 11: Sync and commit** (Status line with the real counts, header, then):

```bash
git add services/api/app/modules/costing services/api/app/modules/passport/service.py services/api/tests docs/plans/B6-costing.md
git commit -m "Serve real roll and order cost and show it on the passport to owner and accountant"
```

---

### Task 5: The month report, the contract field and the note to Ridanshi

**Files:**
- Modify: `services/api/app/modules/costing/service.py`, `router.py`, `schemas.py`; delete `services/api/app/modules/costing/examples.py`
- Modify: `apps/web/src/pages/owner/Owner.test.tsx` (one fixture line), `contracts/openapi.json`, `contracts/types.ts` (regenerated)
- Modify: `docs/HRITWIK_TEAM_NOTES.md` (a note to Ridanshi)
- Test: create `services/api/tests/test_costing_month_api.py`, `tests/test_costing_speed.py`

**Interfaces:**
- Consumes (Tasks 3-4): `month.{month_window, month_costs, machine_hours}`, `loader.load_month`, `service.{money, two_places}`, `people.service.{month_bounds, wage_rows}`.
- Produces: `service.month_report(db, month: str) -> MonthReport`; `ProfitPanel.support_staff: float` (the only contract change).

- [ ] **Step 1: Write the failing tests**

`services/api/tests/test_costing_month_api.py`:

```python
"""B6: the month report on the hand-worked September 2026 mill (tests/costing_world.py)."""
import datetime as dt

import pytest
from app.db.models import BuyerPayment, SupplierPayment, WagePayment
from tests.costing_world import build_world


@pytest.fixture
def world(db):
    return build_world(db)


def test_the_month_report_matches_the_hand_worked_september(client, login_as, db, world):
    # payments dated in October must not leak into September's cash, or into its outstanding amounts
    db.add(BuyerPayment(invoice_id=world.invoice.id, amount=7, received_at=dt.date(2026, 10, 1)))
    db.add(SupplierPayment(bill_id=world.bill.id, amount=9, paid_at=dt.date(2026, 10, 2)))
    db.add(WagePayment(worker_id=world.workers["ravi"].id, period_start=dt.date(2026, 10, 1),
                       period_end=dt.date(2026, 10, 31), amount=11, paid_at=dt.date(2026, 10, 3)))
    db.flush()
    login_as("owner")
    body = client.get("/api/reports/month?month=2026-09").json()
    assert body["month"] == "2026-09"
    assert body["profit"] == {
        "invoiced": 50000.0, "yarn_issued": 25000.0, "wages_earned": 2500.0, "idle_labour": 850.0,
        "support_staff": 800.0, "machine_running_cost": 640.0, "stock_writeoffs": 500.0, "profit": 21360.0,
    }
    assert body["cash"] == {
        "received_from_buyers": 20000.0, "paid_to_suppliers": 40000.0, "paid_wages": 1000.0, "net_cash": -21000.0,
        "receivables_outstanding": 30000.0, "payables_outstanding": 60000.0,
    }
    assert body["orders"] == [{"order_code": world.order.code, "buyer_name": "Sharma Fabrics", "revenue": 50000.0,
                               "cost": 26490.0, "profit": 23510.0}]
    p = body["profit"]            # the reconciliation invariant, on the rounded figures the page shows
    assert body["orders"][0]["cost"] + p["idle_labour"] + p["support_staff"] == p["yarn_issued"] + p["wages_earned"] + p["machine_running_cost"]


def test_the_month_machines_count_only_shift_time(client, login_as, world):
    login_as("owner")
    machines = {m["stage"]: m for m in client.get("/api/reports/month?month=2026-09").json()["machines"]}
    # the only shift is 06:00-14:00, so September has 30 x 8 = 240 hours of shift time
    assert (machines["spinning"]["running_h"], machines["spinning"]["idle_h"], machines["spinning"]["down_h"]) == (4.0, 236.0, 0.0)
    assert (machines["spinning"]["output"], machines["spinning"]["output_unit"]) == (95.0, "kg")
    assert (machines["spinning"]["lost_capacity"], machines["spinning"]["lost_capacity_unit"]) == (4720.0, "kg")
    assert (machines["weaving"]["running_h"], machines["weaving"]["output"], machines["weaving"]["lost_capacity"]) == (4.0, 1000.0, 6608.0)
    assert (machines["dyeing"]["running_h"], machines["dyeing"]["idle_h"], machines["dyeing"]["output"]) == (0.0, 240.0, 1000.0)
    assert machines["dyeing"]["lost_capacity"] == 10800.0


def test_the_month_report_warns_about_a_run_with_no_attendance(client, login_as, world):
    login_as("owner")
    warnings = client.get("/api/reports/month?month=2026-09").json()["warnings"]
    assert len(warnings) == 1 and f"Run {world.runs['dye'].id} " in warnings[0]


def test_the_month_wages_equal_the_wages_page_total(client, login_as, world):
    login_as("accountant")
    page = client.get("/api/wages?month=2026-09").json()["total_earned"]
    assert client.get("/api/reports/month?month=2026-09").json()["profit"]["wages_earned"] == page == 2500.0


def test_a_month_with_nothing_in_it_and_a_future_month_are_zeros_not_errors(client, login_as, world):
    login_as("owner")
    for month in ("2026-08", "2099-01"):
        body = client.get(f"/api/reports/month?month={month}").json()
        assert body["orders"] == [] and body["profit"]["profit"] == 0.0 and body["profit"]["invoiced"] == 0.0
        assert body["cash"]["net_cash"] == 0.0
    assert client.get("/api/reports/month?month=2026-08").json()["machines"] == []         # created after that month


@pytest.mark.parametrize("month", ["2026-13", "2026-00", "26-09", "september", "2026-9"])
def test_a_bad_month_is_a_422(client, login_as, month):
    login_as("owner")
    assert client.get(f"/api/reports/month?month={month}").status_code == 422
```

`services/api/tests/test_costing_speed.py`:

```python
"""B6: a busy month is costed in reasonable time. The budget is generous on purpose: it guards against an accidental
slow-down, and the real figure (run with -s) is recorded in the plan's Status section."""
import datetime as dt
import time

from app.db.models import Attendance
from tests.costing_world import at
from tests.factories import make_machine, make_order, make_run, make_shift, make_user, make_worker

BUDGET_SECONDS = 15


def test_a_busy_month_of_900_runs_is_costed_within_the_budget(client, login_as, db):
    marker = make_user(db, role="supervisor")
    shifts = [make_shift(db, name=name, start_time=dt.time(hour), end_time=dt.time((hour + 8) % 24))
              for name, hour in (("A", 6), ("B", 14), ("C", 22))]
    workers = [make_worker(db) for _ in range(12)]
    stages = ["spinning"] * 2 + ["weaving"] * 6 + ["dyeing"] * 2
    machines = [make_machine(db, stage=stage, created_at=at(1, 0)) for stage in stages]
    order = make_order(db)
    seed = make_run(db, order, machines[0], workers[0], started_at=at(1, 0), ended_at=at(1, 1))
    for day in range(1, 31):
        for number, (shift, hour) in enumerate(zip(shifts, (6, 14, 22))):
            for worker in workers:
                db.add(Attendance(worker_id=worker.id, work_date=dt.date(2026, 9, day), shift_id=shift.id,
                                  status="present", marked_by=marker.id))
            for index, machine in enumerate(machines):
                start = at(day, hour)
                extra = {"input_run_id": seed.id} if machine.stage == "weaving" else {}
                make_run(db, order, machine, workers[(index + number + day) % 12],
                         started_at=start, ended_at=start + dt.timedelta(hours=8), **extra)
    login_as("owner")
    began = time.perf_counter()
    response = client.get("/api/reports/month?month=2026-09")
    seconds = time.perf_counter() - began
    print(f"\nmonth report for 901 runs and 1,080 attendance records: {seconds:.2f} s")
    assert response.status_code == 200 and seconds < BUDGET_SECONDS
    assert response.json()["profit"]["wages_earned"] == 12 * 3 * 30 * 800          # everyone present on every shift
```

- [ ] **Step 2: Run and watch them fail.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_month_api.py tests/test_costing_speed.py -q`. Expected: the month tests fail on the example figures (and `support_staff` missing).

- [ ] **Step 3: Add the contract field.** In `services/api/app/modules/costing/schemas.py`, class `ProfitPanel`, add `support_staff: float` on the line after `idle_labour: float`.

- [ ] **Step 4: Write the month service.** In `services/api/app/modules/costing/service.py`, replace the import block (everything from `import datetime as dt` down to the last `from app.modules.rolls.service import get_roll_or_404`) with:

```python
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_ist
from app.core.money import q_kg, q_money, to_float
from app.db.models import (
    BuyerPayment, Invoice, InvoiceLine, Order, Roll, SupplierBill, SupplierPayment, WagePayment,
)
from app.modules.costing import loader
from app.modules.costing.engine.allocation import PARTS, OrderResult, allocate_order, is_final
from app.modules.costing.engine.labour import Labour, run_interval, split_labour
from app.modules.costing.engine.month import machine_hours, month_costs, month_window
from app.modules.costing.engine.runs import run_costs
from app.modules.costing.schemas import (
    CashPanel, CostParts, MachineMonth, MonthReport, OrderCost, OrderMonth, ProfitPanel, RollCost,
)
from app.modules.floor.service import db_now
from app.modules.orders.service import get_order_or_404
from app.modules.people.service import month_bounds, wage_rows
from app.modules.rolls.service import get_roll_or_404
```

and append this function at the end of the file:

```python
def month_report(db: Session, month: str) -> MonthReport:
    year, mon = (int(p) for p in month.split("-"))
    first, after, span = month_window(year, mon)
    last = after - dt.timedelta(days=1)
    now = db_now(db)
    b = loader.load_month(db, first, after, span, now)
    labour = split_labour(b.attendance, b.workers, b.shifts, b.runs, now)
    costs = month_costs(first, after, span, b.runs, b.machines, b.moves, b.writeoffs, labour, now)

    # --- profit
    invoiced = db.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0))
                         .where(Invoice.issued_at >= span[0], Invoice.issued_at < span[1]))
    wages = sum((Decimal(str(row.earned)) for row in wage_rows(db, *month_bounds(month))), ZERO)   # = GET /wages total
    yarn, machine, writeoffs = money(costs.yarn), money(costs.machine), money(costs.writeoffs)
    profit = ProfitPanel(
        invoiced=to_float(invoiced), yarn_issued=to_float(yarn), wages_earned=to_float(wages),
        idle_labour=to_float(money(costs.idle)), support_staff=to_float(money(costs.support)),
        machine_running_cost=to_float(machine), stock_writeoffs=to_float(writeoffs),
        profit=to_float(Decimal(invoiced) - yarn - wages - machine - writeoffs),
    )

    # --- cash (outstanding amounts are as at the end of the month, or today for the current month)
    asof = min(last, today_ist())

    def total(column, *conditions) -> Decimal:
        return Decimal(db.scalar(select(func.coalesce(func.sum(column), 0)).where(*conditions)))

    received = total(BuyerPayment.amount, BuyerPayment.received_at.between(first, last))
    paid_suppliers = total(SupplierPayment.amount, SupplierPayment.paid_at.between(first, last))
    paid_wages = total(WagePayment.amount, WagePayment.paid_at.between(first, last))
    receivable = (total(Invoice.total_amount, Invoice.issued_at < span[1])
                  - total(BuyerPayment.amount, BuyerPayment.received_at <= asof))
    payable = (total(SupplierBill.amount, SupplierBill.bill_date <= asof)
               - total(SupplierPayment.amount, SupplierPayment.paid_at <= asof))
    cash = CashPanel(
        received_from_buyers=to_float(received), paid_to_suppliers=to_float(paid_suppliers),
        paid_wages=to_float(paid_wages), net_cash=to_float(received - paid_suppliers - paid_wages),
        receivables_outstanding=to_float(receivable), payables_outstanding=to_float(payable),
    )

    # --- machines
    machines = []
    for m in sorted(b.machines.values(), key=lambda x: x.code):
        if m.created_at >= span[1]:
            continue
        h = machine_hours(m, b.runs, b.downtimes, b.rolls, b.roll_runs, list(b.shifts.values()), span, now)
        unit = "kg" if m.stage == "spinning" else "m"
        machines.append(MachineMonth(
            code=m.code, name=m.name, stage=m.stage, running_h=two_places(h.running), idle_h=two_places(h.idle),
            down_h=two_places(h.down), output=two_places(h.output), output_unit=unit,
            lost_capacity=two_places((h.idle + h.down) * m.rated), lost_capacity_unit=unit,
        ))

    # --- orders: revenue is the month's invoice lines, cost is what the order incurred in the month
    revenue = {oid: Decimal(amount) for oid, amount in db.execute(
        select(InvoiceLine.order_id, func.sum(InvoiceLine.amount)).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.issued_at >= span[0], Invoice.issued_at < span[1]).group_by(InvoiceLine.order_id))}
    orders = []
    for order in db.scalars(select(Order).where(Order.id.in_(set(costs.per_order) | set(revenue) or {0})).order_by(Order.code)):
        cost = sum((money(v) for v in costs.per_order.get(order.id, {}).values()), ZERO)
        rev = revenue.get(order.id, ZERO)
        orders.append(OrderMonth(order_code=order.code, buyer_name=order.buyer.name, revenue=to_float(rev),
                                 cost=to_float(cost), profit=to_float(rev - cost)))
    in_month = {r.id for r in b.runs if run_interval(r, now)[0] < span[1] and run_interval(r, now)[1] > span[0]}
    return MonthReport(month=month, profit=profit, cash=cash, machines=machines, orders=orders,
                       warnings=_warnings(b, labour, in_month, now))
```

- [ ] **Step 5: Serve the month for real and delete the example data.** Replace `services/api/app/modules/costing/router.py` with:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.db.session import get_db
from app.modules.costing import service
from app.modules.costing.schemas import MonthReport, OrderCost, RollCost

router = APIRouter(tags=["costing"])
finance = require_roles(*service.FINANCE)
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


@router.get("/costing/rolls/{roll_code}", response_model=RollCost, dependencies=[Depends(finance)])
def roll_cost(roll_code: str, db: Session = Depends(get_db)) -> RollCost:
    return service.roll_cost(db, roll_code)


@router.get("/costing/orders/{order_code}", response_model=OrderCost, dependencies=[Depends(finance)])
def order_cost(order_code: str, db: Session = Depends(get_db)) -> OrderCost:
    return service.order_cost(db, order_code)


@router.get("/reports/month", response_model=MonthReport, dependencies=[Depends(finance)])
def month_report(month: Month, db: Session = Depends(get_db)) -> MonthReport:
    return service.month_report(db, month)
```

Delete `services/api/app/modules/costing/examples.py` (`git rm`). Then `grep -rn "costing.examples\|costing import examples" services/api` and remove or update any remaining reader or example-data test of the month route (`test_contract_*.py` may assert the example month; the real tests above replace them).

- [ ] **Step 6: Keep Ridanshi's web suite green.** Her `apps/web/src/pages/owner/Owner.test.tsx` builds a profit panel by hand (line 12, `profit: { invoiced: 412000, ..., idle_labour: 14200, ...}`). After the contract is regenerated her type-check would fail for the missing field. Add `support_staff: 3200,` right after `idle_labour: 14200,` in that fixture, and nothing else of hers (a row on the owner page is hers to add; say so in the note).

- [ ] **Step 7: Regenerate the contract and check the diff is exactly the one field.**

Run: `npm run contracts` then `git diff --stat contracts` and `git diff contracts | grep '^[+-]' | grep -v '^+++\|^---'`
Expected: only `support_staff` lines (in `openapi.json`: the property and its entry in `required`; in `types.ts`: one field). Anything else is an unintended shape change: stop and find it.

- [ ] **Step 8: Run and watch them pass.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_costing_month_api.py tests/test_costing_speed.py tests/test_contract.py -q`. Expected: 10 month tests (the bad-month test is parametrised five ways) and 1 speed test pass, and the contract tests stay green. Run the speed test again with `-s` and write the printed seconds into this plan's Status line (that is the real, measured figure; the spec said "unmeasured").

- [ ] **Step 9: Web checks (Ridanshi's side stays green).** `cd apps/web && npx vitest run src/pages/owner && npx tsc -b`. Expected: passes, no type errors.

- [ ] **Step 10: Mutation-check** (`service.py`; revert after each):
  1. In `month_report`'s `ProfitPanel(... profit=...)`, also subtract `money(costs.idle)`: `test_the_month_report_matches_the_hand_worked_september` fails.
  2. Replace the `wages = sum(...)` line with `wages = Decimal(0)`: the profit test and `test_the_month_wages_equal_the_wages_page_total` fail (the report must take wages from `wage_rows`).
  3. Remove the date condition from the `received` query (`BuyerPayment.received_at.between(first, last)` → no condition), then from `paid_suppliers` and `paid_wages` the same way, one at a time: the September test fails each time (it adds October payments of 7, 9 and 11 that must stay out). Also change `BuyerPayment.received_at <= asof` in `receivable` to no condition: the same test fails (receivables would be 29,993).
  4. Delete `if m.created_at >= span[1]: continue`: the `machines == []` assertion for August fails.

- [ ] **Step 11: Full suite twice.** Expected both times: about **1,110 passed**.

- [ ] **Step 12: Write the note to Ridanshi** at the top of `docs/HRITWIK_TEAM_NOTES.md` (newest first; heading with the live HH:MM IST; "**From:** Hritwik → Ridanshi"). It must say, in plain words: costing is real (`/costing/rolls/{code}`, `/costing/orders/{code}`, `/reports/month`) for owner and accountant, and the roll passport shows cost only to them (everyone else gets `cost: null`, buyers never); **one new field `support_staff` on the month report's profit panel**, additive, shapes otherwise byte-identical; she needs to add a "Support staff" row next to "Idle labour" on the owner page (idle labour now means idle operators only; support staff is the unrun pay of inspectors, supervisors, storekeepers and dispatch clerks and is already inside "Wages earned"; both are lines inside wages earned, not extra costs); I added `support_staff: 3200` to the fixture in `Owner.test.tsx` only so the type-check stays green; **mark a night shift (C) on the day it starts** (a C shift marked on the 10th covers 22:00 on the 10th to 06:00 on the 11th); roll costs are provisional until the order is fully woven and inspected (the page already shows the badge); the demo seeds have no attendance, so until B9 seeds some, runs show a data warning and no labour. Update the note's `Last updated`.

- [ ] **Step 13: Sync and commit** (Status line with the speed figure and counts, header, then):

```bash
git add services/api/app/modules/costing services/api/tests apps/web/src/pages/owner/Owner.test.tsx contracts docs/HRITWIK_TEAM_NOTES.md docs/plans/B6-costing.md
git commit -m "Serve the real month report and add the support-staff line to the contract"
```

---

### Task 6: Prove it on a real server, close B6

**Files:** modify `docs/plans/B6-costing.md`, `docs/plans/README.md`, `docs/specs/2026-10-10-textile-mill-design.md` (header, §16 if anything new was learned), memory. No code unless the live check finds a bug (then fix it test-first, in the task it belongs to, and say so).

- [ ] **Step 1: Throwaway database and server.** Check `lsof -nP -iTCP:8000 -iTCP:3000 -iTCP:8123 -sTCP:LISTEN`; `export DATABASE_URL=postgresql+psycopg://localhost:5432/everest_livecheck`; `createdb everest_livecheck`; `npm run db:migrate && npm run db:seed && npm run db:demo`; start `cd services/api && uv run uvicorn app.main:app --host 127.0.0.1 --port 8123` in the background. Drive it with `ctx_execute` Python over HTTP (curl is blocked by a hook).

- [ ] **Step 2: Give the demo mill real hours and attendance.** The demo mill's runs last seconds, so make them meaningful with SQL on the throwaway database only: `update production_runs set started_at = started_at - interval '5 hours';` and `update machines set created_at = created_at - interval '40 days';`. Then, as `supervisor`, mark attendance for today's three shifts (`POST /attendance` with the shift whose window holds each run; all 12 workers present; mark one operator `half_day`; leave one run's operator unmarked to see the warning).

- [ ] **Step 3: Check the numbers against the database, not against the engine.** For the current month, compute straight from SQL: yarn issued (`sum(-qty_kg * cost_per_kg)` over issue and return movements joined to their lots), machine cost (hours of each run inside the month × the machine's rate), wages earned (`daily_wage` × 1 / 0.5 over attendance in the month), and compare each with `/api/reports/month`'s `yarn_issued`, `machine_running_cost`, `wages_earned` (also `GET /api/wages`). Then check on the API's own figures that `sum(orders[].cost) + idle_labour + support_staff` equals `yarn_issued + wages_earned + machine_running_cost` within 0.05, and that `GET /costing/orders/ORD-0001`'s total equals that order's row in the month report when all its cost fell in this month.

- [ ] **Step 4: The role and leak matrix on the real server.** `GET /costing/rolls/R-0001` as owner and accountant (200); as `store`, `supervisor`, `qc`, `dispatch` (403); `GET /rolls/R-0001/passport` as owner (cost present) and as `store` (`cost` null); as the order's buyer the passport has no cost and its raw text contains none of `per_metre`, `reject_share`, `parts`. `GET /reports/month?month=2026-13` gives 422.

- [ ] **Step 5: Adversarial checklist, once, on the new code and on the fixes made in this task:** zero or negative-looking values (a run of zero length, a machine rate of 0, an order with no rolls); empty inputs (a month with no data, an operator with no attendance); jointly invalid inputs (a run that overlaps a downtime, two shifts that overlap); double-submit and concurrency (not applicable: read-only; state this); identity change (the passport after a roll's order changes: not possible; state this); type and serialization (no NaN or infinity can reach the JSON: grep the schemas' `float` fields and confirm every value comes from `to_float(Decimal)` or `two_places`). Record what was checked and what was not applicable.

- [ ] **Step 6: Re-check the other half of the system.** With the server still up, run the earlier chain on the same database (`ORD-0001` end the DYE-01 run, QC, dispatch, confirm, pay) and confirm `/reports/month` now shows the invoice and payment in `invoiced` and the cash panel. Then stop the server, `dropdb everest_livecheck`, confirm nothing listens on 8123, and that only `everest` and `everest_test` remain. Hritwik's servers are not touched; if they are running, re-check `GET /api/floor`, `/api/orders`, `/api/money/receivables` and `/api/reports/month?month=<current>` as owner (200s); note that his database needs no migration for this work.

- [ ] **Step 7: Close out.** Mark B6 complete in this plan (`Done when` all met) and in `docs/plans/README.md`; update spec §7.7's "once written" wording and the header; record in spec §16 anything learned (for example "night shifts are dated by the day they start; confirmed with Track A" if she replies); update the memory project state (suite count, B6 done, next B7); run the authorship scan on the staged diff; commit; tell Hritwik to push and what to look at.

```bash
git add docs
git commit -m "Close B6: the costing live check passed on a real server"
```

---

## Done when

- The full suite is green twice; the engine tests pass without a database; every mutation listed in Tasks 1-5 makes a test fail (a surviving one led to a stronger test, as the three found in the scratch run did).
- The roll, order and month figures on a real server agree with totals computed separately from the database, and the month reconciles: orders' cost + idle labour + support staff = yarn + wages + machine, within a paisa of rounding on the page and exactly in the engine tests.
- Only owner and accountant can read cost anywhere (routes and passport); a buyer's raw responses contain none.
- `contracts/` differs from before by exactly `ProfitPanel.support_staff`; Ridanshi's web suite and type-check are green and she has the note.
- `docs/plans/README.md` marks B6 done; the plan's Status, the spec header and the memory are current; the speed figure is recorded.
