"""B5 Task 2: load a dispatch (R11). A truck is for one buyer; only rolls in store can be loaded; over-shipping warns but never blocks.
Hand-worked summary: an order of 3,000 m with 1,000 m already on a confirmed truck and 2,500 m now loading -> previous 1,000,
loaded 2,500, remaining 0, over-shipped (500 m over)."""
import datetime as dt
import threading
import time

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import Dispatch, DispatchItem, Roll, User
from app.modules.dispatch import schemas as ds
from app.modules.dispatch import service
from tests.factories import (
    dye, make_buyer, make_dispatch, make_inspection, make_machine, make_order, make_roll, make_run, make_user,
    put_on_dispatch,
)
from tests.helpers import wipe_database

T0 = dt.datetime(2026, 10, 1, 8, tzinfo=dt.UTC)


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def clerk(login_as):
    return login_as("dispatch")


class Store:
    """One buyer's order with a weaving run; helpers make rolls in each state."""

    def __init__(self, db, buyer=None, qty=5000):
        self.db = db
        self.buyer = buyer or make_buyer(db)
        self.order = make_order(db, buyer=self.buyer, qty_metres=qty)
        self.weave = make_run(db, self.order, make_machine(db, stage="weaving"))

    def roll(self, metres=100, verdict="pass", dyed=True):
        roll = make_roll(self.db, self.order, self.weave, metres)
        if dyed:
            run = make_run(self.db, self.order, make_machine(self.db, stage="dyeing"))
            dye(self.db, roll, run)
            run.ended_at = run.started_at
            self.db.flush()
        if verdict:
            make_inspection(self.db, roll, verdict, inspected_at=T0)
        return roll


def create(client, buyer, **over):
    return client.post("/api/dispatches", json={"buyer_id": buyer.id, "vehicle_no": "KA01AB1234", **over})


def scan(client, dispatch_code, roll):
    return client.post(f"/api/dispatches/{dispatch_code}/items", json={"roll_code": roll.code})


def item_count(db) -> int:
    return db.scalar(select(func.count()).select_from(DispatchItem))


def roll_status(client, roll):
    return next(r["status"] for r in client.get(f"/api/rolls?order_code={roll.order.code}").json() if r["code"] == roll.code)


# ---- create -------------------------------------------------------------------------------------

def test_create_a_dispatch(client, db, clerk, events):
    buyer = make_buyer(db)
    r = create(client, buyer, vehicle_no="  KA01AB1234  ", driver_name="Imran")
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["code"].startswith("DSP-") and out["state"] == "loading" and out["buyer"]["id"] == buyer.id
    assert out["vehicle_no"] == "KA01AB1234" and out["driver_name"] == "Imran" and out["created_at"]
    assert out["rolls"] == [] and out["orders"] == [] and out["total_metres"] == 0.0
    assert out["invoice_no"] is None and out["dispatched_at"] is None and out["warnings"] == []
    assert events == [("dispatch.changed", out["id"])]


def test_create_checks(client, db, clerk, events):
    buyer = make_buyer(db)
    assert create(client, buyer, vehicle_no="V" * 30, driver_name="D" * 120).status_code == 201
    events.clear()
    r = create(client, buyer, vehicle_no="V" * 31)
    assert r.status_code == 422 and r.json()["field"] == "vehicle_no" and r.json()["code"] == "VALIDATION_ERROR"
    r = create(client, buyer, driver_name="D" * 121)
    assert r.status_code == 422 and r.json()["field"] == "driver_name"
    assert create(client, buyer, vehicle_no="   ").status_code == 422
    r = client.post("/api/dispatches", json={"buyer_id": 99999999, "vehicle_no": "KA01"})
    assert r.status_code == 404 and r.json()["field"] == "buyer_id"
    assert events == []


@pytest.mark.parametrize("role, ok", [("dispatch", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("supervisor", False), ("qc", False), ("buyer", False)])
def test_who_can_create(client, db, login_as, role, ok):
    login_as(role)
    assert (create(client, make_buyer(db)).status_code == 201) is ok


# ---- scan ---------------------------------------------------------------------------------------

def test_scanning_rolls_onto_a_truck(client, db, clerk, events):
    s = Store(db)
    a, b = s.roll(1000), s.roll(800)
    code = create(client, s.buyer).json()["code"]
    events.clear()
    r = scan(client, code, a)
    assert r.status_code == 200, r.text
    assert scan(client, code, b).status_code == 200
    out = client.get(f"/api/dispatches/{code}").json()
    assert [x["code"] for x in out["rolls"]] == [a.code, b.code] and {x["status"] for x in out["rolls"]} == {"loading"}
    assert out["total_metres"] == 1800.0 and out["warnings"] == []
    [row] = out["orders"]
    assert row == {"order_code": s.order.code, "ordered_m": 5000.0, "previously_dispatched_m": 0.0, "loaded_m": 1800.0,
                   "remaining_m": 3200.0, "over_shipped": False}
    assert roll_status(client, a) == "loading"
    assert events[:2] == [("dispatch.changed", out["id"]), ("roll.changed", a.id)]


def test_the_summary_after_an_earlier_truck_and_over_shipping_warns_but_loads(client, db, clerk):
    s = Store(db, qty=3000)
    earlier = make_dispatch(db, s.buyer, state="dispatched", dispatched_at=T0 + dt.timedelta(days=1))
    put_on_dispatch(db, s.roll(1000), earlier)
    big = s.roll(2500)
    code = create(client, s.buyer).json()["code"]
    assert scan(client, code, big).status_code == 200                      # over-shipping never blocks
    out = client.get(f"/api/dispatches/{code}").json()
    [row] = out["orders"]
    assert (row["previously_dispatched_m"], row["loaded_m"], row["remaining_m"], row["over_shipped"]) == (1000.0, 2500.0, 0.0, True)
    assert len(out["warnings"]) == 1 and s.order.code in out["warnings"][0] and "500" in out["warnings"][0]


def test_rolls_on_another_truck_that_is_still_loading_are_not_previously_dispatched(client, db, clerk):
    s = Store(db, qty=1000)
    other_truck = create(client, s.buyer).json()["code"]
    assert scan(client, other_truck, s.roll(400)).status_code == 200            # loaded, not confirmed: nothing has left
    this_truck = create(client, s.buyer).json()["code"]
    assert scan(client, this_truck, s.roll(300)).status_code == 200
    [row] = client.get(f"/api/dispatches/{this_truck}").json()["orders"]
    assert (row["previously_dispatched_m"], row["loaded_m"], row["remaining_m"]) == (0.0, 300.0, 700.0)


def test_a_truck_can_carry_two_orders_of_the_same_buyer(client, db, clerk):
    s = Store(db)
    other = Store(db, buyer=s.buyer)
    a, b = s.roll(100), other.roll(200)
    code = create(client, s.buyer).json()["code"]
    assert scan(client, code, a).status_code == 200 and scan(client, code, b).status_code == 200
    out = client.get(f"/api/dispatches/{code}").json()
    assert sorted(r["order_code"] for r in out["orders"]) == sorted([s.order.code, other.order.code])
    assert out["total_metres"] == 300.0


def refused(client, db, events, response, status, code, field, fragment=None):
    before = item_count(db)
    assert response.status_code == status, response.text
    assert response.json()["code"] == code and response.json()["field"] == field, response.json()
    if fragment:
        assert fragment in response.json()["message"], response.json()["message"]
    assert item_count(db) == before and events == []


def test_every_refusal_has_its_code_and_leaves_nothing_behind(client, db, clerk, events):
    s = Store(db)
    foreign = Store(db)                                             # another buyer's order
    code = create(client, s.buyer).json()["code"]
    other_code = create(client, s.buyer).json()["code"]
    on_this = s.roll()
    assert scan(client, code, on_this).status_code == 200
    on_other = s.roll()
    assert scan(client, other_code, on_other).status_code == 200
    rejected, rework, waiting, woven = s.roll(verdict="reject"), s.roll(verdict="rework"), s.roll(verdict=None), s.roll(verdict=None, dyed=False)
    events.clear()
    refused(client, db, events, scan(client, code, foreign.roll()), 409, "WRONG_BUYER", "roll_code")
    refused(client, db, events, scan(client, code, on_this), 409, "ALREADY_DISPATCHED", "roll_code", "this dispatch")
    refused(client, db, events, scan(client, code, on_other), 409, "ALREADY_DISPATCHED", "roll_code", "another")
    refused(client, db, events, scan(client, code, rejected), 409, "ROLL_NOT_PASSED", "roll_code", "rejected")
    refused(client, db, events, scan(client, code, rework), 409, "ROLL_NOT_PASSED", "roll_code", "awaiting_rework")
    refused(client, db, events, scan(client, code, waiting), 409, "ROLL_NOT_PASSED", "roll_code", "awaiting_qc")
    refused(client, db, events, scan(client, code, woven), 409, "ROLL_NOT_PASSED", "roll_code", "woven")
    refused(client, db, events, client.post(f"/api/dispatches/{code}/items", json={"roll_code": "R-9999999"}), 404,
            "NOT_FOUND", "roll_code")
    refused(client, db, events, client.post("/api/dispatches/DSP-9999999/items", json={"roll_code": on_this.code}), 404,
            "NOT_FOUND", "dispatch_code")


def test_a_confirmed_dispatch_is_locked(client, db, clerk, events):
    s = Store(db)
    done = make_dispatch(db, s.buyer, state="dispatched", dispatched_at=T0 + dt.timedelta(days=1))
    refused(client, db, events, scan(client, done.code, s.roll()), 409, "DISPATCH_LOCKED", "dispatch_code")
    roll = s.roll()
    put_on_dispatch(db, roll, done)
    r = client.delete(f"/api/dispatches/{done.code}/items/{roll.code}")
    assert r.status_code == 409 and r.json()["code"] == "DISPATCH_LOCKED"


# ---- take a roll off ----------------------------------------------------------------------------

def test_taking_a_roll_off_puts_it_back_in_store(client, db, clerk, events):
    s = Store(db)
    a, b = s.roll(100), s.roll(200)
    code = create(client, s.buyer).json()["code"]
    scan(client, code, a), scan(client, code, b)
    events.clear()
    r = client.delete(f"/api/dispatches/{code}/items/{a.code}")
    assert r.status_code == 200, r.text
    assert [x["code"] for x in r.json()["rolls"]] == [b.code] and r.json()["total_metres"] == 200.0
    assert roll_status(client, a) == "in_store"
    assert [k for k, _ in events] == ["dispatch.changed", "roll.changed"]
    assert scan(client, code, a).status_code == 200                      # it can be loaded again


def test_taking_off_a_roll_that_is_not_on_this_truck(client, db, clerk, events):
    s = Store(db)
    code = create(client, s.buyer).json()["code"]
    events.clear()
    for target in (s.roll().code, "R-9999999"):
        r = client.delete(f"/api/dispatches/{code}/items/{target}")
        assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND" and r.json()["field"] == "roll_code"
    assert events == []


# ---- list and read ------------------------------------------------------------------------------

def test_list_filters_and_order(client, db, clerk):
    buyer = make_buyer(db)
    first = create(client, buyer).json()["code"]
    done = make_dispatch(db, buyer, state="dispatched", dispatched_at=T0)
    second = create(client, buyer).json()["code"]
    codes = lambda url: [d["code"] for d in client.get(url).json()]  # noqa: E731
    assert codes("/api/dispatches") == [second, done.code, first]                      # newest first
    assert codes("/api/dispatches?state=loading") == [second, first]
    assert codes("/api/dispatches?state=dispatched") == [done.code]
    r = client.get("/api/dispatches?state=whatever")
    assert r.status_code == 422 and r.json()["field"] == "state"
    assert client.get("/api/dispatches/DSP-9999999").status_code == 404


@pytest.mark.parametrize("role, ok", [("dispatch", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("supervisor", False), ("qc", False), ("buyer", False)])
def test_who_can_read_and_load(client, db, login_as, role, ok):
    login_as(role)
    s = Store(db)
    dispatch = make_dispatch(db, s.buyer)
    roll = s.roll()
    assert (client.get("/api/dispatches").status_code == 200) is ok
    assert (client.get(f"/api/dispatches/{dispatch.code}").status_code == 200) is ok
    assert (scan(client, dispatch.code, roll).status_code == 200) is ok


# ---- two clerks, one roll ------------------------------------------------------------------------

def committed_trucks(engine):
    with Session(engine) as setup:
        s = Store(setup)
        roll = s.roll()
        trucks = [make_dispatch(setup, s.buyer), make_dispatch(setup, s.buyer)]
        setup.commit()
        return roll.id, roll.code, [t.code for t in trucks]


def test_two_clerks_scanning_one_roll_onto_two_trucks_at_once(engine):
    try:
        for _ in range(5):
            roll_id, roll_code, truck_codes = committed_trucks(engine)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(truck, roll_code=roll_code, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.scan_roll(session, truck, ds.ScanIn(roll_code=roll_code))
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go, args=(t,)) for t in truck_codes]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["ALREADY_DISPATCHED", "ok"], results
            with Session(engine) as check:
                assert check.scalar(select(func.count()).select_from(DispatchItem).where(DispatchItem.roll_id == roll_id)) == 1
            wipe_database(engine)
    finally:
        wipe_database(engine)


def test_a_scan_waits_for_whoever_holds_the_roll_lock(engine):
    roll_id, roll_code, truck_codes = committed_trucks(engine)
    outcome: list[str] = []

    def second():
        with Session(engine) as session:
            try:
                service.scan_roll(session, truck_codes[1], ds.ScanIn(roll_code=roll_code))
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            holder.scalar(select(Roll).where(Roll.id == roll_id).with_for_update())              # clerk A has the roll
            thread = threading.Thread(target=second)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "clerk B must be waiting on the roll lock"
            truck_a = holder.scalar(select(Dispatch).where(Dispatch.code == truck_codes[0]))
            holder.add(DispatchItem(dispatch_id=truck_a.id, roll_id=roll_id))
            holder.commit()
            thread.join(timeout=10)
        assert outcome == ["ALREADY_DISPATCHED"]
    finally:
        wipe_database(engine)
