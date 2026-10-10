"""B3 Task 4: end a run and hand over (R6). Spinning needs its output; weaving and dyeing refuse one."""
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import ProductionRun, RollRun
from app.modules.floor import schemas as s
from app.modules.floor import service
from tests.factories import make_machine, make_order, make_roll, make_run, make_worker
from tests.helpers import wipe_database


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


def open_runs(db, machine) -> int:
    return db.scalar(select(func.count()).select_from(ProductionRun).where(
        ProductionRun.machine_id == machine.id, ProductionRun.ended_at.is_(None)))


def end(client, run, **body):
    return client.post(f"/api/runs/{run.id}/end", json=body)


def post_raw(client, path, raw):
    return client.post(path, content=raw, headers={"content-type": "application/json"})


# ---- end a run -------------------------------------------------------------------------------

def test_ending_a_spinning_run_saves_its_output(client, db, sup, events):
    machine = make_machine(db, stage="spinning")
    run = make_run(db, make_order(db), machine)
    r = end(client, run, output_kg=640)
    assert r.status_code == 200, r.text
    assert r.json()["output_kg"] == 640.0 and r.json()["ended_at"] and r.json()["id"] == run.id
    db.refresh(run)
    assert run.output_kg == Decimal("640.000") and run.ended_at >= run.started_at and open_runs(db, machine) == 0
    assert events == [("run.changed", run.id), ("machine.changed", machine.id)]


def test_zero_output_is_allowed_but_blank_is_not(client, db, sup, events):
    order = make_order(db)
    run = make_run(db, order, make_machine(db, stage="spinning"))
    r = end(client, run)
    assert r.status_code == 422 and r.json()["code"] == "OUTPUT_REQUIRED" and r.json()["field"] == "output_kg"
    assert events == []
    db.refresh(run)
    assert run.ended_at is None
    assert end(client, run, output_kg=0).status_code == 200


def test_output_is_rounded_half_up_to_three_places(client, db, sup):
    run = make_run(db, make_order(db), make_machine(db, stage="spinning"))
    assert end(client, run, output_kg=1.0005).json()["output_kg"] == 1.001


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "true", '"abc"', "1e9", "null"])
def test_bad_outputs_are_422_and_leave_the_run_open(client, db, sup, events, value):
    run = make_run(db, make_order(db), make_machine(db, stage="spinning"))
    r = post_raw(client, f"/api/runs/{run.id}/end", '{"output_kg": %s}' % value)
    assert r.status_code == 422 and events == []
    db.refresh(run)
    assert run.ended_at is None


@pytest.mark.parametrize("stage", ["weaving", "dyeing"])
def test_weaving_and_dyeing_end_without_output_and_refuse_one(client, db, sup, events, stage):
    order = make_order(db)
    machine = make_machine(db, stage=stage)
    run = make_run(db, order, machine)
    r = end(client, run, output_kg=5)
    assert r.status_code == 422 and r.json()["code"] == "OUTPUT_NOT_ALLOWED" and r.json()["field"] == "output_kg"
    db.refresh(run)
    assert run.ended_at is None and events == []
    assert end(client, run).status_code == 200


def test_ending_twice_and_unknown_runs(client, db, sup):
    run = make_run(db, make_order(db), make_machine(db, stage="dyeing"))
    assert end(client, run).status_code == 200
    r = end(client, run)
    assert r.status_code == 409 and r.json()["code"] == "RUN_NOT_OPEN" and r.json()["field"] == "run_id"
    r = client.post("/api/runs/99999999/end", json={})
    assert r.status_code == 404 and r.json()["field"] == "run_id"


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_end_a_run(client, db, login_as, role, ok):
    login_as(role)
    run = make_run(db, make_order(db), make_machine(db, stage="dyeing"))
    assert (end(client, run).status_code == 200) is ok


# ---- hand over -------------------------------------------------------------------------------

def handover(client, run, worker):
    return client.post(f"/api/runs/{run.id}/handover", json={"operator_worker_id": worker.id})


def test_handover_ends_the_old_run_and_starts_a_new_one_at_the_same_instant(client, db, sup, events):
    order, machine = make_order(db), make_machine(db, stage="spinning")
    first, second = make_worker(db), make_worker(db)
    old = make_run(db, order, machine, operator=first)
    r = handover(client, old, second)
    assert r.status_code == 201, r.text
    out = r.json()
    new = db.get(ProductionRun, out["id"])
    db.refresh(old)
    assert new.id != old.id and out["operator"]["id"] == second.id and out["ended_at"] is None
    assert (new.order_id, new.machine_id, new.stage, new.input_run_id) == (order.id, machine.id, "spinning", None)
    assert old.ended_at == new.started_at and old.output_kg is None
    assert open_runs(db, machine) == 1 and out["roll_codes"] == [] and out["metres"] == 0.0
    assert events == [("run.changed", old.id), ("run.changed", new.id), ("machine.changed", machine.id)]


def test_handover_of_a_weaving_run_keeps_the_input_run_and_leaves_rolls_on_the_old_run(client, db, sup):
    order, machine = make_order(db), make_machine(db, stage="weaving")
    old = make_run(db, order, machine)
    roll = make_roll(db, order, old, 110)
    r = handover(client, old, make_worker(db))
    assert r.status_code == 201
    new = db.get(ProductionRun, r.json()["id"])
    assert new.input_run_id == old.input_run_id and new.stage == "weaving"
    assert db.scalar(select(RollRun.run_id).where(RollRun.roll_id == roll.id)) == old.id
    assert r.json()["roll_codes"] == [] and client.get(f"/api/runs?order_code={order.code}").status_code == 200


def test_handover_to_the_same_operator_is_refused(client, db, sup, events):
    worker = make_worker(db)
    machine = make_machine(db, stage="spinning")
    old = make_run(db, make_order(db), machine, operator=worker)
    r = handover(client, old, worker)
    assert r.status_code == 422 and r.json()["field"] == "operator_worker_id"
    db.refresh(old)
    assert old.ended_at is None and open_runs(db, machine) == 1 and events == []


def test_handover_operator_checks(client, db, sup, events):
    old = make_run(db, make_order(db), make_machine(db, stage="spinning"))
    r = handover(client, old, make_worker(db, active=False))
    assert r.status_code == 409 and r.json()["code"] == "OPERATOR_INACTIVE"
    r = client.post(f"/api/runs/{old.id}/handover", json={"operator_worker_id": 99999999})
    assert r.status_code == 404 and r.json()["field"] == "operator_worker_id"
    db.refresh(old)
    assert old.ended_at is None and events == []


def test_handover_of_an_ended_or_unknown_run(client, db, sup):
    old = make_run(db, make_order(db), make_machine(db, stage="dyeing"))
    end(client, old)
    r = handover(client, old, make_worker(db))
    assert r.status_code == 409 and r.json()["code"] == "RUN_NOT_OPEN"
    assert client.post("/api/runs/99999999/handover", json={"operator_worker_id": 1}).status_code == 404


def test_a_run_without_a_machine_cannot_be_handed_over(client, db, sup):
    order = make_order(db)
    mending = ProductionRun(order_id=order.id, machine_id=None, stage="rework",
                            operator_worker_id=make_worker(db).id)
    db.add(mending)
    db.flush()
    r = handover(client, mending, make_worker(db))
    assert r.status_code == 409 and r.json()["code"] == "WRONG_STAGE" and r.json()["field"] == "run_id"


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_hand_over(client, db, login_as, role, ok):
    login_as(role)
    old = make_run(db, make_order(db), make_machine(db, stage="spinning"))
    assert (handover(client, old, make_worker(db)).status_code == 201) is ok


# ---- time and concurrency -----------------------------------------------------------------------

def committed_run(engine, stage="spinning"):
    with Session(engine) as setup:
        order, machine = make_order(setup), make_machine(setup, stage=stage)
        run = make_run(setup, order, machine)
        workers = [make_worker(setup), make_worker(setup)]
        setup.commit()
        return run.id, [w.id for w in workers]


def test_ending_a_run_that_started_after_this_transaction_began_still_works(engine):
    """The clock hazard: our transaction began, then another session started the run and committed. A transaction-start
    timestamp would be EARLIER than the run's started_at and break end_after_start; the real clock is not."""
    with Session(engine) as setup:
        order, machine, worker = make_order(setup), make_machine(setup, stage="spinning"), make_worker(setup)
        setup.commit()
        body = s.RunStartIn(order_code=order.code, machine_code=machine.code, operator_worker_id=worker.id)
    try:
        with Session(engine) as late:
            late.execute(select(func.now()))                     # our transaction begins here
            time.sleep(0.1)
            with Session(engine) as other:
                run_id = service.start_run(other, body).id       # started AFTER our transaction began, committed
            run = service.end_run(late, run_id, s.RunEndIn(output_kg=1))
            assert run.ended_at >= run.started_at
    finally:
        wipe_database(engine)


def test_an_end_waits_for_the_machine_lock_and_then_sees_the_run_already_ended(engine):
    run_id, _ = committed_run(engine)
    outcome: list[str] = []

    def end_it():
        with Session(engine) as session:
            try:
                service.end_run(session, run_id, s.RunEndIn(output_kg=5))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            held = service.locked_open_run(holder, run_id)
            thread = threading.Thread(target=end_it)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the end must be waiting on the machine lock"
            held.ended_at = service.db_now(holder)
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["RUN_NOT_OPEN"]
    finally:
        wipe_database(engine)


def test_two_simultaneous_handovers_of_one_run_make_exactly_one_new_run(engine):
    try:
        for _ in range(3):
            run_id, worker_ids = committed_run(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(worker_id, run_id=run_id, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.handover(session, run_id, s.HandoverIn(operator_worker_id=worker_id))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go, args=(w,)) for w in worker_ids]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["RUN_NOT_OPEN", "ok"], results
            with Session(engine) as check:
                machine_id = check.get(ProductionRun, run_id).machine_id
                assert check.scalar(select(func.count()).select_from(ProductionRun).where(
                    ProductionRun.machine_id == machine_id, ProductionRun.ended_at.is_(None))) == 1
    finally:
        wipe_database(engine)
