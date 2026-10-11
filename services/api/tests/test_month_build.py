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


def test_an_orders_deadline_and_dates_follow_the_simulated_calendar(built):
    plan, clock, runner, db = built
    for order in db.scalars(select(Order)):
        created = order.created_at.astimezone(IST).date()
        assert plan.day0.date() <= created <= END.date()
        assert (order.deadline - created).days == 12                     # the plan asked for twelve days from creation
        assert order.confirmed_at is not None and abs((order.confirmed_at - order.created_at).total_seconds()) < 3600


@pytest.fixture(scope="module")
def built():
    """A 30-day month with the first three orders, every event played into a fresh `everest_month_test`: orders, yarn, runs,
    quality, rework, trucks, invoices, payments, attendance, wages and breakdowns."""
    database.recreate(URL)
    database.migrate(URL)
    engine = create_engine(URL)
    db = Session(engine)
    plan = build_plan(END, seed=11, days=30, orders=ORDERS[:3])
    clock = SimClock(db, END)
    with clock.installed():
        with clock.at(plan.day0 - dt.timedelta(days=6)):
            seed_dev.seed_all(db)
        runner = Runner(db, clock)
        runner.play(plan.events)
    yield plan, clock, runner, db
    db.close()
    engine.dispose()
    database.drop(URL)


def count(plan, action):
    return sum(1 for e in plan.events if e.action == action)


def test_every_event_was_played_and_nothing_leaks(built):
    plan, clock, runner, db = built
    assert runner.count == len(plan.events)
    assert clock.leaks() == [], clock.leaks()


def test_inspections_rework_trucks_and_invoices_match_the_plan(built):
    from app.db.models import Dispatch, DispatchItem, Invoice, QcInspection, RollRun
    plan, clock, runner, db = built
    assert db.scalar(select(func.count()).select_from(QcInspection)) == count(plan, "inspect") > 10
    assert db.scalar(select(func.count()).select_from(RollRun).where(RollRun.purpose == "rework")) >= count(plan, "rework_start") >= 1
    assert db.scalar(select(func.count()).select_from(Dispatch)) == count(plan, "dispatch_create") >= 3
    assert db.scalar(select(func.count()).select_from(Invoice)) == count(plan, "dispatch_confirm") >= 3
    assert db.scalar(select(func.count()).select_from(DispatchItem)) == count(plan, "dispatch_scan")


def test_a_dispatched_roll_always_has_a_final_pass(built):
    from sqlalchemy import text
    plan, clock, runner, db = built
    bad = db.execute(text("""
        SELECT r.code FROM dispatch_items di JOIN rolls r ON r.id = di.roll_id
        WHERE (SELECT verdict FROM qc_inspections q WHERE q.roll_id = r.id ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) <> 'pass'""")).all()
    assert bad == []


def test_attendance_covers_every_shift_and_every_run_operator_was_present(built):
    from sqlalchemy import text
    from app.db.models import Attendance
    plan, clock, runner, db = built
    expected = sum(len(e.args["entries"]) for e in plan.events if e.action == "attendance")
    assert db.scalar(select(func.count()).select_from(Attendance)) == expected
    uncovered = db.execute(text("""
        SELECT p.id FROM production_runs p JOIN shifts s ON TRUE
        WHERE p.machine_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.worker_id = p.operator_worker_id AND a.status = 'present'
                          AND a.shift_id = (SELECT id FROM shifts WHERE name = CASE
                              WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time >= '06:00' AND (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '14:00' THEN 'A'
                              WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time >= '14:00' AND (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '22:00' THEN 'B'
                              ELSE 'C' END)
                          AND a.date = CASE WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '06:00'
                                            THEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::date - 1
                                            ELSE (p.started_at AT TIME ZONE 'Asia/Kolkata')::date END)
        GROUP BY p.id""")).all()
    assert uncovered == [], f"{len(uncovered)} runs started with an operator who was not marked present for that shift"


def test_breakdowns_payments_and_wages_were_recorded(built):
    from app.db.models import BuyerPayment, MachineDowntime, SupplierPayment, WagePayment
    plan, clock, runner, db = built
    assert db.scalar(select(func.count()).select_from(MachineDowntime)) == count(plan, "breakdown") == 4
    still_down = db.scalars(select(MachineDowntime).where(MachineDowntime.ended_at.is_(None))).all()
    assert len(still_down) == 1                                                       # SPIN-02 is down "now"
    assert db.scalar(select(func.count()).select_from(SupplierPayment)) == count(plan, "supplier_payment") == 2
    assert db.scalar(select(func.count()).select_from(WagePayment)) > 0
    assert db.scalar(select(func.count()).select_from(BuyerPayment)) == sum(
        1 for e in plan.events if e.action == "buyer_payment")


def test_the_money_screens_load_and_the_opening_lots_bill_is_overdue(built):
    from app.modules.money import service as money
    plan, clock, runner, db = built
    assert money.receivables(db)
    overdue = [p for p in money.payables(db) if p.overdue]
    assert len(overdue) >= 1


def test_the_audit_passes_on_a_small_month(built):
    from scripts.month.audit import audit, report
    plan, clock, runner, db = built
    checks = audit(db, clock, runner=runner, full=False)
    assert len(checks) >= 8 and all(c.ok for c in checks), report([c for c in checks if not c.ok])


def test_the_audit_fails_when_something_is_wrong(built):
    """Each planted fault must turn its own check red: a real-clock timestamp, and a run whose operator (a night-shift
    worker) was never marked present in the shift the run started in."""
    from sqlalchemy import text
    from scripts.month.audit import audit
    plan, clock, runner, db = built

    def failing(plant):
        nested = db.begin_nested()
        try:
            db.execute(text(plant))
            return {c.name for c in audit(db, clock, runner=runner, full=False) if not c.ok}
        finally:
            nested.rollback()

    assert "no real-clock timestamp left" in failing("UPDATE orders SET confirmed_at = clock_timestamp() WHERE id = (SELECT min(id) FROM orders)")
    assert "every run's operator was present that shift" in failing(
        "UPDATE production_runs SET operator_worker_id = (SELECT id FROM workers WHERE code = 'W-010') "
        "WHERE id = (SELECT min(id) FROM production_runs WHERE machine_id IS NOT NULL)")
