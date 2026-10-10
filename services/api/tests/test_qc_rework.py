"""B4 Task 3: rework runs (R10). One roll per run; manual mending (no machine) or a re-dye on a dyeing machine.
Hand-worked story: a 1,000 m order, rolls of 600 m and 400 m. The 600 m roll passes; the 400 m roll is sent for rework
with 2 holes, mended, inspected again and passes: passed metres 1,000, the order is ready to ship."""
import datetime as dt
import threading
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import MachineDowntime, ProductionRun, QcInspection, Roll, RollRun, User
from app.modules.qc import schemas as s
from app.modules.qc import service
from tests.factories import (
    dye, make_inspection, make_machine, make_order, make_roll, make_run, make_user, make_worker,
)
from tests.helpers import wipe_database

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


def make_floor(db, qty=1000):
    order = make_order(db, qty_metres=qty)
    weave = make_run(db, order, make_machine(db, stage="weaving"))
    return order, weave


def dyed_roll(db, order, weave, metres):
    roll = make_roll(db, order, weave, metres)
    run = make_run(db, order, make_machine(db, stage="dyeing"))
    dye(db, roll, run)
    run.ended_at = run.started_at
    db.flush()
    return roll


def needs_rework(db, metres=400, order=None, weave=None):
    if order is None:
        order, weave = make_floor(db)
    roll = dyed_roll(db, order, weave, metres)
    make_inspection(db, roll, "rework", inspected_at=T0)
    return roll


def status(client, roll):
    return next(r["status"] for r in client.get(f"/api/rolls?order_code={roll.order.code}").json() if r["code"] == roll.code)


def rework(client, roll, operator, machine=None, **over):
    body = {"roll_code": roll.code, "operator_worker_id": operator.id, **over}
    if machine is not None:
        body["machine_code"] = machine.code
    return client.post("/api/rework-runs", json=body)


def run_count(db) -> int:
    return db.scalar(select(func.count()).select_from(ProductionRun))


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


# ---- the story -------------------------------------------------------------------------------------

def test_the_rework_story_end_to_end(client, db, login_as, events):
    order, weave = make_floor(db)
    good = dyed_roll(db, order, weave, 600)
    sent_back = dyed_roll(db, order, weave, 400)
    login_as("qc")
    first = client.post("/api/qc/inspections", json={"roll_code": good.code, "verdict": "pass", "defects": []})
    assert first.status_code == 201
    r = client.post("/api/qc/inspections", json={"roll_code": sent_back.code, "verdict": "rework",
                                                  "defects": [{"defect_type": "hole", "count": 2}]})
    assert r.status_code == 201 and status(client, sent_back) == "awaiting_rework"
    login_as("supervisor")
    events.clear()
    started = rework(client, sent_back, make_worker(db))
    assert started.status_code == 201, started.text
    run = started.json()
    assert (run["stage"], run["machine_code"], run["order_code"]) == ("rework", None, order.code)
    assert run["roll_codes"] == [sent_back.code] and run["metres"] == 400.0 and run["ended_at"] is None
    assert run["input_run_id"] is None and run["output_kg"] is None
    assert status(client, sent_back) == "in_rework"
    assert events == [("roll.changed", sent_back.id), ("run.changed", run["id"])]               # no machine, no machine event
    assert client.post(f"/api/runs/{run['id']}/end", json={}).status_code == 200
    assert status(client, sent_back) == "awaiting_qc"
    login_as("qc")
    assert client.post("/api/qc/inspections", json={"roll_code": sent_back.code, "verdict": "pass", "defects": []}).status_code == 201
    assert status(client, sent_back) == "in_store"
    login_as("owner")
    out = client.get(f"/api/orders/{order.code}").json()
    assert out["progress"]["passed_m"] == 1000.0 and out["stage"] == "ready_to_ship"
    assert db.scalar(select(func.count()).select_from(QcInspection).where(QcInspection.roll_id == sent_back.id)) == 2


def test_a_re_dye_on_a_dyeing_machine(client, db, sup, events):
    roll = needs_rework(db)
    machine = make_machine(db, stage="dyeing")
    r = rework(client, roll, make_worker(db), machine)
    assert r.status_code == 201, r.text
    assert r.json()["machine_code"] == machine.code and status(client, roll) == "in_rework"
    assert events == [("roll.changed", roll.id), ("run.changed", r.json()["id"]), ("machine.changed", machine.id)]
    card = next(m for m in client.get("/api/floor").json()["machines"] if m["code"] == machine.code)
    assert card["status"] == "running" and card["current_run"]["stage"] == "rework" and card["current_run"]["order_progress_pct"] == 0.0
    assert client.post(f"/api/runs/{r.json()['id']}/end", json={}).status_code == 200
    assert status(client, roll) == "awaiting_qc"


def test_a_rework_run_takes_no_output_and_ends_on_a_breakdown(client, db, sup):
    roll = needs_rework(db)
    machine = make_machine(db, stage="dyeing")
    run = rework(client, roll, make_worker(db), machine).json()
    refused = client.post(f"/api/runs/{run['id']}/end", json={"output_kg": 5})
    assert refused.status_code == 422 and refused.json()["code"] == "OUTPUT_NOT_ALLOWED"
    assert client.post(f"/api/machines/{machine.code}/breakdown", json={"reason": "pump"}).status_code == 200
    assert status(client, roll) == "awaiting_qc"


def test_a_rework_run_started_right_after_an_inspection_is_in_rework_not_awaiting_rework(client, db, login_as):
    """Review Focus 3: the inspection and the rework run are stamped by the real clock, so the run is never 'before' it."""
    order, weave = make_floor(db)
    roll = dyed_roll(db, order, weave, 400)
    login_as("qc")
    assert client.post("/api/qc/inspections", json={"roll_code": roll.code, "verdict": "rework",
                                                     "defects": [{"defect_type": "stain", "count": 1}]}).status_code == 201
    login_as("supervisor")
    assert rework(client, roll, make_worker(db)).status_code == 201
    assert status(client, roll) == "in_rework"


# ---- refusals leave nothing behind ---------------------------------------------------------------------

def refused(client, db, events, response, status_code, code, field):
    before = (run_count(db), db.scalar(select(func.count()).select_from(RollRun)))
    assert response.status_code == status_code, response.text
    assert response.json()["code"] == code and response.json()["field"] == field, response.json()
    assert (run_count(db), db.scalar(select(func.count()).select_from(RollRun))) == before
    assert events == []


def test_the_roll_must_be_awaiting_rework(client, db, sup, events):
    order, weave = make_floor(db)
    waiting_qc = dyed_roll(db, order, weave, 100)
    woven = make_roll(db, order, weave, 100)
    in_store = dyed_roll(db, order, weave, 100)
    make_inspection(db, in_store, "pass", inspected_at=T0)
    for roll in (waiting_qc, woven, in_store):
        refused(client, db, events, rework(client, roll, make_worker(db)), 409, "ROLL_WRONG_STATUS", "roll_code")


def test_a_roll_already_in_rework_cannot_start_a_second_run(client, db, sup, events):
    roll = needs_rework(db)
    assert rework(client, roll, make_worker(db)).status_code == 201
    events.clear()
    refused(client, db, events, rework(client, roll, make_worker(db)), 409, "ROLL_WRONG_STATUS", "roll_code")


@pytest.mark.parametrize("stage", ["weaving", "spinning"])
def test_only_a_dyeing_machine_can_rework(client, db, sup, events, stage):
    roll = needs_rework(db)
    refused(client, db, events, rework(client, roll, make_worker(db), make_machine(db, stage=stage)), 409,
            "WRONG_STAGE", "machine_code")


def test_machine_and_operator_checks(client, db, sup, events):
    roll = needs_rework(db)
    worker = make_worker(db)
    refused(client, db, events, rework(client, roll, worker, make_machine(db, stage="dyeing", active=False)), 409,
            "MACHINE_INACTIVE", "machine_code")
    down = make_machine(db, stage="dyeing")
    db.add(MachineDowntime(machine_id=down.id, reason="pump"))
    db.flush()
    refused(client, db, events, rework(client, roll, worker, down), 409, "MACHINE_DOWN", "machine_code")
    refused(client, db, events, rework(client, roll, make_worker(db, active=False)), 409, "OPERATOR_INACTIVE",
            "operator_worker_id")
    assert status(client, roll) == "awaiting_rework"
    # last: a database constraint failure rolls the test's whole (single) transaction back, so nothing may follow it
    busy = make_machine(db, stage="dyeing")
    make_run(db, roll.order, busy)
    refused(client, db, events, rework(client, roll, worker, busy), 409, "MACHINE_BUSY", "machine_code")


def test_unknown_roll_machine_and_operator_are_404(client, db, sup, events):
    roll = needs_rework(db)
    worker = make_worker(db)
    refused(client, db, events, client.post("/api/rework-runs", json={"roll_code": "R-9999999",
            "operator_worker_id": worker.id}), 404, "NOT_FOUND", "roll_code")
    refused(client, db, events, client.post("/api/rework-runs", json={"roll_code": roll.code, "machine_code": "NOPE-1",
            "operator_worker_id": worker.id}), 404, "NOT_FOUND", "machine_code")
    refused(client, db, events, client.post("/api/rework-runs", json={"roll_code": roll.code,
            "operator_worker_id": 99999999}), 404, "NOT_FOUND", "operator_worker_id")


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("qc", True), ("owner", True), ("store", False),
                                      ("dispatch", False), ("accountant", False), ("buyer", False)])
def test_who_can_start_rework(client, db, login_as, role, ok):
    login_as(role)
    roll = needs_rework(db)
    assert (rework(client, roll, make_worker(db)).status_code == 201) is ok


# ---- two requests on one roll --------------------------------------------------------------------------------

def committed_rework_roll(engine):
    with Session(engine) as setup:
        roll = needs_rework(setup)
        workers = [make_worker(setup), make_worker(setup)]
        setup.commit()
        return roll.id, roll.code, [w.id for w in workers]


def test_two_simultaneous_rework_starts_on_one_roll_make_one_run(engine):
    try:
        for _ in range(5):
            roll_id, code, worker_ids = committed_rework_roll(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(worker_id, code=code, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.start_rework(session, s.ReworkIn(roll_code=code, operator_worker_id=worker_id))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go, args=(w,)) for w in worker_ids]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["ROLL_WRONG_STATUS", "ok"], results
            with Session(engine) as check:
                assert check.scalar(select(func.count()).select_from(RollRun).where(
                    RollRun.roll_id == roll_id, RollRun.purpose == "rework")) == 1
            wipe_database(engine)
    finally:
        wipe_database(engine)


def test_a_rework_start_waits_for_whoever_holds_the_roll_lock(engine):
    roll_id, code, worker_ids = committed_rework_roll(engine)
    outcome: list[str] = []

    def second():
        with Session(engine) as session:
            try:
                service.start_rework(session, s.ReworkIn(roll_code=code, operator_worker_id=worker_ids[1]))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            roll = holder.scalar(select(Roll).where(Roll.id == roll_id).with_for_update())     # the first supervisor has it
            thread = threading.Thread(target=second)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the second start must be waiting on the roll lock"
            run = ProductionRun(order_id=roll.order_id, machine_id=None, stage="rework",
                                operator_worker_id=worker_ids[0], started_at=service.db_now(holder))
            holder.add(run)
            holder.flush()
            holder.add(RollRun(roll_id=roll_id, run_id=run.id, purpose="rework"))
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ROLL_WRONG_STATUS"]
    finally:
        wipe_database(engine)


def test_a_rework_run_stamped_by_a_transaction_that_began_before_the_inspection_still_counts(engine):
    """The clock hazard: this transaction began, then an inspector sent the roll back and committed. A transaction-start
    stamp on the rework run would be EARLIER than the inspection, and the roll would stay awaiting_rework."""
    with Session(engine) as setup:
        order, weave = make_floor(setup)
        roll = dyed_roll(setup, order, weave, 400)
        qc_user, worker = make_user(setup, role="qc"), make_worker(setup)
        setup.commit()
        code, qc_id, worker_id, roll_id = roll.code, qc_user.id, worker.id, roll.id
    try:
        with Session(engine) as late:
            late.execute(select(func.now()))                         # our transaction begins here
            time.sleep(0.1)
            with Session(engine) as inspector:
                service.record_inspection(inspector, inspector.get(User, qc_id), s.InspectionIn(
                    roll_code=code, verdict="rework", defects=[s.DefectIn(defect_type="hole", count=1)]))
            service.start_rework(late, s.ReworkIn(roll_code=code, operator_worker_id=worker_id))
            assert roll_status_of(late, roll_id) == "in_rework"
    finally:
        wipe_database(engine)


def roll_status_of(db, roll_id):
    from app.modules.rolls.service import roll_status
    return roll_status(db, roll_id)
