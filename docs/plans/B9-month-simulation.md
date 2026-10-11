# B9 — A Simulated Month Implementation Plan

> **Summary:** Builds `scripts/month/` and `scripts/build_month.py`: a deterministic scheduler that turns a hand-picked set of orders into timed mill events for the 30 days ending an hour before the build, a simulated clock that moves every real-clock timestamp the services write to the simulated moment, a runner that plays the events through the real service functions, and an audit that proves seven stories show up through the real endpoints. The target is a separate database `everest_month`; `everest` is never touched.
> **Last updated:** 2026-10-11 06:29 IST (B9 complete: Tasks 1-7 done)

> **How this plan is executed:** inline, one task at a time (atomic-workflow): test first, the full suite twice at each boundary, the important behaviours mutation-checked. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Hritwik and the jury see a mill with a month of history, on every screen, built by the real rules.

**Architecture:** `plan.py` (pure Python) produces `Event(t, seq, action, args)` objects in simulated time. `runner.py` plays them in order; around each one `clock.py` records the real time, lets the service run, then rewrites every `timestamptz` value written in that real window to the simulated moment, and swaps `today_ist()` for the simulated date. `audit.py` reads the finished database through the real endpoint functions. `build_month.py` creates the database, migrates, seeds, plays, audits.

**Tech Stack:** Python 3.12, SQLAlchemy 2, PostgreSQL 16, pytest (`uv run python -m pytest -p no:warnings -o addopts=` from `services/api`), the existing service functions. No new dependencies.

**Spec:** `docs/specs/2026-10-11-month-simulation-design.md` (read it first). The corrections below were found while writing this plan and supersede the spec where they differ; Task 7 folds them into the spec.

## Status

Task 1 done and verified (2026-10-11 05:42 IST): `scripts/month/clock.py` (`SimClock`: the timestamp mover, the `today_ist` swap, the leak check) and 9 tests; passed first time. **Five of six planned mutations survived at first**, which showed the tests were weaker than the design: the older-value and window mutations needed a row with one old and one real column (the hand-over case) and the one-statement-per-table rule needed a throwaway table whose later column is declared first (a real `production_runs` row cannot show it because `started_at` precedes `ended_at`); both tests were added and every mutation now dies. Full backend suite 1,461 passed (1,452 before), twice. Nothing listening on :8000.

Task 2 done and verified (2026-10-11 05:47 IST): `scripts/month/plan.py` and 21 tests (`test_month_plan.py`, no database). First run found: (1) a real bug, `ZeroDivisionError` in `Roster.operator`: the roster covered 36 days but a late order's pipeline is planned past the end and those dropped events still name an operator, so the roster now covers `days + 90`; (2) my own arithmetic: the twelve orders total **39,500 m** (not 40,000), about 61% of the dyers' capacity, and the plan makes **69 rolls** (not about 150), 66 inspections (73% passed first time), 10 trucks (one still loading at the end), 4 machines running and SPIN-02 down at the end; (3) the in-progress story: orders took 7 to 8 days each, so only O11 was open; fixed by moving O9 to day 22 and O10 to day 25 and adding `OrderSpec.hold` (hours a loaded truck waits for sign-out: O9 holds 20 h so its truck is still loading "now"); (4) only one buyer payment landed in the month because payments came 12 to 25 days after the truck; now 4 to 14 days, and the partial payment is the third payment that really happens. Mutations: nine of ten died at once; the survivor (spinning ignores the machine's free time) showed that the standard month never makes orders compete for the ring frames, so a stress test (three orders arriving together queue for two frames) was added and the mutant now dies. Full backend suite 1,482 passed (1,461 before), twice.

Task 3 done and verified (2026-10-11 05:51 IST): `scripts/month/database.py`, the first half of `scripts/month/runner.py`, and 9 tests in `test_month_build.py` on a real throwaway database (`everest_month_test`, made once per module and dropped; only `everest` and `everest_test` remain afterwards). **The real services accepted every order, lot, run, hand-over, roll-off and dye load on the first run, and the leak check was empty**: the database defaults, `db_now` and `datetime.now` were all moved, and bill dates and deadlines follow the simulated calendar. The test's first-half filter had to change (play the events before the first inspection, since nothing before that involves rework). Mutations: the mover doing nothing, `today_ist` swapped only in the core module, no safety margin (which does matter), seeding outside a clock step, and the deadline taken from the real date all die; the last one first survived because no test checked deadlines, so one was added. Full backend suite 1,491 passed (1,482 before), twice.

Task 4 done and verified (2026-10-11 05:56 IST): the second half of `runner.py` (quality, rework, dispatch, invoices, buyer and supplier payments, attendance, wages, breakdowns) and 6 more tests; **the real services accepted every event on the first run** (a 30-day month with three orders: inspections, hand and machine rework, trucks, invoices, 4 breakdowns with SPIN-02 still down at the end, wage payments, attendance). Checked in SQL from the tables, not from the plan: every run's operator was marked present for the shift in which the run started; every dispatched roll's latest inspection is a pass; the opening lot's bill is overdue. Corrections to the plan's code: `WageRow` has `worker_id` (not `worker.id`); the two module-scoped fixtures were merged into one (the second `DROP DATABASE ... WITH (FORCE)` killed the first one's connection), so `Runner.play` lost its `only` filter. Mutations: wrong operator, everyone absent, wages skipped, breakdowns not recorded (the real service refuses the repair), supplier payment skipped and verdict forced to pass (the real service refuses the rework) all die. Full backend suite 1,497 passed (1,491 before), twice.

Task 5 done and verified (2026-10-11 06:02 IST): `scripts/month/audit.py` (structure checks for any month: no leaks, yarn on hand = ledger, every run's operator present, month reports with invoiced = invoices in SQL and no "not covered" warning, order yarn cost = ledger x lot price in SQL, portal scope; story checks for the full month: bad lot flagged and recall reaching both buyers, unlucky operator not flagged, loss order, late order, low cotton, floor board statuses, idle loom, QC queue, overdue bill, part-paid invoice, truck still loading, and the month's counts) and 2 tests. **The first audit run found a real design flaw in the clock (Task 1):** the mover kept the few milliseconds a step really took, so a hand-over planned for 14:00:00 landed at 14:00:00.012, a hair outside the outgoing operator's shift, and the month report warned "0.0 hours not covered by attendance". A simulated step is instantaneous, so the mover now sets every value written in a step to exactly the planned moment; its tests were rewritten to say so (and the old design now fails six tests). Plan changes: `audit(db, clock, runner=None, full=True)` takes the runner (for the lot, order and roll codes), not the plan. Planted-fault tests prove the leak check and the attendance check turn red; the ledger and invoiced checks compare two derivations of the same table, so no SQL plant can separate them (the real build is their test). Full backend suite 1,499 passed (1,497 before), twice.

Task 6 done and verified (2026-10-11 06:06 IST): `scripts/build_month.py` (`choose_end`, `build_month`, `main`), `npm run db:month`, the two buyer emails in `seed_dev.py`, and 7 more tests including a whole 30-day, three-order month built end to end through the entry point into its own database and audited clean. The refusals are proved: any other database name, a month ending after (or within 30 minutes of) the real clock, and the end not rounded down. `ALLOWED` grew to three fixed names (`everest_month`, `everest_month_test`, `everest_month_e2e`) because dropping a database kills the other test fixture's connection to it. Mutations die (future end allowed; end not rounded down). Full backend suite 1,504 passed (1,499 before), twice; nothing under `app/` changed; `everest` untouched.

Task 7 done and verified (2026-10-11 06:29 IST): the real month built in about 10 seconds (`npm run db:month`) and **19 of 22 checks passed the first time**; the three failures each found something real and were fixed at the cause, never by loosening the audit: (1) open runs are costed up to the real clock, so the audit now judges finished runs, the build ends five minutes (not an hour) before now, and attendance is marked for every shift dated up to the end's own date; (2) the bad lot was not flagged (10 rolls, 50% defective, p = 0.054 against a Bonferroni threshold near 0.005): the bad orders grew to 3,000 m with 85% non-pass odds and the loss order shrank to 2,000 m so its own lot (under five rolls) is never tested; (3) only one invoice was unpaid because buyers paid 4 to 14 days after a truck: now 7 to 21. Then the headline numbers exposed a bigger finding: the late-orders screen listed seven orders, the oldest "21 days late", because a rejected roll is never replaced and there is no "close short" feature. Rejected metres are now re-made (their own lot, spinning, weaving, dyeing, check), which first stretched every order to two weeks because the scheduler's per-machine "free from" pointer was pushed into the future by each replacement batch; machines now keep booked intervals and jobs take the earliest gap that fits. Result: 22 of 22 checks pass; bad lot L-0009 flagged (92% against 20%, p = 0.0000045) with the unlucky operator not flagged; ORD-0007 loses ₹27,576; ORD-0012 is the only late order (5 days, bottleneck dyeing); cotton is 56 kg short; one supplier bill overdue (L-0001); 10 invoices, 4 unpaid, 1 half-paid; one truck loading; 4 rolls waiting for QC; 4 machines running, 5 idle, 1 down. Independent SQL recalculation matches to the paisa for wages (September and October), ORD-0001's machine cost, verdict counts and money outstanding. Every role (owner 21 endpoints, accountant, supervisor, qc, store, dispatch, buyer) gets 200 on its screens through a real server on a throwaway port; the buyer is refused the floor board and the money screens. `docs/demo.md`, the spec (section 9), the plan index and a note to Ridanshi are written; `everest` still has its three orders and nothing under `app/` or `contracts/` changed. Not done: looking at the screens in a browser. Full backend suite 1,505 passed, in 9 of 10 full runs after the last code change: **one run showed a single failure that I could not identify** (I had printed only the last line, so the test name was lost) and could not reproduce in five more full runs and fourteen loops of the month, clock and plan tests; it is recorded here as an unexplained intermittent failure, not as explained.

## Spec corrections found while planning

| Spec says | Reality (read from the code) | Plan does |
|---|---|---|
| "one buyer invoice overdue" | invoices have no due date; only supplier bills do (`due_date = bill_date + 30 days`) | invoices of different ages stay unpaid and one is part-paid; the overdue story is the supplier bill |
| a supplier bill can be overdue within a 30-day month | a bill is due 30 days after the lot arrives, so it is overdue only if the lot arrived more than 30 days before "today" | the first order's lot is received 4 days before the month starts (opening stock) and left unpaid |
| the bad lot is the 17th lot (`L-0017`) | each order gets its own lot, so about 14 lots arise; forcing 17 would need filler | the bad lot gets whatever number it gets; `docs/demo.md` names it |
| about 35,000 m, about 54% of the dyers | the chosen 12 orders total 40,000 m, about 62% of the dyers' 64,800 m a month | 40,000 m |
| verdicts about 75% pass, 15% rework, 10% reject | root cause needs a clean contrast: base odds 88/8/4, bad lot 35/40/25, loss order 15/65/20 | the overall mix is measured and reported, not promised |
| `npm run dev:month` | the repo has a Windows teammate (`https` runs PowerShell); an inline environment variable does not work there | `docs/demo.md` gives the command for both shells |

## Global Constraints

- Only `everest_month` (and `everest_month_test`, made and dropped by the end-to-end test) may be built. Any other database name is refused before anything connects for writing. `everest` is never written.
- No change to application code under `app/`, and no migrations. The scripts only call existing functions.
- Simulated history ends at the build moment rounded down to the hour, minus one hour, so every real-clock value is later than every simulated one (the timestamp mover depends on it).
- Every record is made by the real service functions (or the router functions for attendance and wages, called directly). A service refusing a step stops the build with the event named; nothing is skipped silently.
- Deterministic: the same seed and end moment give the same events (`random.Random(seed)`, fixed iteration order).
- Machine facts come from `scripts/seed_dev.py` (rates 20 and 22 kg/h, 28 m/h, 45 m/h; shifts A 06-14, B 14-22, C 22-06; 7 operators); a night shift is dated by the day it starts.
- Commit locally, never push.
- Hritwik's dev server auto-reloads from this folder; the plan changes nothing it serves, but after each task confirm `GET /api/health` still answers if `lsof -nP -iTCP:8000 -sTCP:LISTEN` shows it. His `everest` database needs no migration.

## Review Focus

The conditions the spec implies but does not spell out, most likely first, each pinned by a test in the task that owns it:

1. **A service refuses a step because the plan broke a rule** (a machine double-booked, an operator not present, a roll in the wrong status). Task 2 pins the plan's own invariants without a database; Task 3 and 4 run the real services, which refuse loudly.
2. **A real-clock timestamp slips through** (a default, `datetime.now`, a column added later). Task 1 (the mover and the leak check) and Task 3 (a mini month whose leak check must be empty).
3. **A run's operator is not present for the hours the run covers** (the month report's "hours not covered by attendance" warning). Task 2 pins that every start and hand-over names a present operator; Task 5 pins that the month report has no such warning.
4. **The month ends in the future or the target is the wrong database.** Task 6 pins both refusals.
5. **A story does not show on its screen** (the bad lot is not flagged, the late order is not late). Task 5's audit fails the build; the numbers are tuned, the audit is not weakened.
6. **Events after the end moment.** Anything later than the end is dropped, so runs, trucks and QC are left open "right now" as designed. Task 2 pins that nothing is later than the end and that at least three orders are in progress.

---

## File structure

| File | Responsibility |
|---|---|
| `services/api/scripts/month/__init__.py` (create) | empty |
| `services/api/scripts/month/clock.py` (create) | `SimClock`: simulated moment, `today_ist` swap, timestamp mover, leak check |
| `services/api/scripts/month/plan.py` (create) | the orders, the roster, the scheduler; `build_plan` |
| `services/api/scripts/month/database.py` (create) | making, migrating and dropping the month's own database; refusing every other name |
| `services/api/scripts/month/runner.py` (create) | `Runner`: plays events through the real services |
| `services/api/scripts/month/audit.py` (create) | the pass or fail checks |
| `services/api/scripts/build_month.py` (create) | the end-moment rule, `build_month`, `main` |
| `services/api/scripts/seed_dev.py` (modify) | two fake buyer emails |
| `package.json` (modify) | `db:month` |
| `docs/demo.md` (create, Task 7) | what to open, with the real numbers |
| tests | `test_month_clock.py` (in the usual rolled-back fixture), `test_month_plan.py` (no database), `test_month_build.py` (its own throwaway database `everest_month_test`), all in `services/api/tests/` |

---

### Task 1: The simulated clock

**Files:**
- Create: `services/api/scripts/month/__init__.py` (empty), `services/api/scripts/month/clock.py`
- Test: `services/api/tests/test_month_clock.py`

**Interfaces:**
- Produces: `SimClock(db, end)` with `.now` (the current simulated moment), `.at(moment)` (a context manager), `.installed()` (a context manager that swaps `today_ist`), `.leaks() -> list[str]`; `timestamp_columns(db) -> dict[str, list[str]]`.

- [x] **Step 1: Write the failing tests.**

`services/api/tests/test_month_clock.py`:

```python
"""B9 Task 1: the simulated clock moves real timestamps written inside a step to the simulated moment, and nothing else."""
import datetime as dt
import time

from sqlalchemy import func, select, text

from app.core import clock as core_clock
from app.modules.orders import service as orders_service
from scripts.month.clock import SimClock, timestamp_columns
from tests.factories import make_order

IST = core_clock.IST
END = dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST)
MOMENT = dt.datetime(2026, 9, 20, 10, 30, tzinfo=IST)


def real_now(db):
    return db.scalar(select(func.clock_timestamp()))


def test_columns_known(db):
    cols = timestamp_columns(db)
    assert "started_at" in cols["production_runs"] and "ended_at" in cols["production_runs"]
    assert "confirmed_at" in cols["orders"] and "received_at" in cols["yarn_lots"]
    assert all(not name.startswith("v_") for name in cols)               # views are not tables


def test_a_value_written_inside_the_step_moves_and_an_older_one_stays(db):
    clock = SimClock(db, END)
    old, new = make_order(db), make_order(db)
    old_value = real_now(db)
    db.execute(text("UPDATE orders SET confirmed_at = :v WHERE id = :i"), {"v": old_value, "i": old.id})
    time.sleep(0.4)                                                        # clear of the 0.25 s margin
    with clock.at(MOMENT):
        db.execute(text("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = :i"), {"i": new.id})
    db.expire_all()
    assert abs((new.confirmed_at - MOMENT).total_seconds()) < 0.2
    assert old.confirmed_at == old_value


def test_two_values_in_one_step_keep_their_distance(db):
    clock = SimClock(db, END)
    first, second = make_order(db), make_order(db)
    with clock.at(MOMENT):
        db.execute(text("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = :i"), {"i": first.id})
        time.sleep(0.05)
        db.execute(text("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = :i"), {"i": second.id})
    db.expire_all()
    assert 0.04 < (second.confirmed_at - first.confirmed_at).total_seconds() < 0.5


def test_one_statement_may_move_two_columns_of_a_row_without_breaking_a_check(db):
    """production_runs has CHECK ended_at >= started_at; both columns are real in this step, so both must move together."""
    from tests.factories import make_machine, make_run
    clock = SimClock(db, END)
    order = make_order(db)
    run = make_run(db, order, make_machine(db, stage="spinning"))
    with clock.at(MOMENT):
        db.execute(text("UPDATE production_runs SET started_at = clock_timestamp() WHERE id = :i"), {"i": run.id})
        time.sleep(0.02)
        db.execute(text("UPDATE production_runs SET ended_at = clock_timestamp() WHERE id = :i"), {"i": run.id})
    db.expire_all()
    assert run.started_at <= run.ended_at and abs((run.started_at - MOMENT).total_seconds()) < 0.2


def test_today_is_swapped_only_inside_installed(db):
    clock = SimClock(db, END)
    real_today = core_clock.today_ist()
    with clock.installed():
        with clock.at(MOMENT):
            assert core_clock.today_ist() == dt.date(2026, 9, 20)
            assert orders_service.today_ist() == dt.date(2026, 9, 20)          # a module that imported the name
    assert core_clock.today_ist() == real_today and orders_service.today_ist() == real_today


def test_the_leak_check_names_a_value_later_than_the_end(db):
    clock = SimClock(db, END)
    order = make_order(db)
    db.execute(text("UPDATE orders SET confirmed_at = :v WHERE id = :i"), {"v": END + dt.timedelta(hours=1), "i": order.id})
    assert any(line.startswith("orders.confirmed_at") for line in clock.leaks())


def test_the_leak_check_is_quiet_when_everything_is_before_the_end(db):
    clock = SimClock(db, dt.datetime.now(IST) + dt.timedelta(days=1))
    make_order(db)
    assert clock.leaks() == []
```

The tests in this file run inside the usual rolled-back test transaction, where a database default `now()` is frozen at the start of the test. They therefore write their "real" timestamps explicitly with `clock_timestamp()` inside the step. The default-`now()` columns are proved in Task 3 on a real throwaway database.

- [x] **Step 2: Run to verify it fails.** `cd services/api && uv run python -m pytest -p no:warnings -o addopts= tests/test_month_clock.py -q` — Expected: collection error, `scripts.month` does not exist.

- [x] **Step 3: Implement.** `services/api/scripts/month/__init__.py` empty. `services/api/scripts/month/clock.py`:

```python
"""The simulated clock for the month build.

The services take "now" from the database clock (`db_now`), from a database default (`DEFAULT now()`), from Python
(`datetime.now`) and, for dates, from `today_ist()`. Around every simulated step this clock records the real time, lets the
service run, then rewrites every timestamp-with-time-zone value written in that real window to the simulated moment (plus
the same offset inside the window), and answers `today_ist()` with the simulated date. It works only because simulated
history ends before the real clock: a simulated value can never fall inside a later real window.
"""
import datetime as dt
import sys
from contextlib import contextmanager

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core import clock as core_clock

MARGIN = dt.timedelta(seconds=0.25)     # a transaction's `now()` is its start, a hair before the first query's clock reading


def timestamp_columns(db: Session) -> dict[str, list[str]]:
    """Every timestamp-with-time-zone column of every real table (views excluded), by table: asked of the database,
    so a column added later is covered without anyone remembering to list it."""
    rows = db.execute(text(
        "SELECT c.table_name, c.column_name FROM information_schema.columns c "
        "JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name "
        "WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE' AND c.data_type = 'timestamp with time zone' "
        "ORDER BY c.table_name, c.ordinal_position")).all()
    out: dict[str, list[str]] = {}
    for table, column in rows:
        out.setdefault(table, []).append(column)
    return out


class SimClock:
    def __init__(self, db: Session, end: dt.datetime):
        self.db, self.end, self.now = db, end, end
        self.columns = timestamp_columns(db)

    def real_now(self) -> dt.datetime:
        return self.db.scalar(select(func.clock_timestamp()))

    @contextmanager
    def installed(self):
        """Inside this block `today_ist()` answers with the simulated date, in every loaded `app` module that imported it."""
        original = core_clock.today_ist
        patched = lambda: self.now.astimezone(core_clock.IST).date()  # noqa: E731
        touched = [m for name, m in list(sys.modules.items()) if name.startswith("app.") and getattr(m, "today_ist", None) is original]
        for module in touched:
            module.today_ist = patched
        core_clock.today_ist = patched
        try:
            yield self
        finally:
            for module in touched:
                module.today_ist = original
            core_clock.today_ist = original

    @contextmanager
    def at(self, moment: dt.datetime):
        """One simulated step. Whatever real timestamps the body writes become `moment` (keeping their small differences)."""
        real_start = self.real_now()
        self.now = moment
        yield
        self._move(real_start, self.real_now(), moment)
        self.db.commit()

    def _move(self, real_start: dt.datetime, real_end: dt.datetime, moment: dt.datetime) -> None:
        params = {"lo": real_start - MARGIN, "hi": real_end + MARGIN, "moment": moment, "real_start": real_start}
        for table, columns in self.columns.items():
            # one statement per table, so a row's two columns (started_at and ended_at) move together and a CHECK between
            # them is judged on the final values
            sets = ", ".join(f'"{c}" = CASE WHEN "{c}" BETWEEN :lo AND :hi THEN :moment + ("{c}" - :real_start) ELSE "{c}" END'
                             for c in columns)
            where = " OR ".join(f'"{c}" BETWEEN :lo AND :hi' for c in columns)
            self.db.execute(text(f'UPDATE "{table}" SET {sets} WHERE {where}'), params)

    def leaks(self) -> list[str]:
        """Every column holding a value later than the simulated end: a real-clock value that was never moved."""
        out = []
        for table, columns in self.columns.items():
            for column in columns:
                n = self.db.scalar(text(f'SELECT count(*) FROM "{table}" WHERE "{column}" > :end'), {"end": self.end})
                if n:
                    out.append(f"{table}.{column}: {n} value(s) later than {self.end:%Y-%m-%d %H:%M}")
        return out
```

- [x] **Step 4: Run it.** Expected: all pass.
- [x] **Step 5: Mutation checks:** narrow the window to `real_start` exactly (`MARGIN = 0`) is not testable here (it only matters for `now()` defaults), so instead: remove the `ELSE "{c}"` branch (the older-value test fails); move the two columns in two statements (the CHECK test fails); drop the `installed` restore (the "only inside" test fails); drop the view filter (`test_columns_known` fails).
- [x] **Step 6: Full suite twice;** both green.
- [x] **Step 7: Commit.**

```bash
git add services/api/scripts/month services/api/tests/test_month_clock.py
git commit -m "Add the simulated clock for building a month of mill history"
```

---

### Task 2: The scheduler

**Files:**
- Create: `services/api/scripts/month/plan.py`
- Test: `services/api/tests/test_month_plan.py`

**Interfaces:**
- Consumes: `scripts.seed_dev.MACHINES`.
- Produces: `IST`; `shift_of(t) -> (shift, date)`; `boundaries(start, end) -> list[datetime]`; `Roster(start_date, days, seed)` with `.status(worker, shift, date)`, `.present(shift, date)`, `.operator(machine, t)`, `.sheet(shift, date)`; `Event(t, seq, action, args)`; `OrderSpec`; `ORDERS`; `Plan(events, end, day0, roster)`; `build_plan(end, seed=11, days=30, orders=None) -> Plan`.

The event vocabulary (what `Runner` handles, Task 3 and 4): `create_order`, `confirm_order`, `cancel_order`, `receive_lot`, `start_run`, `rework_start`, `issue_yarn`, `load_rolls`, `roll_off`, `handover`, `end_run`, `inspect`, `dispatch_create`, `dispatch_scan`, `dispatch_confirm`, `buyer_payment`, `supplier_payment`, `attendance`, `wage_period`, `breakdown`, `repair`.

- [x] **Step 1: Write the failing tests.** `services/api/tests/test_month_plan.py`:

```python
"""B9 Task 2: the scheduler's own invariants, without a database."""
import datetime as dt
from collections import defaultdict

import pytest

from scripts.month.plan import IST, LOOMS, ORDERS, Roster, boundaries, build_plan, shift_of

END = dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST)


@pytest.fixture(scope="module")
def plan():
    return build_plan(END, seed=11)


def at(day, hour, minute=0):
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=IST)


def test_a_night_shift_is_dated_by_the_day_it_starts():
    assert shift_of(at(10, 22)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 1)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 5, 59)) == ("C", dt.date(2026, 10, 10))
    assert shift_of(at(11, 6)) == ("A", dt.date(2026, 10, 11))
    assert shift_of(at(11, 14)) == ("B", dt.date(2026, 10, 11))


def test_boundaries_are_strictly_inside_the_interval():
    assert boundaries(at(10, 5), at(11, 7)) == [at(10, 6), at(10, 14), at(10, 22), at(11, 6)]
    assert boundaries(at(10, 6), at(10, 14)) == []


def test_the_roster_always_has_an_operator_in_every_shift():
    roster = Roster(dt.date(2026, 9, 11), 31, seed=3)
    for d in range(31):
        for shift in "ABC":
            assert roster.present(shift, dt.date(2026, 9, 11) + dt.timedelta(days=d))


def test_same_seed_same_plan_and_a_different_seed_differs():
    a, b, c = build_plan(END, seed=11), build_plan(END, seed=11), build_plan(END, seed=12)
    assert [(e.t, e.action, e.args) for e in a.events] == [(e.t, e.action, e.args) for e in b.events]
    assert [(e.t, e.action) for e in a.events] != [(e.t, e.action) for e in c.events]


def test_events_are_in_time_order_and_none_is_after_the_end(plan):
    keys = [(e.t, e.seq) for e in plan.events]
    assert keys == sorted(keys) and all(e.t <= END for e in plan.events)


def test_a_machine_is_never_double_booked_and_runs_open_and_close_in_order(plan):
    open_run = {}
    for e in plan.events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            assert m not in open_run, f"{m} started while a run is open at {e.t}"
            open_run[m] = e.t
        elif e.action == "handover":
            assert m in open_run, f"hand-over on {m} with no open run at {e.t}"
        elif e.action == "end_run" and m:
            assert m in open_run, f"end on {m} with no open run at {e.t}"
            del open_run[m]
        elif e.action == "roll_off":
            assert m in open_run
        elif e.action in ("issue_yarn", "load_rolls"):
            assert m in open_run


def test_a_breakdown_never_hits_a_busy_machine_and_is_repaired_or_still_down_at_the_end(plan):
    busy = set()
    down = set()
    for e in plan.events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            assert m not in down, f"{m} started a run while down at {e.t}"
            busy.add(m)
        elif e.action == "end_run" and m:
            busy.discard(m)
        elif e.action == "breakdown":
            assert m not in busy, f"{m} broke down in the middle of a run at {e.t}"
            down.add(m)
        elif e.action == "repair":
            assert m in down
            down.discard(m)


def test_every_run_names_an_operator_who_is_present_that_shift(plan):
    for e in plan.events:
        if e.action in ("start_run", "rework_start", "handover") and e.args.get("operator"):
            shift, date = shift_of(e.t)
            assert plan.roster.status(e.args["operator"], shift, date) == "present", (e.action, e.t, e.args)


def test_a_handover_always_changes_the_operator(plan):
    current = {}
    for e in plan.events:
        m = e.args.get("machine")
        if e.action in ("start_run", "rework_start") and m:
            current[m] = e.args["operator"]
        elif e.action == "handover":
            assert e.args["operator"] != current[m], (m, e.t)
            current[m] = e.args["operator"]


def test_attendance_is_marked_for_every_shift_up_to_the_end(plan):
    marked = {(e.args["date"], e.args["shift"]) for e in plan.events if e.action == "attendance"}
    day = plan.day0.date()
    while day <= END.date():
        for shift, hour in (("A", 6), ("B", 14), ("C", 22)):
            start = dt.datetime.combine(day, dt.time(hour), tzinfo=IST)
            if start <= END:
                assert (day, shift) in marked, (day, shift)
        day += dt.timedelta(days=1)


def test_weaving_starts_only_after_its_spinning_has_ended(plan):
    spin_end, spin_machine = {}, {}
    open_spin = {}
    for e in plan.events:
        if e.action == "start_run" and e.args["run_key"] and e.args["run_key"].startswith("spin:"):
            open_spin[e.args["machine"]] = e.args["run_key"]
        elif e.action == "end_run" and e.args["machine"] in open_spin:
            spin_end[open_spin.pop(e.args["machine"])] = e.t
        elif e.action == "start_run" and e.args["input_key"]:
            assert e.args["input_key"] in spin_end and spin_end[e.args["input_key"]] <= e.t


def test_a_rolls_life_runs_in_order_and_dispatch_takes_only_passed_rolls(plan):
    roll_off, loaded, inspections, rework_started = {}, {}, defaultdict(list), {}
    scanned, passed = {}, {}
    for e in plan.events:
        r = e.args.get("roll")
        if e.action == "roll_off":
            roll_off[r] = e.t
        elif e.action == "load_rolls":
            for key in e.args["rolls"]:
                assert key in roll_off and roll_off[key] <= e.t
                loaded[key] = e.t
        elif e.action == "inspect":
            assert r in loaded and loaded[r] <= e.t
            inspections[r].append((e.t, e.args["verdict"]))
            assert len(inspections[r]) <= 2
            if len(inspections[r]) == 2:
                assert inspections[r][0][1] == "rework" and r in rework_started and rework_started[r] <= e.t
            if e.args["verdict"] != "pass":
                assert e.args["defects"]
        elif e.action == "rework_start":
            assert inspections[r] and inspections[r][-1][1] == "rework"
            rework_started[r] = e.t
        elif e.action == "dispatch_scan":
            assert inspections[r][-1][1] == "pass", f"{r} dispatched without a final pass"
            assert r not in scanned
            scanned[r] = e.t
    assert scanned, "no roll was ever dispatched"


def test_a_truck_is_scanned_before_it_is_confirmed(plan):
    created, last_scan, confirmed = {}, {}, {}
    for e in plan.events:
        k = e.args.get("truck")
        if e.action == "dispatch_create":
            created[k] = e.t
        elif e.action == "dispatch_scan":
            assert k in created
            last_scan[k] = e.t
        elif e.action == "dispatch_confirm":
            assert k in last_scan and last_scan[k] <= e.t
            confirmed[k] = e.t
    assert confirmed


def test_the_orders_and_their_states(plan):
    created = [e.args["order"] for e in plan.events if e.action == "create_order"]
    assert len(created) == len(ORDERS)
    cancelled = [e.args["order"] for e in plan.events if e.action == "cancel_order"]
    assert cancelled == ["O14"]
    confirmed = {e.args["order"] for e in plan.events if e.action == "confirm_order"}
    assert "O13" not in confirmed and "O14" in confirmed          # the draft is never confirmed; the cancelled one was


def test_the_month_is_the_size_that_was_designed(plan):
    metres = sum(o.metres for o in ORDERS if o.state == "confirmed")
    assert metres == 40000


def test_three_orders_are_in_progress_at_the_end(plan):
    last_dispatch = {}
    started = set()
    for e in plan.events:
        if e.action == "start_run" and e.args["order"]:
            started.add(e.args["order"])
        if e.action == "dispatch_confirm":
            last_dispatch[e.args["order"]] = e.t
    open_orders = [o for o in started if o not in last_dispatch]
    assert len(open_orders) >= 3, open_orders


def test_the_idle_loom_is_never_planned_and_the_last_order_has_no_yarn_yet(plan):
    machines = {e.args["machine"] for e in plan.events if e.action in ("start_run", "rework_start")}
    assert "LOOM-06" not in machines and "LOOM-06" not in LOOMS
    o12 = [e for e in plan.events if e.args.get("order") == "O12"]
    assert [e.action for e in o12] == ["create_order", "confirm_order"]       # no lot, no run: the shortage story


def test_the_bad_lot_reaches_both_buyers(plan):
    lots = [e for e in plan.events if e.action == "receive_lot" and e.args["lot"] == "lot:bad"]
    assert len(lots) == 1
    issued = [e for e in plan.events if e.action == "issue_yarn" and e.args["lot"] == "lot:bad"]
    assert len(issued) == 2
    buyers = {e.args["buyer"] for e in plan.events if e.action == "create_order" and e.args["order"] in ("O7", "O8")}
    assert buyers == {"Sharma Fabrics", "Kavya Garments"}
    trucks = {e.args["truck"]: e.args["buyer"] for e in plan.events if e.action == "dispatch_create"}
    bad_rolls = {e.args["roll"] for e in plan.events if e.action == "dispatch_scan" and e.args["roll"].startswith(("roll:O7:", "roll:O8:"))}
    assert bad_rolls and {trucks[e.args["truck"]] for e in plan.events if e.action == "dispatch_scan" and e.args["roll"] in bad_rolls} == buyers
```

- [x] **Step 2: Run to verify it fails.** Expected: collection error, `scripts.month.plan` does not exist.

- [x] **Step 3: Implement.** `services/api/scripts/month/plan.py`:

```python
"""The month as a list of timed events: pure Python, no database, deterministic for a seed.

Every order is walked through the mill in creation order: spin on the first free ring frame, weave on two or three free
looms (a roll off about every 500 m), dye in batches on free dyers, inspect each roll, re-dye or mend the ones sent back,
load the passed rolls on trucks, confirm the trucks, and let the buyers pay later. Machines run round the clock and are
handed to a present operator at every shift change. Events later than `end` are dropped, so whatever is mid-way at
`end` is left open: that is the mill "right now".
"""
import datetime as dt
import math
import random
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from scripts.seed_dev import MACHINES

IST = ZoneInfo("Asia/Kolkata")
SHIFT_STARTS = (6, 14, 22)
SHIFT_OF_HOUR = {6: "A", 14: "B", 22: "C"}
RATE = {code: rate for code, _name, _stage, rate, _cost in MACHINES}
MACHINE_INDEX = {code: i for i, (code, *_rest) in enumerate(MACHINES)}
SPINNERS, DYERS = ["SPIN-01", "SPIN-02"], ["DYE-01", "DYE-02"]
LOOMS = [f"LOOM-{n:02d}" for n in range(1, 6)]                  # LOOM-06 is never planned: the idle machine
OPERATORS = {"A": ["W-001", "W-006", "W-007"], "B": ["W-008", "W-009"], "C": ["W-010", "W-011"]}
SUPPORT = ["W-002", "W-003", "W-004", "W-005", "W-012"]         # on the payroll, not running machines; marked in shift A
UNLUCKY = "W-009"                                               # a little more defective than the rest, but not flaggable
RECIPE = {                                                      # kg per metre, wastage, yarn code, supplier, cost range per kg
    "Poplin 58in": (0.12, 0.05, "30S-COT-RAW", "Vardhman Yarns", (245, 265)),
    "Twill 58in": (0.16, 0.04, "40S-PC-RAW", "Coastal Spinners", (272, 290)),
}
ODDS = {"normal": (0.88, 0.08, 0.04), "bad": (0.35, 0.40, 0.25), "loss": (0.15, 0.65, 0.20)}    # pass, rework, reject
REDYE_SHARE = {"normal": 0.5, "bad": 0.5, "loss": 0.85}         # of the reworked rolls, the share re-dyed (the rest mended by hand)
DEFECTS = {"normal": ["hole", "stain", "thread_fault"], "bad": ["thread_fault", "hole"], "loss": ["stain", "hole"]}
BREAKDOWNS = [("LOOM-06", 9, 10, 40, "belt snapped"), ("SPIN-01", 15, 11, 14, "bearing noise"),
              ("DYE-02", 22, 8, 20, "heater fault"), ("SPIN-02", 29, 20, 12, "drive belt slipping")]


def hours(x: float) -> dt.timedelta:
    return dt.timedelta(hours=x)


def minutes(x: float) -> dt.timedelta:
    return dt.timedelta(minutes=x)


def shift_of(t: dt.datetime) -> tuple[str, dt.date]:
    """The shift in effect at t and the date it is filed under (a night shift is dated by the day it starts)."""
    if 6 <= t.hour < 14:
        return "A", t.date()
    if 14 <= t.hour < 22:
        return "B", t.date()
    return "C", t.date() if t.hour >= 22 else t.date() - dt.timedelta(days=1)


def boundaries(start: dt.datetime, end: dt.datetime) -> list[dt.datetime]:
    """The shift changes strictly inside (start, end)."""
    out = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        for hour in SHIFT_STARTS:
            b = day.replace(hour=hour)
            if start < b < end:
                out.append(b)
        day += dt.timedelta(days=1)
    return out


class Roster:
    """Who is present when. Each operator pool always keeps at least one operator; support staff may be absent or half-day."""

    def __init__(self, start_date: dt.date, days: int, seed: int):
        rng = random.Random(seed * 7 + 1)
        self._status: dict[tuple[str, str, dt.date], str] = {}
        for d in range(days + 1):
            date = start_date + dt.timedelta(days=d)
            for shift, pool in OPERATORS.items():
                absent = rng.choice(pool) if len(pool) > 1 and rng.random() < 0.08 else None
                for worker in pool:
                    self._status[(worker, shift, date)] = "absent" if worker == absent else "present"
            for worker in SUPPORT:
                roll = rng.random()
                self._status[(worker, "A", date)] = "absent" if roll < 0.04 else "half_day" if roll < 0.09 else "present"

    def status(self, worker: str, shift: str, date: dt.date) -> str:
        return self._status.get((worker, shift, date), "absent")

    def present(self, shift: str, date: dt.date) -> list[str]:
        return [w for w in OPERATORS[shift] if self.status(w, shift, date) == "present"]

    def operator(self, machine: str, t: dt.datetime) -> str:
        shift, date = shift_of(t)
        pool = self.present(shift, date)
        return pool[MACHINE_INDEX[machine] % len(pool)]

    def sheet(self, shift: str, date: dt.date) -> dict[str, str]:
        workers = OPERATORS[shift] + (SUPPORT if shift == "A" else [])
        return {w: self.status(w, shift, date) for w in workers}


@dataclass(frozen=True)
class Event:
    t: dt.datetime
    seq: int
    action: str
    args: dict


@dataclass(frozen=True)
class OrderSpec:
    key: str
    buyer: str
    fabric: str
    colour: str
    metres: int
    price: int
    day: int                       # created on this day of the month, at 09:00
    deadline_days: int
    state: str = "confirmed"       # confirmed | draft | cancelled
    story: str = ""                # "" | bad | loss | late | no_yarn
    opening_lot: bool = False      # its yarn lot arrived 4 days before the month began


SHARMA, KAVYA = "Sharma Fabrics", "Kavya Garments"
ORDERS = [
    OrderSpec("O1", SHARMA, "Poplin 58in", "navy", 4000, 120, 0, 12, opening_lot=True),
    OrderSpec("O2", KAVYA, "Twill 58in", "charcoal", 3000, 150, 1, 12),
    OrderSpec("O3", SHARMA, "Poplin 58in", "white", 3500, 118, 3, 12),
    OrderSpec("O4", KAVYA, "Poplin 58in", "maroon", 2500, 110, 6, 12),
    OrderSpec("O5", SHARMA, "Twill 58in", "grey", 3000, 148, 8, 12),
    OrderSpec("O6", KAVYA, "Poplin 58in", "red", 3000, 65, 10, 12, story="loss"),
    OrderSpec("O7", SHARMA, "Poplin 58in", "sky blue", 2500, 122, 13, 12, story="bad"),
    OrderSpec("O8", KAVYA, "Poplin 58in", "teal", 2500, 118, 14, 12, story="bad"),
    OrderSpec("O9", SHARMA, "Twill 58in", "olive", 3500, 150, 17, 12),
    OrderSpec("O10", KAVYA, "Twill 58in", "black", 3000, 152, 21, 12),
    OrderSpec("O11", SHARMA, "Poplin 58in", "burgundy", 6000, 115, 26, 4, story="late"),
    OrderSpec("O12", KAVYA, "Poplin 58in", "beige", 3000, 118, 28, 10, story="no_yarn"),
    OrderSpec("O13", KAVYA, "Twill 58in", "brown", 2000, 150, 29, 10, state="draft"),
    OrderSpec("O14", SHARMA, "Poplin 58in", "cream", 2000, 118, 5, 10, state="cancelled"),
]


@dataclass
class Plan:
    events: list[Event]
    end: dt.datetime
    day0: dt.datetime
    roster: Roster
    notes: dict = field(default_factory=dict)


class Builder:
    def __init__(self, end: dt.datetime, seed: int, days: int):
        self.end = end
        self.days = days
        self.rng = random.Random(seed)
        self.day0 = (end - dt.timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        self.roster = Roster(self.day0.date() - dt.timedelta(days=5), days + 6, seed)
        self.events: list[Event] = []
        self.free = {code: self.day0 for code, *_rest in MACHINES}
        self.busy: list[tuple[str, dt.datetime, dt.datetime]] = []
        self.trucks = 0
        self.lot_kg: dict[str, float] = {}

    def at(self, day: int, hour: float = 9) -> dt.datetime:
        return self.day0 + dt.timedelta(days=day, hours=hour)

    def ev(self, t: dt.datetime, action: str, **args) -> None:
        self.events.append(Event(t, len(self.events), action, args))

    def machine_run(self, machine: str, start: dt.datetime, length_h: float, *, order: str, kind: str, run_key: str | None = None,
                    input_key: str | None = None, issue: tuple[str, float] | None = None, output_kg: float | None = None,
                    rolls: list[tuple[float, int, str]] = (), load: list[str] = (), roll: str | None = None) -> dt.datetime:
        """One machine-run: start (or rework start), hand-over at every shift change, end. Returns the end moment."""
        end = start + hours(length_h)
        operator = self.roster.operator(machine, start)
        if kind == "rework":
            self.ev(start, "rework_start", roll=roll, machine=machine, operator=operator)
        else:
            self.ev(start, "start_run", order=order, machine=machine, operator=operator, input_key=input_key, run_key=run_key)
        if issue:
            self.ev(start + minutes(5), "issue_yarn", machine=machine, lot=issue[0], qty_kg=issue[1])
        if load:
            self.ev(start + minutes(2), "load_rolls", machine=machine, rolls=list(load))
        for offset, metres, key in rolls:
            self.ev(min(start + hours(offset), end - minutes(1)), "roll_off", machine=machine, roll=key, metres=metres)
        for b in boundaries(start, end):
            self.ev(b, "handover", machine=machine, operator=self.roster.operator(machine, b))
        self.ev(end, "end_run", machine=machine, run_key=None, output_kg=output_kg)
        self.free[machine] = end
        self.busy.append((machine, start, end))
        return end

    def qc_time(self, ready: dt.datetime, bump: int = 0) -> dt.datetime:
        """The inspector works 07:00 to 13:30: the first moment at least two hours after `ready`, spread by `bump` minutes."""
        t = ready + hours(2) + minutes(7 * bump)
        if t.hour < 7:
            t = t.replace(hour=7, minute=self.rng.randint(0, 40))
        elif t.hour > 13 or (t.hour == 13 and t.minute > 30):
            t = (t + dt.timedelta(days=1)).replace(hour=7, minute=self.rng.randint(0, 40))
        return t


def _need_kg(o: OrderSpec) -> float:
    per_m, waste, *_rest = RECIPE[o.fabric]
    return round(o.metres * per_m * (1 + waste) * 2) / 2


def _split_rolls(rng: random.Random, total: int) -> list[int]:
    lengths, left = [], total
    while left > 600:
        n = rng.randint(420, 600)
        lengths.append(n)
        left -= n
    if left < 150 and lengths:
        lengths[-1] += left
    else:
        lengths.append(left)
    return lengths


def _plan_order(b: Builder, o: OrderSpec, state: dict) -> None:
    t0 = b.at(o.day, 9)
    b.ev(t0, "create_order", order=o.key, buyer=o.buyer, fabric=o.fabric, colour=o.colour, metres=o.metres, price=o.price,
         deadline_days=o.deadline_days)
    if o.state == "draft":
        return
    b.ev(t0 + minutes(10), "confirm_order", order=o.key)
    if o.state == "cancelled":
        b.ev(t0 + hours(30), "cancel_order", order=o.key)
        return
    per_m, waste, yarn, supplier, (lo, hi) = RECIPE[o.fabric]
    kg = _need_kg(o)
    if o.story == "no_yarn":
        return                                          # the yarn has not arrived: nothing can run, the shortage shows
    if o.story == "bad":
        lot = "lot:bad"
        if "bad_lot" not in state:                      # the first bad order brings the lot both bad orders draw from
            other = next(x for x in ORDERS if x.story == "bad" and x.key != o.key)
            b.ev(t0 + hours(3), "receive_lot", lot=lot, yarn=yarn, supplier=supplier,
                 qty_kg=math.ceil((kg + _need_kg(other)) * 1.05 / 10) * 10, cost_per_kg=250, order=None, challan=f"CH-BAD-{o.key}")
            state["bad_lot"] = True
    else:
        lot = f"lot:{o.key}"
        when = b.day0 - dt.timedelta(days=4) + hours(10) if o.opening_lot else t0 + hours(3)
        b.ev(when, "receive_lot", lot=lot, yarn=yarn, supplier=supplier, qty_kg=math.ceil(kg * 1.08 / 10) * 10,
             cost_per_kg=b.rng.randint(lo, hi), order=None if o.opening_lot else o.key, challan=f"CH-{o.key}")
    # spinning
    machine = min(SPINNERS, key=lambda m: b.free[m])
    start = max(t0 + hours(4), b.free[machine])
    spin_end = b.machine_run(machine, start, kg / RATE[machine] * b.rng.uniform(0.97, 1.05), order=o.key, kind="spin",
                             run_key=f"spin:{o.key}", issue=(lot, kg), output_kg=kg)
    # weaving
    looms = sorted(LOOMS, key=lambda m: b.free[m])[: 3 if o.metres > 4000 else 2]
    shares = [round(o.metres / len(looms))] * (len(looms) - 1)
    shares.append(o.metres - sum(shares))
    rolls: list[tuple[str, int, dt.datetime, str]] = []         # key, metres, ready, producing operator
    weave_end = spin_end
    for loom, share in zip(looms, shares):
        wstart = max(spin_end, b.free[loom])
        offset, plan_rolls = 0.0, []
        for i, metres in enumerate(_split_rolls(b.rng, share)):
            offset += metres / RATE[loom]
            plan_rolls.append((offset, metres, f"roll:{o.key}:{loom}:{i}"))
        end = b.machine_run(loom, wstart, share / RATE[loom], order=o.key, kind="weave", input_key=f"spin:{o.key}",
                            rolls=plan_rolls)
        weave_end = max(weave_end, end)
        for off, metres, key in plan_rolls:
            t = min(wstart + hours(off), end - minutes(1))
            rolls.append((key, metres, t, b.roster.operator(loom, t)))
    rolls.sort(key=lambda r: (r[2], r[0]))
    # dyeing, in two batches so both dyers work
    batches = [rolls[0::2], rolls[1::2]] if len(rolls) >= 4 else [rolls]
    ready_at: dict[str, dt.datetime] = {}
    for batch in batches:
        dyer = min(DYERS, key=lambda m: b.free[m])
        dstart = max(weave_end + minutes(30), b.free[dyer])
        dend = b.machine_run(dyer, dstart, sum(r[1] for r in batch) / RATE[dyer] * b.rng.uniform(0.97, 1.05), order=o.key,
                             kind="dye", load=[r[0] for r in batch])
        for r in batch:
            ready_at[r[0]] = dend
    # quality
    kind = o.story if o.story in ("bad", "loss") else "normal"
    finals: list[tuple[dt.datetime, str, str, int]] = []         # time, roll, verdict, metres
    for bump, (key, metres, _t, operator) in enumerate(rolls):
        odds = (0.78, 0.14, 0.08) if operator == UNLUCKY and kind == "normal" else ODDS[kind]
        verdict = b.rng.choices(["pass", "rework", "reject"], odds)[0]
        t1 = b.qc_time(ready_at[key], bump)
        defects = [] if verdict == "pass" else [(b.rng.choice(DEFECTS[kind]), b.rng.randint(1, 3))]
        b.ev(t1, "inspect", roll=key, verdict=verdict, defects=defects)
        if verdict != "rework":
            finals.append((t1, key, verdict, metres))
            continue
        if b.rng.random() < REDYE_SHARE[kind]:
            dyer = min(DYERS, key=lambda m: b.free[m])
            rstart = max(t1 + hours(3), b.free[dyer])
            rend = b.machine_run(dyer, rstart, metres / RATE[dyer] * b.rng.uniform(0.97, 1.05), order=o.key, kind="rework", roll=key)
        else:
            rstart = (t1 + hours(3) + dt.timedelta(days=1)).replace(hour=7, minute=0)
            rend = rstart + hours(b.rng.uniform(2.5, 5.0))
            b.ev(rstart, "rework_start", roll=key, machine=None, operator=b.roster.present("A", rstart.date())[0])
            b.ev(rend, "end_run", machine=None, run_key=f"rework:{key}", output_kg=None)
        again = b.rng.choices(["pass", "reject"], [0.6, 0.4] if kind == "loss" else [0.8, 0.2])[0]
        t2 = b.qc_time(rend, bump)
        b.ev(t2, "inspect", roll=key, verdict=again, defects=[] if again == "pass" else [(b.rng.choice(DEFECTS[kind]), 1)])
        finals.append((t2, key, again, metres))
    # trucks: the passed rolls, one truck (two for a big order), the morning after the last of them is ready
    passed = sorted((f for f in finals if f[2] == "pass"), key=lambda f: f[0])
    groups = [passed] if len(passed) < 8 else [passed[: len(passed) // 2], passed[len(passed) // 2:]]
    for group in groups:
        if not group:
            continue
        b.trucks += 1
        truck = f"truck:{b.trucks}"
        t = (group[-1][0] + dt.timedelta(days=1)).replace(hour=10, minute=0)
        b.ev(t, "dispatch_create", truck=truck, order=o.key, buyer=o.buyer, vehicle=f"KA-01-AB-{1000 + b.trucks}")
        for i, (_ft, key, _v, _m) in enumerate(group):
            b.ev(t + minutes(2 + 2 * i), "dispatch_scan", truck=truck, roll=key)
        done = t + minutes(10 + 2 * len(group))
        b.ev(done, "dispatch_confirm", truck=truck, order=o.key)
        state.setdefault("trucks", []).append((truck, o.key, done))


def _plan_money(b: Builder, state: dict) -> None:
    for n, (truck, order, done) in enumerate(state.get("trucks", [])):
        fraction = 0.5 if n == 4 else 1.0                       # the fifth truck is only half paid
        b.ev((done + dt.timedelta(days=b.rng.randint(12, 25))).replace(hour=11, minute=0), "buyer_payment", truck=truck,
             fraction=fraction, reference=f"NEFT-{7000 + n}")
    if b.days >= 30:
        for key in ("O2", "O3"):
            b.ev(b.at(14 if key == "O2" else 16, 11), "supplier_payment", lot=f"lot:{key}", fraction=1.0, reference=f"PAY-{key}")
        d0 = b.day0.date()
        b.ev(b.at(15, 18), "wage_period", start=d0, end=d0 + dt.timedelta(days=13), fraction=1.0)
        b.ev(b.at(29, 18), "wage_period", start=d0 + dt.timedelta(days=14), end=d0 + dt.timedelta(days=27), fraction=0.6)


def _plan_attendance(b: Builder) -> None:
    day = b.day0.date()
    while day <= b.end.date():
        for shift, hour in (("A", 6), ("B", 14), ("C", 22)):
            b.ev(dt.datetime.combine(day, dt.time(hour), tzinfo=IST), "attendance", date=day, shift=shift,
                 entries=b.roster.sheet(shift, day))
        day += dt.timedelta(days=1)


def _plan_breakdowns(b: Builder) -> None:
    for machine, day, hour, length_h, reason in BREAKDOWNS:
        start = b.at(day, hour)
        while any(m == machine and s < start + hours(length_h) and e > start for m, s, e in b.busy):
            start += hours(6)
        b.ev(start, "breakdown", machine=machine, reason=reason)
        b.ev(start + hours(length_h), "repair", machine=machine)


def build_plan(end: dt.datetime, seed: int = 11, days: int = 30, orders: list[OrderSpec] | None = None) -> Plan:
    b = Builder(end, seed, days)
    state: dict = {}
    for o in sorted(orders if orders is not None else ORDERS, key=lambda x: (x.day, x.key)):
        _plan_order(b, o, state)
    _plan_money(b, state)
    _plan_attendance(b)
    if days >= 30:
        _plan_breakdowns(b)
    events = sorted((e for e in b.events if e.t <= end), key=lambda e: (e.t, e.seq))
    return Plan(events=events, end=end, day0=b.day0, roster=b.roster, notes={"trucks": state.get("trucks", [])})
```

- [x] **Step 4: Run it.** `uv run python -m pytest -p no:warnings -o addopts= tests/test_month_plan.py -q`. **Expect some failures on the first run: this code has never been run.** Fix by finding the real cause each time (systematic-debugging), never by weakening a test; record each real finding in the Status line. Likely first findings: the manual-rework `end_run` carries `run_key` while machine runs carry `machine`, which the first test's state machine must handle (`m` is None for a manual rework: skip it there); events at identical times needing the `seq` order; an order whose roll count makes `_split_rolls` return a tiny last roll.
- [x] **Step 5: Tune the numbers until every story test passes** (order sizes, deadlines, odds in `ODDS`), recording the final values in the Status line. The in-progress test, the bad-lot test and the late order are the ones most likely to need it.
- [x] **Step 6: Mutation checks:** let a machine start while another run is open (the double-booking test fails); give a handover the same operator (the operator-change test fails); schedule `dispatch_scan` for a rolled-over `rework` roll (the dispatch test fails); remove the roster's at-least-one-present rule (the roster test fails); let an event through after `end` (the time-order test fails).
- [x] **Step 7: Full suite twice;** both green.
- [x] **Step 8: Commit.**

```bash
git add services/api/scripts/month/plan.py services/api/tests/test_month_plan.py
git commit -m "Add the month scheduler: orders walked through the mill in timed events"
```

---

### Task 3: A throwaway database, then orders through to rolls played through the real services

**Files:**
- Create: `services/api/scripts/month/database.py`, `services/api/scripts/month/runner.py` (the first half: orders, lots, runs, hand-overs, rolls)
- Test: `services/api/tests/test_month_build.py` (the database refusals and the first month test)

**Why a real database here.** The usual test fixture keeps one outer transaction open for the whole test, so a database default `now()` (every `created_at`, a lot's `received_at`) is frozen at the start of the test and the timestamp mover cannot be proved there. The month tests therefore build into their own database, `everest_month_test`, made fresh once per test module and dropped afterwards.

**Interfaces:**
- Consumes (Task 1 and 2): `SimClock`, `build_plan`, `Event`.
- Produces: `ALLOWED`, `database_name(url)`, `refuse_unless_allowed(url)`, `recreate(url)`, `drop(url)`, `migrate(url)`; `Runner(db, clock)`, `Runner.play(events, only=None)`, `RunnerError`, and the maps `.order`, `.lot`, `.roll`, `.run`, `.open`, `.truck`.

- [x] **Step 1: Write the failing tests.** `services/api/tests/test_month_build.py`:

```python
"""B9 Task 3 to 6: a small month, end to end, through the real services, in its own throwaway database."""
import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import Order, ProductionRun, Roll, YarnLot
from scripts import seed_dev
from scripts.month import database
from scripts.month.clock import SimClock
from scripts.month.database import ALLOWED, database_name, refuse_unless_allowed
from scripts.month.plan import IST, ORDERS, build_plan
from scripts.month.runner import Runner

URL = "postgresql+psycopg://localhost:5432/everest_month_test"
END = dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST)
FIRST_HALF = {"create_order", "confirm_order", "cancel_order", "receive_lot", "issue_yarn", "start_run", "handover", "end_run",
              "roll_off", "load_rolls"}


@pytest.mark.parametrize("url", ["postgresql+psycopg://localhost:5432/everest", "postgresql+psycopg://localhost/everest_test",
                                 "postgresql+psycopg://localhost/postgres", "postgresql+psycopg://localhost/everest_month2"])
def test_any_other_database_is_refused(url):
    with pytest.raises(SystemExit):
        refuse_unless_allowed(url)


def test_the_two_allowed_names_pass():
    for name in ALLOWED:
        refuse_unless_allowed(f"postgresql+psycopg://localhost:5432/{name}")
    assert database_name("postgresql+psycopg://u:p@host:5432/everest_month?x=1") == "everest_month"


def test_recreate_and_drop_refuse_a_wrong_name_before_connecting():
    for action in (database.recreate, database.drop):
        with pytest.raises(SystemExit):
            action("postgresql+psycopg://localhost:5432/everest")


@pytest.fixture(scope="module")
def built():
    """Three orders over twelve days, played through the real services into a fresh `everest_month_test`."""
    database.recreate(URL)
    database.migrate(URL)
    engine = create_engine(URL)
    db = Session(engine)
    plan = build_plan(END, seed=11, days=12, orders=ORDERS[:3])
    clock = SimClock(db, END)
    with clock.installed():
        with clock.at(plan.day0 - dt.timedelta(days=6)):
            seed_dev.seed_all(db)
        runner = Runner(db, clock)
        runner.play(plan.events, only=FIRST_HALF)
    yield plan, clock, runner, db
    db.close()
    engine.dispose()
    database.drop(URL)


def test_orders_yarn_runs_and_rolls_are_made_by_the_real_services_and_no_timestamp_leaks(built):
    plan, clock, runner, db = built
    assert db.scalar(select(func.count()).select_from(Order)) == 3
    assert db.scalar(select(func.count()).select_from(YarnLot)) == 3
    assert db.scalar(select(func.count()).select_from(ProductionRun)) > 6          # spin, weave, dye and the hand-overs
    assert db.scalar(select(func.count()).select_from(Roll)) >= 6
    assert clock.leaks() == [], clock.leaks()                                       # defaults, db_now and datetime.now all moved
    first = db.scalar(select(func.min(ProductionRun.started_at)))
    last = db.scalar(select(func.max(ProductionRun.started_at)))
    assert plan.day0 <= first and last <= END and (last - first) > dt.timedelta(hours=24)


def test_a_lots_received_at_and_bill_dates_are_simulated_not_real(built):
    plan, clock, runner, db = built
    for lot in db.scalars(select(YarnLot)):
        assert lot.received_at <= END
        assert lot.bill.bill_date == lot.received_at.astimezone(IST).date()
        assert lot.bill.due_date == lot.bill.bill_date + dt.timedelta(days=30)
```

- [x] **Step 2: Run to verify it fails.** Expected: `scripts.month.database` does not exist.

- [x] **Step 3: Implement `services/api/scripts/month/database.py`:**

```python
"""Making, migrating and dropping the month's own database, and refusing every other name."""
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[2]
ALLOWED = {"everest_month", "everest_month_test"}


def database_name(url: str) -> str:
    return make_url(url).database or ""


def refuse_unless_allowed(url: str) -> None:
    if database_name(url) not in ALLOWED:
        sys.exit(f"Refused: this builds only {sorted(ALLOWED)}, not {database_name(url)!r}. Your own database is never touched.")


def _admin(url: str):
    return create_engine(make_url(url).set(database="postgres"), isolation_level="AUTOCOMMIT")


def drop(url: str) -> None:
    refuse_unless_allowed(url)
    admin = _admin(url)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{database_name(url)}" WITH (FORCE)'))
    admin.dispose()


def recreate(url: str) -> None:
    refuse_unless_allowed(url)
    drop(url)
    admin = _admin(url)
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{database_name(url)}"'))
    admin.dispose()


def migrate(url: str) -> None:
    refuse_unless_allowed(url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
```

  And the first half of `services/api/scripts/month/runner.py`:

```python
"""Plays a month plan through the real service functions, one event at a time, inside the simulated clock."""
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Buyer, Dispatch, FabricType, Invoice, Shift, Supplier, SupplierBill, User, Worker, YarnLot, YarnType
from app.modules.floor import rolls as floor_rolls
from app.modules.floor import schemas as fs
from app.modules.floor import service as floor
from app.modules.orders import schemas as os_
from app.modules.orders import service as orders
from app.modules.store import schemas as ss
from app.modules.store import service as store
from scripts.month.clock import SimClock
from scripts.month.plan import Event


class RunnerError(RuntimeError):
    pass


class Runner:
    def __init__(self, db: Session, clock: SimClock):
        self.db, self.clock = db, clock
        self.users = {u.username: u for u in db.scalars(select(User))}
        self.worker = {w.code: w.id for w in db.scalars(select(Worker))}
        self.buyer = {b.name: b.id for b in db.scalars(select(Buyer))}
        self.fabric = {f.name: f.id for f in db.scalars(select(FabricType))}
        self.yarn = {y.code: y.id for y in db.scalars(select(YarnType))}
        self.supplier = {s.name: s.id for s in db.scalars(select(Supplier))}
        self.shift = {s.name: s.id for s in db.scalars(select(Shift))}
        self.order: dict[str, str] = {}          # plan key -> order code
        self.lot: dict[str, str] = {}            # plan key -> lot code
        self.roll: dict[str, str] = {}           # plan key -> roll code
        self.run: dict[str, int] = {}            # run key -> the first run's id (a weaving run's input)
        self.open: dict[str, int] = {}           # machine code -> its open run id
        self.truck: dict[str, str] = {}          # plan key -> dispatch code
        self.hand_run: dict[str, int] = {}       # roll key -> its hand-mending run id
        self.count = 0

    def play(self, events: list[Event], only: set[str] | None = None) -> None:
        for e in events:
            if only is not None and e.action not in only:
                continue
            handler = getattr(self, f"do_{e.action}")
            try:
                with self.clock.at(e.t):
                    handler(**e.args)
            except Exception as exc:
                self.db.rollback()
                raise RunnerError(f"{e.t:%d %b %H:%M} {e.action} {e.args}: {exc}") from exc
            self.count += 1

    # ---- orders and yarn
    def do_create_order(self, order, buyer, fabric, colour, metres, price, deadline_days):
        created = orders.create_order(self.db, os_.OrderIn(
            buyer_id=self.buyer[buyer], fabric_type_id=self.fabric[fabric], colour=colour, qty_metres=metres,
            price_per_metre=price, deadline=self.clock.now.date() + dt.timedelta(days=deadline_days)))
        self.order[order] = created.code

    def do_confirm_order(self, order):
        orders.confirm_order(self.db, self.order[order])

    def do_cancel_order(self, order):
        orders.cancel_order(self.db, self.order[order])

    def do_receive_lot(self, lot, yarn, supplier, qty_kg, cost_per_kg, order, challan):
        body = ss.LotReceiveIn(yarn_type_id=self.yarn[yarn], supplier_id=self.supplier[supplier], qty_kg=qty_kg,
                               cost_per_kg=cost_per_kg, challan_no=challan,
                               intended_order_code=self.order[order] if order else None)
        self.lot[lot] = store.receive_lot(self.db, self.users["store"], body).lot_code

    def do_issue_yarn(self, machine, lot, qty_kg):
        store.issue_yarn(self.db, self.users["supervisor"], ss.IssueIn(lot_code=self.lot[lot], run_id=self.open[machine], qty_kg=qty_kg))

    # ---- runs
    def do_start_run(self, order, machine, operator, input_key, run_key):
        run = floor.start_run(self.db, fs.RunStartIn(order_code=self.order[order], machine_code=machine,
                                                    operator_worker_id=self.worker[operator],
                                                    input_run_id=self.run[input_key] if input_key else None))
        self.open[machine] = run.id
        if run_key:
            self.run[run_key] = run.id

    def do_handover(self, machine, operator):
        self.open[machine] = floor.handover(self.db, self.open[machine], fs.HandoverIn(operator_worker_id=self.worker[operator])).id

    def do_end_run(self, machine, run_key, output_kg):
        run_id = self.open.pop(machine) if machine else self.hand_run.pop(run_key.removeprefix("rework:"))
        floor.end_run(self.db, run_id, fs.RunEndIn(output_kg=output_kg))

    def do_roll_off(self, machine, roll, metres):
        self.roll[roll] = floor_rolls.roll_off(self.db, self.open[machine], fs.RollOffIn(metres=metres)).code

    def do_load_rolls(self, machine, rolls):
        floor_rolls.load_rolls(self.db, self.open[machine], fs.LoadRollsIn(roll_codes=[self.roll[r] for r in rolls]))
```

- [x] **Step 4: Run it.** Expect real findings on the first run (a service refusing a step, or a default-`now()` value the mover missed); fix the cause in the plan, the runner or the mover, never by skipping a step or loosening a test, and record each finding in the Status line. Likely first findings: `seed_all` committing in a way the mover window misses; `do_create_order` needing the swapped `today_ist`; the opening lot received before any order exists.
- [x] **Step 5: Full suite twice;** green. Hritwik's server check.
- [x] **Step 6: Commit.**

```bash
git add services/api/scripts/month/database.py services/api/scripts/month/runner.py services/api/tests/test_month_build.py
git commit -m "Play orders, yarn, runs and rolls through the real services under the simulated clock"
```

---

### Task 4: QC, rework, dispatch, money, attendance and breakdowns

**Files:**
- Modify: `services/api/scripts/month/runner.py` (the second half)
- Test: `services/api/tests/test_month_build.py` (a longer mini month)

**Interfaces:**
- Consumes: Task 3's `Runner`; the services `qc`, `dispatch`, `money`, `people` and `floor`.
- Produces: the remaining `do_*` handlers: `do_inspect`, `do_rework_start`, `do_dispatch_create`, `do_dispatch_scan`, `do_dispatch_confirm`, `do_buyer_payment`, `do_supplier_payment`, `do_attendance`, `do_wage_period`, `do_breakdown`, `do_repair`.

- [x] **Step 1: Write the failing test** (added to `test_month_build.py`, using a second module-scoped fixture `built_all` like `built` but playing every event, `runner.play(plan.events)`): assert that inspections, at least one dispatch, an invoice, attendance rows and at least one rework run exist, that no roll is dispatched without a final pass, that `clock.leaks() == []`, that `receivables` and `payables` return rows, and that every attendance row's date is within the simulated month. (If 12 days still ends before the first dispatch, raise `days` until it does and record the number; a buyer payment only appears once a truck is old enough, so assert it only if the plan has one.)
- [x] **Step 2: Run to verify it fails.** Expected: `AttributeError: 'Runner' object has no attribute 'do_inspect'`.
- [x] **Step 3: Implement.** Append to `runner.py` (imports added at the top: `from app.modules.dispatch import schemas as ds, service as dispatch`, `from app.modules.money import schemas as ms, service as money`, `from app.modules.people import router as people, schemas as ps, service as people_service`, `from app.modules.qc import schemas as qs, service as qc`):

```python
    # ---- quality
    def do_inspect(self, roll, verdict, defects):
        qc.record_inspection(self.db, self.users["qc"], qs.InspectionIn(
            roll_code=self.roll[roll], verdict=verdict, defects=[qs.DefectIn(defect_type=t, count=n) for t, n in defects]))

    def do_rework_start(self, roll, machine, operator):
        run = qc.start_rework(self.db, qs.ReworkIn(roll_code=self.roll[roll], machine_code=machine,
                                                  operator_worker_id=self.worker[operator]))
        if machine:
            self.open[machine] = run.id
        else:
            self.hand_run[roll] = run.id

    # ---- dispatch and money
    def do_dispatch_create(self, truck, order, buyer, vehicle):
        self.truck[truck] = dispatch.create_dispatch(self.db, ds.DispatchIn(buyer_id=self.buyer[buyer], vehicle_no=vehicle)).code

    def do_dispatch_scan(self, truck, roll):
        dispatch.scan_roll(self.db, self.truck[truck], ds.ScanIn(roll_code=self.roll[roll]))

    def do_dispatch_confirm(self, truck, order):
        dispatch.confirm_dispatch(self.db, self.truck[truck])

    def _invoice(self, truck) -> Invoice:
        d = self.db.scalar(select(Dispatch).where(Dispatch.code == self.truck[truck]))
        return self.db.scalar(select(Invoice).where(Invoice.dispatch_id == d.id))

    def do_buyer_payment(self, truck, fraction, reference):
        invoice = self._invoice(truck)
        money.record_buyer_payment(self.db, ms.BuyerPaymentIn(
            invoice_no=invoice.invoice_no, amount=round(float(invoice.total_amount) * fraction, 2),
            received_on=self.clock.now.date(), reference=reference))

    def do_supplier_payment(self, lot, fraction, reference):
        bill = self.db.scalar(select(SupplierBill).join(YarnLot, YarnLot.id == SupplierBill.yarn_lot_id)
                              .where(YarnLot.lot_code == self.lot[lot]))
        money.record_supplier_payment(self.db, ms.SupplierPaymentIn(
            bill_id=bill.id, amount=round(float(bill.amount) * fraction, 2), paid_on=self.clock.now.date(), reference=reference))

    # ---- people
    def do_attendance(self, date, shift, entries):
        people.mark_attendance(ps.AttendanceIn(date=date, shift_id=self.shift[shift], entries=[
            ps.AttendanceEntry(worker_id=self.worker[w], status=s) for w, s in entries.items()]),
            db=self.db, user=self.users["supervisor"])

    def do_wage_period(self, start, end, fraction):
        for row in people_service.wage_rows(self.db, start, end):
            owed = round(float(row.owed) * fraction, 2)
            if owed > 0:
                people.pay_wages(ps.WagePaymentIn(worker_id=row.worker.id, period_start=start, period_end=end, amount=owed,
                                                 paid_at=self.clock.now.date()), db=self.db)

    # ---- machines
    def do_breakdown(self, machine, reason):
        floor.breakdown(self.db, machine, fs.BreakdownIn(reason=reason))

    def do_repair(self, machine):
        floor.repair(self.db, machine)
```

  Verify at execution: `WageRow`'s fields (the plan assumes `.owed` and `.worker.id`; read `people/schemas.py`), the router function's exact parameter names (`mark_attendance(body, db, user)` takes `body`, not positional: use keywords), `qs.DefectIn`'s `ai_detected` default, and that `record_inspection` needs `user.worker` (the `qc` user is linked to W-002).
- [x] **Step 4: Run it.** Expect real findings; fix the cause. A service refusing a payment as "before the invoice date" or "future-dated" means the payment day and the simulated date disagree: check `today_ist` is swapped inside the step.
- [x] **Step 5: Full suite twice;** green. Hritwik's server check.
- [x] **Step 6: Commit.**

```bash
git add services/api/scripts/month/runner.py services/api/tests/test_month_build.py
git commit -m "Play quality checks, rework, dispatch, money, attendance and breakdowns through the real services"
```

---

### Task 5: The stories and the audit

**Files:**
- Create: `services/api/scripts/month/audit.py`
- Test: `services/api/tests/test_month_build.py` (the mini month's audit, structure only, on the `built_all` fixture)

**Interfaces:**
- Consumes: the finished database; the endpoint functions `costing.router.month_report(month, db)` and `order_cost(order_code, db)`, `insights.router.late_orders(db)`, `shortages(db)`, `root_causes(db)`, `store.router.lot_recall(lot_code, db)`, `money.service.receivables(db)` and `payables(db)`, `floor.board`, `qc.service.queue(db)`, `portal.service`.
- Produces: `Check(name, ok, detail)`; `audit(db, clock, plan=None, full=True) -> list[Check]`; `report(checks) -> str`.

- [x] **Step 1: Write the failing tests.** In `test_month_build.py`: `audit(db, clock, full=False)` on the mini month returns checks that are all `ok` (structure only: no leaks, every attendance-covered run, the yarn ledger equals receipts minus issues for every lot, the month report has no "not covered by attendance" warning, receivables and payables load); and a unit test that a check fails when it should: a database with a timestamp later than the end gives a failing `leaks` check.
- [x] **Step 2: Run to verify it fails.** Expected: `scripts.month.audit` does not exist.
- [x] **Step 3: Implement `audit.py`.** The full list (`full=True`), each a function returning a `Check` and each reading through the real endpoint functions, with an independent SQL figure where noted:
  1. `leaks`: `clock.leaks() == []`.
  2. `ledger`: for every lot, on-hand from the stock endpoint equals receipts minus issues plus returns summed in SQL.
  3. `month_report`: for the month of the end date and the previous month, no warning contains "not covered"; invoiced total equals `SELECT sum(total_amount) FROM invoices WHERE issued_at` in that month (independent SQL, to the paisa).
  4. `order_cost`: one finished order's yarn cost equals the sum over its issues of kg × cost per kg in SQL.
  5. `bad_lot`: `root_causes` has a flagged `yarn_lot` row for the bad lot's code and no flagged `weaving_operator` row for `W-009`; `lot_recall` of the bad lot reaches both buyers and at least one dispatched truck.
  6. `loss_order`: `order_cost("O6's code")` has `profit < 0` and `parts.rework` above 0.
  7. `late_order`: `late_orders` contains O11's code with `days_late > 0` and a bottleneck stage.
  8. `low_yarn`: `shortages` contains the cotton yarn type with `suggested_kg > 0` and a supplier.
  9. `machines`: the floor board has at least one machine of each status (running, idle, down), the month report's machine rows show LOOM-06 with more down than run hours, and the QC queue has `awaiting_qc > 0`.
  10. `money`: `payables` has at least one `overdue` bill, `receivables` has at least one invoice with `0 < paid < total` and at least two with `paid == 0`; one dispatch is still `loading`.
  11. `portal`: the `buyer` user sees only its own orders (every code returned belongs to its buyer in SQL).
  12. `mix`: reported, not asserted: the overall verdict mix and the counts of orders, lots, rolls, runs, inspections.
  Output: `report(checks)` prints one line per check, `PASS` or `FAIL`, with the detail.
  Verify at execution: the field names above against the schemas (`MonthReport.profit`, `RecallOut`, `MachineMonth`), and adjust the audit, never loosen a threshold.
- [x] **Step 4: Run it.** Expected: the mini-month audit passes. The full audit is first run in Task 7.
- [x] **Step 5: Full suite twice;** green.
- [x] **Step 6: Commit.**

```bash
git add services/api/scripts/month/audit.py services/api/tests/test_month_build.py
git commit -m "Add the audit that proves each story shows through the real endpoints"
```

---

### Task 6: The entry point, the end-moment rule, the seed emails and the npm script

**Files:**
- Create: `services/api/scripts/build_month.py`
- Modify: `services/api/scripts/seed_dev.py` (two fake buyer emails), `package.json` (`db:month`)
- Test: `services/api/tests/test_month_build.py` (the end-moment rule; an end-to-end build through the entry point)

**Interfaces:**
- Consumes: `scripts/month/database.py` (Task 3), `plan`, `runner`, `audit`.
- Produces: `choose_end(now) -> datetime`, `build_month(url, end=None, days=30, orders=None, seed=11, full=True, keep=True) -> list[Check]`, `main()`.

- [x] **Step 1: Write the failing tests** (added to `test_month_build.py`):

```python
from scripts.build_month import build_month, choose_end


def test_the_end_is_the_hour_before_now_rounded_down():
    now = dt.datetime(2026, 10, 11, 3, 40, tzinfo=IST)
    assert choose_end(now) == dt.datetime(2026, 10, 11, 2, 0, tzinfo=IST)
    assert choose_end(now) <= now - dt.timedelta(hours=1)


def test_a_month_that_would_end_after_the_real_clock_is_refused():
    with pytest.raises(SystemExit):
        build_month(URL, end=dt.datetime.now(IST) + dt.timedelta(hours=2), days=3, orders=ORDERS[:1], full=False)


def test_a_small_month_builds_end_to_end_through_the_entry_point_and_audits_clean():
    checks = build_month(URL, days=12, orders=ORDERS[:3], full=False, keep=False)
    assert checks and all(c.ok for c in checks), [c for c in checks if not c.ok]
```

- [x] **Step 2: Run to verify it fails.** Expected: `scripts.build_month` does not exist.
- [x] **Step 3: Implement `services/api/scripts/build_month.py`:**

```python
"""Builds `everest_month`: 30 days of mill history, ending an hour before now, through the real services.

    npm run db:month         (from the repository root)

It creates the database itself (dropping and recreating only that one), migrates it, loads the starter data, plays the
month and prints the audit. It refuses any other database name, so `everest` can never be touched.
"""
import datetime as dt
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts import seed_dev
from scripts.month import database
from scripts.month.audit import Check, audit, report
from scripts.month.clock import SimClock
from scripts.month.plan import IST, build_plan
from scripts.month.runner import Runner

DEFAULT_URL = "postgresql+psycopg://localhost:5432/everest_month"
SAFETY_GAP = dt.timedelta(minutes=30)


def choose_end(now: dt.datetime) -> dt.datetime:
    """The simulated month ends the hour before now, rounded down: every real timestamp is then later than every simulated one."""
    return now.astimezone(IST).replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=1)


def build_month(url: str, end: dt.datetime | None = None, days: int = 30, orders=None, seed: int = 11, full: bool = True,
                keep: bool = True) -> list[Check]:
    database.refuse_unless_allowed(url)
    now = dt.datetime.now(IST)
    end = end or choose_end(now)
    if end > now - SAFETY_GAP:
        sys.exit(f"Refused: the simulated month would end at {end:%d %b %H:%M}, too close to or after the real clock "
                 f"({now:%d %b %H:%M}); real and simulated timestamps would be indistinguishable.")
    database.recreate(url)
    database.migrate(url)
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            plan = build_plan(end, seed=seed, days=days, orders=orders)
            clock = SimClock(db, end)
            with clock.installed():
                with clock.at(plan.day0 - dt.timedelta(days=6)):
                    seed_dev.seed_all(db)
                runner = Runner(db, clock)
                runner.play(plan.events)
            return audit(db, clock, runner=runner, full=full)
    finally:
        engine.dispose()
        if not keep:
            database.drop(url)


def main() -> None:
    url = os.environ.get("MONTH_DATABASE_URL", DEFAULT_URL)
    checks = build_month(url)
    print(report(checks))
    sys.exit(0 if all(c.ok for c in checks) else 1)


if __name__ == "__main__":
    main()
```

  `seed_dev.py`: give the two buyers `email="accounts@sharmafabrics.example"` and `"orders@kavyagarments.example"` (read the `Buyer` model for the column name first; if there is none, stop and say so). `package.json`: `"db:month": "uv run --directory services/api python -m scripts.build_month"`.
- [x] **Step 4: Run it.** Expected: the end-moment rule and the refusal pass; the end-to-end mini build passes (about a minute).
- [x] **Step 5: Full suite twice;** green; `test_committed_contract_matches_the_code` untouched; `git status` shows no change under `app/`.
- [x] **Step 6: Commit.**

```bash
git add services/api/scripts/build_month.py services/api/scripts/seed_dev.py package.json services/api/tests/test_month_build.py
git commit -m "Add the month build command, the end-moment rule and the buyer emails"
```

---

### Task 7: Build the real month, check it, close out

**Files:** modify this plan; create `docs/demo.md`; update `docs/plans/README.md`, `docs/specs/2026-10-11-month-simulation-design.md`, the team note, memory.

- [x] **Step 1: Ports and databases.** `lsof -nP -iTCP:8000 -iTCP:3000 -sTCP:LISTEN` (note what is running, touch nothing); `psql -l` (note `everest`).
- [x] **Step 2: Build.** `npm run db:month`. Expect the first full run to fail the audit on at least one story. For each failing check find the real cause (the data, not the audit): tune `ODDS`, order sizes, deadlines and the bad-lot quantities in `plan.py`, re-run, and record every change and why in the Status line. The audit is never loosened.
- [x] **Step 3: Independent recalculation.** For three figures not already in the audit (the month's wages earned from attendance, one order's machine cost from run hours times the machine rates, the number of rolls per verdict) recompute from raw SQL and compare with the endpoints to the paisa.
- [x] **Step 4: Run the backend against it.** `cd services/api && DATABASE_URL=postgresql+psycopg://localhost:5432/everest_month uv run --group ml uvicorn app.main:app --host 127.0.0.1 --port 8123`; with a Python client log in as `owner`, `accountant`, `supervisor`, `qc`, `dispatch` and `buyer` (password `everest123`) and read the main screens' endpoints (`/api/floor`, `/api/orders`, `/api/qc/queue`, `/api/reports/month` for both months, `/api/insights/*`, `/api/money/*`, `/api/portal/orders`): every role gets 200 and plausible figures; record the headline numbers (orders, rolls, invoiced, profit, paid, owed) for `docs/demo.md`. Stop the server.
- [x] **Step 5: Hritwik's side.** Confirm `everest` is untouched (`select count(*) from orders` still 3, the same three codes) and that nothing listens on 8123; if his servers run, `GET /api/health` answers.
- [x] **Step 6: `docs/demo.md`.** The command to build; how to run the app against `everest_month` for macOS or Linux (`DATABASE_URL=... npm run dev`) and for Windows PowerShell (`$env:DATABASE_URL="..."; npm run dev`); the logins; the real numbers from Step 4; for each story the page to open and what to see. Header with summary and date.
- [x] **Step 7: Close out.** Mark B9 done in this plan's Status line and in `docs/plans/README.md` (rows B9 and R3); fold the corrections table into the spec (stories, sizes, no buyer-invoice due date, opening lot, no `dev:month`); a note to Ridanshi at the top of `docs/HRITWIK_TEAM_NOTES.md` (what exists, the command, `everest_month`, the two buyer emails, the numbers, the pages to look at, that nobody has looked at the screens in a browser); update the project memory; authorship scan of the staged changes; commit.

```bash
git add docs services/api package.json
git commit -m "Close B9: a simulated month of mill history, built and audited through the real services"
```

---

## Done when

- The full backend suite is green twice; the scheduler passes its invariants over its seed; every mutation listed in Tasks 1 and 2 makes a test fail.
- `npm run db:month` builds `everest_month` and the whole audit prints PASS, including the independent SQL recalculations.
- `everest` is byte-for-byte what it was (three orders), and nothing under `app/` or `contracts/` changed.
- `docs/demo.md` states the real numbers; the spec, the plan, the plan index, the team note and the memory are current.
