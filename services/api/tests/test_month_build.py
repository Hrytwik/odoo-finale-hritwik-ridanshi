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
        first_inspection = min(e.t for e in plan.events if e.action == "inspect")       # before quality starts there is no rework
        runner.play([e for e in plan.events if e.t < first_inspection], only=FIRST_HALF)
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


def test_an_orders_deadline_and_dates_follow_the_simulated_calendar(built):
    plan, clock, runner, db = built
    for order in db.scalars(select(Order)):
        created = order.created_at.astimezone(IST).date()
        assert plan.day0.date() <= created <= END.date()
        assert (order.deadline - created).days == 12                     # the plan asked for twelve days from creation
        assert order.confirmed_at is not None and abs((order.confirmed_at - order.created_at).total_seconds()) < 3600
