"""B3 Task 3: start a run (R4). Stage = the machine's stage; checks in the planned order; nothing left behind on refusal."""
import threading
import time

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import MachineDowntime, Order, ProductionRun
from app.modules.floor import schemas as s
from app.modules.floor import service
from app.modules.orders import service as orders
from tests.factories import make_machine, make_order, make_run, make_worker
from tests.helpers import wipe_database


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def sup(login_as):
    return login_as("supervisor")


def run_count(db) -> int:
    return db.scalar(select(func.count()).select_from(ProductionRun))


def start(client, order, machine, operator, **over):
    return client.post("/api/runs", json={"order_code": order.code, "machine_code": machine.code,
                                          "operator_worker_id": operator.id, **over})


def refused(client, db, events, response, status, code, field):
    before = run_count(db)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code and response.json()["field"] == field, response.json()
    assert run_count(db) == before and events == []


# ---- happy paths ------------------------------------------------------------------------------

def test_start_a_spinning_run(client, db, sup, events):
    order, machine, worker = make_order(db), make_machine(db, stage="spinning"), make_worker(db)
    r = start(client, order, machine, worker)
    assert r.status_code == 201, r.text
    out = r.json()
    assert (out["order_code"], out["machine_code"], out["stage"]) == (order.code, machine.code, "spinning")
    assert out["operator"]["id"] == worker.id and out["ended_at"] is None and out["output_kg"] is None
    assert out["input_run_id"] is None and out["roll_codes"] == [] and out["metres"] == 0.0 and out["started_at"]
    run = db.get(ProductionRun, out["id"])
    assert run.ended_at is None and run.operator_worker_id == worker.id
    assert events == [("run.changed", run.id), ("machine.changed", machine.id)]


def test_start_a_weaving_run_with_its_spinning_input(client, db, sup):
    order, worker = make_order(db), make_worker(db)
    spin = make_run(db, order, make_machine(db, stage="spinning"))
    r = start(client, order, make_machine(db, stage="weaving"), worker, input_run_id=spin.id)
    assert r.status_code == 201 and r.json()["stage"] == "weaving" and r.json()["input_run_id"] == spin.id


def test_an_ended_spinning_run_is_a_fine_input(client, db, sup):
    order = make_order(db)
    spin = make_run(db, order, make_machine(db, stage="spinning"))
    spin.ended_at = spin.started_at
    db.flush()
    r = start(client, order, make_machine(db, stage="weaving"), make_worker(db), input_run_id=spin.id)
    assert r.status_code == 201


def test_start_a_dyeing_run(client, db, sup):
    r = start(client, make_order(db), make_machine(db, stage="dyeing"), make_worker(db))
    assert r.status_code == 201 and r.json()["stage"] == "dyeing"


def test_one_operator_may_run_two_machines(client, db, sup):
    order, worker = make_order(db), make_worker(db)
    assert start(client, order, make_machine(db, stage="spinning"), worker).status_code == 201
    assert start(client, order, make_machine(db, stage="dyeing"), worker).status_code == 201


# ---- refusals (each leaves nothing behind) -----------------------------------------------------

def test_unknown_order_machine_and_operator_are_404(client, db, sup, events):
    order, machine, worker = make_order(db), make_machine(db, stage="spinning"), make_worker(db)
    r = client.post("/api/runs", json={"order_code": "ORD-9999999", "machine_code": machine.code,
                                       "operator_worker_id": worker.id})
    refused(client, db, events, r, 404, "NOT_FOUND", "order_code")
    r = client.post("/api/runs", json={"order_code": order.code, "machine_code": "NOPE-1",
                                       "operator_worker_id": worker.id})
    refused(client, db, events, r, 404, "NOT_FOUND", "machine_code")
    r = client.post("/api/runs", json={"order_code": order.code, "machine_code": machine.code,
                                       "operator_worker_id": 99999999})
    refused(client, db, events, r, 404, "NOT_FOUND", "operator_worker_id")


@pytest.mark.parametrize("state", ["draft", "cancelled"])
def test_the_order_must_be_confirmed(client, db, sup, events, state):
    order = make_order(db, state=state)
    refused(client, db, events, start(client, order, make_machine(db, stage="spinning"), make_worker(db)),
            409, "ORDER_NOT_CONFIRMED", "order_code")


def test_the_machine_must_be_active(client, db, sup, events):
    machine = make_machine(db, stage="spinning", active=False)
    refused(client, db, events, start(client, make_order(db), machine, make_worker(db)), 409,
            "MACHINE_INACTIVE", "machine_code")


def test_the_operator_must_be_active(client, db, sup, events):
    worker = make_worker(db, active=False)
    refused(client, db, events, start(client, make_order(db), make_machine(db, stage="spinning"), worker), 409,
            "OPERATOR_INACTIVE", "operator_worker_id")


def test_a_down_machine_cannot_start(client, db, sup, events):
    machine = make_machine(db, stage="spinning")
    db.add(MachineDowntime(machine_id=machine.id, reason="belt"))
    db.flush()
    refused(client, db, events, start(client, make_order(db), machine, make_worker(db)), 409,
            "MACHINE_DOWN", "machine_code")


def test_a_busy_machine_cannot_start_and_keeps_exactly_one_open_run(client, db, sup, events):
    order, machine = make_order(db), make_machine(db, stage="spinning")
    assert start(client, order, machine, make_worker(db)).status_code == 201
    events.clear()
    refused(client, db, events, start(client, order, machine, make_worker(db)), 409, "MACHINE_BUSY", "machine_code")
    assert db.scalar(select(func.count()).select_from(ProductionRun).where(
        ProductionRun.machine_id == machine.id, ProductionRun.ended_at.is_(None))) == 1


def test_weaving_needs_an_input_run(client, db, sup, events):
    refused(client, db, events, start(client, make_order(db), make_machine(db, stage="weaving"), make_worker(db)),
            422, "INPUT_RUN_REQUIRED", "input_run_id")


def test_weaving_input_must_be_a_spinning_run_of_the_same_order(client, db, sup, events):
    order, other = make_order(db), make_order(db)
    weaving_machine, worker = make_machine(db, stage="weaving"), make_worker(db)
    foreign = make_run(db, other, make_machine(db, stage="spinning"))
    refused(client, db, events, start(client, order, weaving_machine, worker, input_run_id=foreign.id), 409,
            "INPUT_RUN_REQUIRED", "input_run_id")
    a_weaving_run = make_run(db, order, make_machine(db, stage="weaving"))
    refused(client, db, events, start(client, order, weaving_machine, worker, input_run_id=a_weaving_run.id), 409,
            "INPUT_RUN_REQUIRED", "input_run_id")
    refused(client, db, events, start(client, order, weaving_machine, worker, input_run_id=99999999), 404,
            "NOT_FOUND", "input_run_id")


@pytest.mark.parametrize("stage", ["spinning", "dyeing"])
def test_only_weaving_takes_an_input_run(client, db, sup, events, stage):
    order = make_order(db)
    spin = make_run(db, order, make_machine(db, stage="spinning"))
    refused(client, db, events, start(client, order, make_machine(db, stage=stage), make_worker(db),
                                      input_run_id=spin.id), 422, "VALIDATION_ERROR", "input_run_id")


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_start_a_run(client, db, login_as, role, ok):
    login_as(role)
    r = start(client, make_order(db), make_machine(db, stage="spinning"), make_worker(db))
    assert (r.status_code == 201) is ok


def test_bad_bodies_are_422(client, db, sup):
    assert client.post("/api/runs", json={"order_code": "  ", "machine_code": "x", "operator_worker_id": 1}
                       ).status_code == 422
    assert client.post("/api/runs", json={"order_code": "x", "machine_code": "x"}).status_code == 422


# ---- the database clock, not the transaction start ----------------------------------------------

def test_started_at_is_the_real_time_of_the_write_not_the_start_of_the_transaction(engine):
    with Session(engine) as setup:
        order = make_order(setup)
        machine, worker = make_machine(setup, stage="spinning"), make_worker(setup)
        setup.commit()
        body = s.RunStartIn(order_code=order.code, machine_code=machine.code, operator_worker_id=worker.id)
    try:
        with Session(engine) as session:
            began = session.scalar(text("SELECT now()"))        # the transaction's start, fixed from here on
            time.sleep(0.2)
            run = service.start_run(session, body)
            assert (run.started_at - began).total_seconds() >= 0.15
    finally:
        wipe_database(engine)


# ---- two requests at the same moment --------------------------------------------------------------

def test_two_simultaneous_starts_on_one_machine_make_one_run(engine):
    """Review Focus 1: committed data, separate sessions, five fresh machines."""
    with Session(engine) as setup:
        order = make_order(setup)
        workers = [make_worker(setup), make_worker(setup)]
        machines = [make_machine(setup, stage="spinning") for _ in range(5)]
        setup.commit()
        order_code, worker_ids, machine_codes = order.code, [w.id for w in workers], [m.code for m in machines]
    try:
        for code in machine_codes:
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(worker_id, code=code, results=results, barrier=barrier):
                with Session(engine) as session:
                    body = s.RunStartIn(order_code=order_code, machine_code=code, operator_worker_id=worker_id)
                    barrier.wait()
                    try:
                        service.start_run(session, body)
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go, args=(w,)) for w in worker_ids]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["MACHINE_BUSY", "ok"], results
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(ProductionRun)) == 5
    finally:
        wipe_database(engine)


def test_a_start_waits_for_a_session_that_holds_the_order_and_cancels_it(engine):
    """Review Focus 2: cancel holds the order lock and commits first; the waiting start must be refused."""
    with Session(engine) as setup:
        order = make_order(setup)
        machine, worker = make_machine(setup, stage="spinning"), make_worker(setup)
        setup.commit()
        order_code, machine_code, worker_id = order.code, machine.code, worker.id
    outcome: list[str] = []

    def start_it():
        with Session(engine) as session:
            try:
                service.start_run(session, s.RunStartIn(order_code=order_code, machine_code=machine_code,
                                                        operator_worker_id=worker_id))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            held = orders.get_order_or_404(holder, order_code, for_update=True)
            thread = threading.Thread(target=start_it)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the start must be waiting on the order lock"
            held.state = "cancelled"
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ORDER_NOT_CONFIRMED"]
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(ProductionRun)) == 0
            assert check.scalar(select(Order.state).where(Order.code == order_code)) == "cancelled"
    finally:
        wipe_database(engine)
