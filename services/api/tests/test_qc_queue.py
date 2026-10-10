"""B4 Task 4: the QC queue. Counts come from the roll-status view; 'passed' means the roll's latest verdict is pass
(in store, on a loading dispatch or dispatched). Six rolls: 1 awaiting QC, 1 awaiting rework, 1 in rework, 1 in store,
1 on a loading dispatch, 1 rejected -> awaiting_qc 1, awaiting_rework 1, in_rework 1, passed 2, rejected 1."""
import datetime as dt

import pytest

from app.db.models import RollRun
from tests.factories import (
    dye, make_dispatch, make_inspection, make_machine, make_order, make_roll, make_run, put_on_dispatch,
)

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


class Yard:
    def __init__(self, db):
        self.db = db
        self.order = make_order(db, qty_metres=5000)
        self.weave = make_run(db, self.order, make_machine(db, stage="weaving"))

    def roll(self, metres=100, dyed=True):
        roll = make_roll(self.db, self.order, self.weave, metres)
        if dyed:
            run = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"))
            dye(self.db, roll, run)
            run.ended_at = run.started_at
            self.db.flush()
        return roll

    def inspected(self, verdict, days=1, **kw):
        roll = self.roll(**kw)
        make_inspection(self.db, roll, verdict, inspected_at=T0 + dt.timedelta(days=days))
        return roll


def queue(client):
    r = client.get("/api/qc/queue")
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def qc(login_as):
    return login_as("qc")


def test_the_six_roll_counts_and_the_list(client, db, qc):
    y = Yard(db)
    r1 = y.roll()                                                    # awaiting_qc
    r2 = y.inspected("rework")                                       # awaiting_rework
    r3 = y.inspected("rework")                                       # in_rework: a rework run started after the inspection
    run = make_run(db, y.order, make_machine(db, stage="dyeing"), stage="rework", started_at=T0 + dt.timedelta(days=2))
    db.add(RollRun(roll_id=r3.id, run_id=run.id, purpose="rework"))
    y.inspected("pass")                                              # in_store
    r5 = y.inspected("pass")                                         # on a loading dispatch
    put_on_dispatch(db, r5, make_dispatch(db, y.order.buyer))
    y.inspected("reject")                                            # rejected
    y.roll(dyed=False)                                               # woven: not in the queue
    dyeing = y.roll(dyed=False)                                      # dyeing: not in the queue
    dye(db, dyeing, make_run(db, y.order, make_machine(db, stage="dyeing")))
    out = queue(client)
    assert out["counts"] == {"awaiting_qc": 1, "awaiting_rework": 1, "in_rework": 1, "passed": 2, "rejected": 1}
    assert [r["code"] for r in out["rolls"]] == [r1.code, r2.code, r3.code]                    # oldest first
    assert [r["status"] for r in out["rolls"]] == ["awaiting_qc", "awaiting_rework", "in_rework"]
    assert out["rolls"][0]["metres"] == 100.0 and out["rolls"][0]["order_code"] == y.order.code


def test_passed_includes_dispatched_rolls(client, db, qc):
    y = Yard(db)
    roll = y.inspected("pass")
    put_on_dispatch(db, roll, make_dispatch(db, y.order.buyer, state="dispatched", dispatched_at=T0 + dt.timedelta(days=3)))
    out = queue(client)
    assert out["counts"]["passed"] == 1 and out["rolls"] == []


def test_the_latest_verdict_decides_what_counts_as_passed(client, db, qc):
    y = Yard(db)
    for _ in range(2):                                               # reworked, then passed: both count as passed
        roll = y.inspected("rework", days=1)
        make_inspection(db, roll, "pass", inspected_at=T0 + dt.timedelta(days=5))
    later_bad = y.inspected("pass", days=1)
    make_inspection(db, later_bad, "rework", inspected_at=T0 + dt.timedelta(days=6))    # passed, then sent back
    out = queue(client)
    assert out["counts"]["passed"] == 2 and out["counts"]["awaiting_rework"] == 1      # the oldest verdict would give 1
    assert [r["code"] for r in out["rolls"]] == [later_bad.code]


def test_an_empty_database_gives_zero_counts_and_no_rolls(client, db, qc):
    assert queue(client) == {"counts": {"awaiting_qc": 0, "awaiting_rework": 0, "in_rework": 0, "passed": 0, "rejected": 0},
                             "rolls": []}


@pytest.mark.parametrize("role, ok", [("qc", True), ("owner", True), ("supervisor", True), ("store", False),
                                      ("dispatch", False), ("accountant", False), ("buyer", False)])
def test_who_can_see_the_queue(client, db, login_as, role, ok):
    login_as(role)
    assert (client.get("/api/qc/queue").status_code == 200) is ok
