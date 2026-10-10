"""B3 Task 5: breakdown and repair (R5). A breakdown opens a downtime and ends any open run at the same instant;
repair closes the downtime and does not reopen the run."""
import threading
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import MachineDowntime, Order, ProductionRun
from app.modules.floor import schemas as s
from app.modules.floor import service
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


def down(client, machine, reason="belt snapped"):
    return client.post(f"/api/machines/{machine.code}/breakdown", json={"reason": reason})


def repair(client, machine):
    return client.post(f"/api/machines/{machine.code}/repair")


def downtimes(db, machine) -> list[MachineDowntime]:
    return list(db.scalars(select(MachineDowntime).where(MachineDowntime.machine_id == machine.id)
                           .order_by(MachineDowntime.id)))


# ---- breakdown ------------------------------------------------------------------------------

def test_breakdown_with_a_running_job_ends_the_run_at_the_same_instant(client, db, sup, events):
    machine, order = make_machine(db, stage="spinning"), make_order(db)
    run = make_run(db, order, machine)
    r = down(client, machine, "  belt snapped  ")
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["code"] == machine.code and card["status"] == "down" and card["current_run"] is None
    assert card["downtime"]["reason"] == "belt snapped"
    [dt] = downtimes(db, machine)
    db.refresh(run)
    assert dt.ended_at is None and run.ended_at == dt.started_at and run.output_kg is None
    assert events == [("machine.changed", machine.id), ("run.changed", run.id)]


def test_breakdown_on_an_idle_machine_has_no_run_to_end(client, db, sup, events):
    machine = make_machine(db, stage="weaving")
    r = down(client, machine)
    assert r.status_code == 200 and r.json()["status"] == "down"
    assert events == [("machine.changed", machine.id)] and len(downtimes(db, machine)) == 1


def test_a_second_breakdown_while_down_is_refused_and_adds_nothing(client, db, sup, events):
    machine = make_machine(db, stage="spinning")
    assert down(client, machine).status_code == 200
    events.clear()
    r = down(client, machine, "again")
    assert r.status_code == 409 and r.json()["code"] == "MACHINE_ALREADY_DOWN" and r.json()["field"] == "machine_code"
    assert len(downtimes(db, machine)) == 1 and events == []


def test_blank_or_missing_reason_is_422(client, db, sup, events):
    machine = make_machine(db, stage="spinning")
    assert down(client, machine, "   ").status_code == 422
    assert client.post(f"/api/machines/{machine.code}/breakdown", json={}).status_code == 422
    assert downtimes(db, machine) == [] and events == []


def test_unknown_and_inactive_machines(client, db, sup, events):
    for path in ("breakdown", "repair"):
        r = client.post(f"/api/machines/NOPE-1/{path}", json={"reason": "x"})
        assert r.status_code == 404 and r.json()["field"] == "machine_code"
    off = make_machine(db, stage="spinning", active=False)
    r = down(client, off)
    assert r.status_code == 409 and r.json()["code"] == "MACHINE_INACTIVE" and r.json()["field"] == "machine_code"
    r = repair(client, off)
    assert r.status_code == 409 and r.json()["code"] == "MACHINE_INACTIVE"
    assert downtimes(db, off) == [] and events == []


# ---- repair --------------------------------------------------------------------------------------

def test_repair_closes_the_downtime_and_does_not_reopen_the_run(client, db, sup, events):
    machine, order = make_machine(db, stage="spinning"), make_order(db)
    run = make_run(db, order, machine)
    down(client, machine)
    events.clear()
    r = repair(client, machine)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "idle" and r.json()["downtime"] is None and r.json()["current_run"] is None
    [dt] = downtimes(db, machine)
    db.refresh(run)
    assert dt.ended_at is not None and dt.ended_at >= dt.started_at and run.ended_at is not None
    assert events == [("machine.changed", machine.id)]
    again = client.post("/api/runs", json={"order_code": order.code, "machine_code": machine.code,
                                           "operator_worker_id": make_worker(db).id})
    assert again.status_code == 201                      # someone has to start a NEW run


def test_repair_when_not_down_is_refused(client, db, sup, events):
    machine = make_machine(db, stage="weaving")
    r = repair(client, machine)
    assert r.status_code == 409 and r.json()["code"] == "MACHINE_NOT_DOWN" and events == []


def test_after_repair_the_machine_can_break_down_again(client, db, sup):
    machine = make_machine(db, stage="dyeing")
    down(client, machine)
    repair(client, machine)
    assert down(client, machine, "second time").status_code == 200 and len(downtimes(db, machine)) == 2


@pytest.mark.parametrize("role, ok", [("supervisor", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("qc", False), ("dispatch", False), ("buyer", False)])
def test_who_can_break_down_and_repair(client, db, login_as, role, ok):
    login_as(role)
    machine = make_machine(db, stage="spinning")
    assert (down(client, machine).status_code == 200) is ok
    assert (repair(client, machine).status_code == 200) is ok


# ---- start against breakdown, and the clock ------------------------------------------------------

def committed_machine(engine):
    with Session(engine) as setup:
        order, machine, worker = make_order(setup), make_machine(setup, stage="spinning"), make_worker(setup)
        setup.commit()
        return order.code, machine.code, machine.id, worker.id


def test_a_start_waits_for_a_breakdown_that_holds_the_machine_and_is_then_refused(engine):
    """Review Focus 3: without the machine lock a start could slip in beside the breakdown and leave a down machine
    with a running job."""
    order_code, machine_code, machine_id, worker_id = committed_machine(engine)
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
            service.lock_machine(holder, machine_id)                   # the breakdown has the machine
            thread = threading.Thread(target=start_it)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the start must be waiting on the machine lock"
            service.breakdown(holder, machine_code, s.BreakdownIn(reason="belt"))      # commits, releases the lock
            thread.join(timeout=10)
        assert outcome == ["MACHINE_DOWN"]
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(ProductionRun)) == 0
    finally:
        wipe_database(engine)


def test_a_breakdown_that_began_before_a_start_committed_still_ends_that_run(engine):
    """The clock hazard: this transaction began, then another session started a run and committed; a breakdown stamping
    the transaction-start time would end the run BEFORE it started and break end_after_start."""
    order_code, machine_code, machine_id, worker_id = committed_machine(engine)
    try:
        with Session(engine) as late:
            late.execute(select(func.now()))                         # our transaction begins here
            time.sleep(0.1)
            with Session(engine) as other:
                run_id = service.start_run(other, s.RunStartIn(order_code=order_code, machine_code=machine_code,
                                                               operator_worker_id=worker_id)).id
            service.breakdown(late, machine_code, s.BreakdownIn(reason="belt"))
            run = late.get(ProductionRun, run_id)
            late.refresh(run)
            assert run.ended_at is not None and run.ended_at >= run.started_at
    finally:
        wipe_database(engine)


def test_a_breakdown_waits_for_a_start_that_holds_the_machine_and_then_ends_the_run_it_made(engine):
    """The other direction: the start has the machine lock and commits a run; the breakdown must wait, then end it."""
    order_code, machine_code, machine_id, worker_id = committed_machine(engine)
    done = threading.Event()

    def break_it():
        with Session(engine) as session:
            service.breakdown(session, machine_code, s.BreakdownIn(reason="belt"))
        done.set()

    try:
        with Session(engine) as holder:
            service.lock_machine(holder, machine_id)                       # the start has the machine
            thread = threading.Thread(target=break_it)
            thread.start()
            time.sleep(0.7)
            assert not done.is_set(), "the breakdown must be waiting on the machine lock"
            order_id = holder.scalar(select(Order.id).where(Order.code == order_code))
            holder.add(ProductionRun(order_id=order_id, machine_id=machine_id, stage="spinning",
                                     operator_worker_id=worker_id, started_at=service.db_now(holder)))
            holder.commit()                                                # the start finishes, releases the lock
            thread.join(timeout=10)
        assert done.is_set()
        with Session(engine) as check:
            run = check.scalar(select(ProductionRun).where(ProductionRun.machine_id == machine_id))
            assert run.ended_at is not None                                # the breakdown ended the run it waited for
            assert check.scalar(select(func.count()).select_from(MachineDowntime).where(
                MachineDowntime.machine_id == machine_id, MachineDowntime.ended_at.is_(None))) == 1
    finally:
        wipe_database(engine)
