"""B3 Task 1: v_roll_status implements spec §5, rule by rule (dispatch, latest verdict, rework run, dye run)."""
import datetime as dt

import pytest
from sqlalchemy import text

from app.db.models import RollRun
from tests.factories import (
    dye, make_dispatch, make_inspection, make_machine, make_order, make_roll, make_run, put_on_dispatch,
)

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


def at(days: int) -> dt.datetime:
    return T0 + dt.timedelta(days=days)


class World:
    def __init__(self, db):
        self.db = db
        self.order = make_order(db)
        self.weave = make_run(db, self.order, make_machine(db, stage="weaving"))
        self.roll = make_roll(db, self.order, self.weave)

    def status(self) -> str:
        return self.db.execute(text("SELECT status FROM v_roll_status WHERE roll_id = :i"),
                               {"i": self.roll.id}).scalar_one()

    def dye_run(self, ended: bool, started_days: int = 0):
        run = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"), started_at=at(started_days),
                       ended_at=at(started_days) + dt.timedelta(hours=2) if ended else None)
        dye(self.db, self.roll, run)
        return run

    def rework_run(self, started_days: int, ended: bool):
        run = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"), stage="rework",
                       started_at=at(started_days), ended_at=at(started_days) + dt.timedelta(hours=2) if ended else None)
        self.db.add(RollRun(roll_id=self.roll.id, run_id=run.id, purpose="rework"))
        self.db.flush()
        return run

    def inspect(self, verdict: str, days: int):
        return make_inspection(self.db, self.roll, verdict, inspected_at=at(days))


@pytest.fixture
def w(db):
    return World(db)


def test_a_roll_with_no_dye_run_and_no_inspection_is_woven(w):
    assert w.status() == "woven"


def test_an_open_dye_run_means_dyeing(w):
    w.dye_run(ended=False)
    assert w.status() == "dyeing"


def test_an_ended_dye_run_means_awaiting_qc(w):
    w.dye_run(ended=True)
    assert w.status() == "awaiting_qc"


def test_the_latest_dye_run_decides_an_open_run_after_an_ended_one_is_dyeing(w):
    w.dye_run(ended=True, started_days=0)
    w.dye_run(ended=False, started_days=1)
    assert w.status() == "dyeing"


def test_the_latest_dye_run_decides_an_ended_run_after_an_open_one_is_awaiting_qc(w):
    w.dye_run(ended=False, started_days=0)
    w.dye_run(ended=True, started_days=1)
    assert w.status() == "awaiting_qc"


def test_two_ended_dye_runs_are_awaiting_qc(w):
    w.dye_run(ended=True, started_days=0)
    w.dye_run(ended=True, started_days=1)
    assert w.status() == "awaiting_qc"


def test_the_latest_rework_run_decides_an_open_run_after_an_ended_one_is_in_rework(w):
    w.dye_run(ended=True)
    w.inspect("rework", 1)
    w.rework_run(started_days=2, ended=True)
    w.rework_run(started_days=3, ended=False)
    assert w.status() == "in_rework"


def test_latest_pass_is_in_store(w):
    w.dye_run(ended=True)
    w.inspect("pass", 1)
    assert w.status() == "in_store"


def test_latest_reject_is_rejected(w):
    w.dye_run(ended=True)
    w.inspect("reject", 1)
    assert w.status() == "rejected"


def test_reject_then_a_later_pass_is_in_store(w):
    w.dye_run(ended=True)
    w.inspect("reject", 1)
    w.inspect("pass", 2)
    assert w.status() == "in_store"


def test_an_inspected_roll_ignores_an_open_dye_run(w):
    w.inspect("pass", 1)
    w.dye_run(ended=False)
    assert w.status() == "in_store"


def test_rework_verdict_with_no_rework_run_is_awaiting_rework(w):
    w.dye_run(ended=True)
    w.inspect("rework", 1)
    assert w.status() == "awaiting_rework"


def test_pass_then_a_later_rework_is_awaiting_rework(w):
    w.dye_run(ended=True)
    w.inspect("pass", 1)
    w.inspect("rework", 2)
    assert w.status() == "awaiting_rework"


def test_an_open_rework_run_after_the_inspection_is_in_rework(w):
    w.dye_run(ended=True)
    w.inspect("rework", 1)
    w.rework_run(started_days=2, ended=False)
    assert w.status() == "in_rework"


def test_an_ended_rework_run_after_the_inspection_is_awaiting_qc(w):
    w.dye_run(ended=True)
    w.inspect("rework", 1)
    w.rework_run(started_days=2, ended=True)
    assert w.status() == "awaiting_qc"


def test_a_rework_run_from_before_the_latest_rework_inspection_is_ignored(w):
    w.dye_run(ended=True)
    w.inspect("rework", 1)
    w.rework_run(started_days=2, ended=True)          # first cycle: reworked, then inspected again
    w.inspect("rework", 3)                            # second inspection says rework again
    assert w.status() == "awaiting_rework"


def test_a_dispatched_roll_is_dispatched_whatever_its_verdict(w):
    w.dye_run(ended=True)
    w.inspect("reject", 1)
    put_on_dispatch(w.db, w.roll, make_dispatch(w.db, w.order.buyer, state="dispatched", dispatched_at=at(5)))
    assert w.status() == "dispatched"


def test_a_roll_on_a_loading_dispatch_is_loading(w):
    w.dye_run(ended=True)
    w.inspect("pass", 1)
    put_on_dispatch(w.db, w.roll, make_dispatch(w.db, w.order.buyer))
    assert w.status() == "loading"


def test_every_roll_has_exactly_one_status_row(db):
    order = make_order(db)
    weave = make_run(db, order, make_machine(db, stage="weaving"))
    rolls = [make_roll(db, order, weave) for _ in range(3)]
    rows = db.execute(text("SELECT roll_id, status FROM v_roll_status WHERE roll_id = ANY(:ids)"),
                      {"ids": [r.id for r in rolls]}).all()
    assert sorted(r.roll_id for r in rows) == sorted(r.id for r in rolls) and {r.status for r in rows} == {"woven"}
