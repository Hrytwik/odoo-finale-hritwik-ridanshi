"""B9 Task 1: the simulated clock moves real timestamps written inside a step to the simulated moment, and nothing else.

These tests run inside the usual rolled-back test transaction, where a database default `now()` is frozen at the start of
the test. They therefore write their "real" timestamps explicitly with `clock_timestamp()` inside the step. The default-now
columns are proved in Task 3 on a real throwaway database."""
import datetime as dt
import time

from sqlalchemy import func, select, text

from app.core import clock as core_clock
from app.modules.orders import service as orders_service
from scripts.month.clock import SimClock, timestamp_columns
from tests.factories import make_machine, make_order, make_run

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
    assert new.confirmed_at == MOMENT                                      # exactly the planned moment, not a few ms after it
    assert old.confirmed_at == old_value


def test_two_values_written_in_one_step_become_the_same_moment(db):
    """A simulated step is instantaneous: a hand-over planned for 14:00:00 must not land at 14:00:00.012."""
    clock = SimClock(db, END)
    first, second = make_order(db), make_order(db)
    with clock.at(MOMENT):
        db.execute(text("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = :i"), {"i": first.id})
        time.sleep(0.05)
        db.execute(text("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = :i"), {"i": second.id})
    db.expire_all()
    assert first.confirmed_at == second.confirmed_at == MOMENT


def test_one_statement_may_move_two_columns_of_a_row_without_breaking_a_check(db):
    """production_runs has CHECK ended_at >= started_at; both columns are real in this step and both are moved."""
    clock = SimClock(db, END)
    order = make_order(db)
    run = make_run(db, order, make_machine(db, stage="spinning"))
    with clock.at(MOMENT):
        db.execute(text("UPDATE production_runs SET started_at = clock_timestamp() WHERE id = :i"), {"i": run.id})
        time.sleep(0.02)
        db.execute(text("UPDATE production_runs SET ended_at = clock_timestamp() WHERE id = :i"), {"i": run.id})
    db.expire_all()
    assert run.started_at == run.ended_at == MOMENT


def test_an_older_value_in_the_same_row_stays_put(db):
    """The hand-over case: a run's start was set in an earlier step, its end is written now. Only the end may move."""
    clock = SimClock(db, END)
    run = make_run(db, make_order(db), make_machine(db, stage="spinning"))
    old_start = dt.datetime(2026, 9, 15, 6, 0, tzinfo=IST)
    db.execute(text("UPDATE production_runs SET started_at = :s WHERE id = :i"), {"s": old_start, "i": run.id})
    time.sleep(0.4)
    with clock.at(MOMENT):
        db.execute(text("UPDATE production_runs SET ended_at = clock_timestamp() WHERE id = :i"), {"i": run.id})
    db.expire_all()
    assert run.started_at == old_start and run.ended_at == MOMENT


def test_one_statement_moves_all_of_a_tables_columns_so_a_check_between_them_holds(db):
    """`late` is declared before `early`, so moving the columns one at a time would move `late` first and break the
    CHECK; moving them in one statement judges the check on the final values."""
    db.execute(text("CREATE TABLE zz_pair (id serial PRIMARY KEY, late timestamptz, early timestamptz, CHECK (late >= early))"))
    clock = SimClock(db, END)                                              # reads the columns after the table exists
    with clock.at(MOMENT):
        db.execute(text("INSERT INTO zz_pair (early, late) VALUES (clock_timestamp(), clock_timestamp())"))
    row = db.execute(text("SELECT early, late FROM zz_pair")).one()
    assert row.early == row.late == MOMENT


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
