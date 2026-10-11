"""B5 Task 3: confirm a dispatch (R12) and the invoice. One line per order; amount = metres x rate rounded half up;
the invoice total is the sum of the rounded lines. Hand-worked numbers: 1,800 m at 120 = 216,000.00; 333.333 m at 120.50
= 40,166.63 (40,166.6265); total 256,166.63."""
import datetime as dt
import threading
import time
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import broadcaster
from app.db.models import BuyerPayment, Dispatch, DispatchItem, Invoice, User
from app.modules.dispatch import schemas as ds
from app.modules.dispatch import service
from tests.factories import make_buyer, make_machine, make_order, make_roll, make_run, make_user
from tests.helpers import wipe_database
from tests.test_dispatch_load import Store, T0, create, scan


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def clerk(login_as):
    return login_as("dispatch")


def confirm(client, code):
    return client.post(f"/api/dispatches/{code}/confirm")


def invoice_count(db) -> int:
    return db.scalar(select(func.count()).select_from(Invoice))


def truck_with(client, db, *pairs):
    """pairs of (Store, roll) for one buyer; returns the dispatch code."""
    buyer = pairs[0][0].buyer
    code = create(client, buyer).json()["code"]
    for _, roll in pairs:
        assert scan(client, code, roll).status_code == 200
    return code


# ---- the invoice ---------------------------------------------------------------------------------

def test_the_worked_invoice_two_orders_two_lines(client, db, clerk, events):
    a = Store(db)
    b = Store(db, buyer=a.buyer)
    b.order.price_per_metre = Decimal("120.50")
    db.flush()
    r1, r2, r3 = a.roll(1000), a.roll(800), b.roll(Decimal("333.333"))
    code = truck_with(client, db, (a, r1), (a, r2), (b, r3))
    events.clear()
    r = confirm(client, code)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["state"] == "dispatched" and out["dispatched_at"] and out["invoice_no"].startswith("INV-")
    assert {x["status"] for x in out["rolls"]} == {"dispatched"}
    assert events[0] == ("dispatch.changed", out["id"]) and {k for k, _ in events} == {"dispatch.changed", "roll.changed", "notice.changed"}  # the buyer is told too
    assert [i for k, i in events if k == "roll.changed"] == sorted(x.id for x in (r1, r2, r3))
    inv = client.get(f"/api/invoices/{out['invoice_no']}").json()
    assert inv["issued_at"] == out["dispatched_at"] and inv["dispatch_code"] == code and inv["vehicle_no"] == "KA01AB1234"
    assert inv["buyer"]["id"] == a.buyer.id
    la, lb = sorted(inv["lines"], key=lambda x: x["order_code"] == b.order.code)
    assert (la["order_code"], la["metres"], la["rate"], la["amount"]) == (a.order.code, 1800.0, 120.0, 216000.0)
    assert la["roll_codes"] == [r1.code, r2.code] and la["fabric"] == a.order.fabric_type.name and la["colour"] == "navy"
    assert (lb["order_code"], lb["metres"], lb["rate"], lb["amount"]) == (b.order.code, 333.333, 120.5, 40166.63)
    assert inv["total_amount"] == 256166.63 and inv["paid_amount"] == 0.0 and inv["balance"] == 256166.63


def test_the_total_is_the_sum_of_the_rounded_lines(client, db, clerk):
    """Two lines of 10.005 m at 1.00 each round to 10.01; the total must be 20.02, not 20.01 (rounding the exact sum)."""
    a = Store(db)
    b = Store(db, buyer=a.buyer)
    for s in (a, b):
        s.order.price_per_metre = Decimal("1.00")
    db.flush()
    code = truck_with(client, db, (a, a.roll(Decimal("10.005"))), (b, b.roll(Decimal("10.005"))))
    inv = client.get(f"/api/invoices/{confirm(client, code).json()['invoice_no']}").json()
    assert sorted(l["amount"] for l in inv["lines"]) == [10.01, 10.01] and inv["total_amount"] == 20.02


def test_over_shipped_metres_are_billed(client, db, clerk):
    s = Store(db, qty=1000)
    code = truck_with(client, db, (s, s.roll(1500)))
    inv = client.get(f"/api/invoices/{confirm(client, code).json()['invoice_no']}").json()
    assert inv["lines"][0]["metres"] == 1500.0 and inv["total_amount"] == 180000.0


def test_the_rest_of_the_system_sees_the_dispatch(client, db, login_as):
    login_as("dispatch")
    s = Store(db, qty=2000)
    first = s.roll(1200)
    second = s.roll(800)
    code = truck_with(client, db, (s, first))
    out = confirm(client, code).json()
    login_as("owner")
    o = client.get(f"/api/orders/{s.order.code}").json()
    assert o["progress"]["dispatched_m"] == 1200.0 and o["stage"] == "partly_dispatched"
    p = client.get(f"/api/rolls/{first.code}/passport").json()
    assert p["roll"]["status"] == "dispatched"
    assert p["dispatch"]["code"] == code and p["dispatch"]["invoice_no"] == out["invoice_no"] and p["dispatch"]["dispatched_at"]
    login_as("dispatch")
    code2 = truck_with(client, db, (s, second))
    assert confirm(client, code2).status_code == 200
    login_as("owner")
    o = client.get(f"/api/orders/{s.order.code}").json()
    assert o["progress"]["dispatched_m"] == 2000.0 and o["stage"] == "dispatched"


# ---- refusals ------------------------------------------------------------------------------------

def test_an_empty_truck_cannot_be_confirmed(client, db, clerk, events):
    s = Store(db)
    code = create(client, s.buyer).json()["code"]
    events.clear()
    r = confirm(client, code)
    assert r.status_code == 409 and r.json()["code"] == "EMPTY_DISPATCH" and r.json()["field"] == "dispatch_code"
    assert invoice_count(db) == 0 and events == []
    assert client.get(f"/api/dispatches/{code}").json()["state"] == "loading"


def test_a_second_confirm_and_any_change_after_it_are_locked_and_make_no_second_invoice(client, db, clerk):
    s = Store(db)
    roll = s.roll()
    code = truck_with(client, db, (s, roll))
    assert confirm(client, code).status_code == 200
    again = confirm(client, code)
    assert again.status_code == 409 and again.json()["code"] == "DISPATCH_LOCKED"
    assert scan(client, code, s.roll()).json()["code"] == "DISPATCH_LOCKED"
    assert client.delete(f"/api/dispatches/{code}/items/{roll.code}").json()["code"] == "DISPATCH_LOCKED"
    assert invoice_count(db) == 1
    assert client.get(f"/api/dispatches/{code}").json()["total_metres"] == 100.0


def test_unknown_dispatch_is_404(client, db, clerk):
    r = confirm(client, "DSP-9999999")
    assert r.status_code == 404 and r.json()["field"] == "dispatch_code"


@pytest.mark.parametrize("role, ok", [("dispatch", True), ("owner", True), ("accountant", False), ("store", False),
                                      ("supervisor", False), ("qc", False), ("buyer", False)])
def test_who_can_confirm(client, db, login_as, role, ok):
    s = Store(db)
    login_as("dispatch")
    code = truck_with(client, db, (s, s.roll()))
    login_as(role)
    assert (confirm(client, code).status_code == 200) is ok


# ---- reading an invoice -----------------------------------------------------------------------------

def invoice_for(client, db, buyer=None):
    s = Store(db, buyer=buyer)
    code = truck_with(client, db, (s, s.roll(100)))
    return s, confirm(client, code).json()["invoice_no"]


def test_paid_and_balance_come_from_the_payments(client, db, clerk):
    s, no = invoice_for(client, db)
    inv = db.scalar(select(Invoice).where(Invoice.invoice_no == no))
    db.add_all([BuyerPayment(invoice_id=inv.id, amount=Decimal("4000.00"), received_at=dt.date(2026, 10, 12)),
                BuyerPayment(invoice_id=inv.id, amount=Decimal("1500.50"), received_at=dt.date(2026, 10, 13))])
    db.flush()
    out = client.get(f"/api/invoices/{no}").json()
    assert (out["total_amount"], out["paid_amount"], out["balance"]) == (12000.0, 5500.5, 6499.5)


@pytest.mark.parametrize("role", ["dispatch", "accountant", "owner"])
def test_staff_roles_that_may_read_invoices(client, db, login_as, role):
    login_as("dispatch")
    s, no = invoice_for(client, db)
    login_as(role)
    assert client.get(f"/api/invoices/{no}").status_code == 200


@pytest.mark.parametrize("role", ["store", "supervisor", "qc"])
def test_other_staff_roles_cannot_read_invoices(client, db, login_as, role):
    login_as("dispatch")
    s, no = invoice_for(client, db)
    login_as(role)
    assert client.get(f"/api/invoices/{no}").status_code == 403


def test_a_buyer_reads_their_own_invoice_and_a_foreign_one_looks_like_a_missing_one(client, db, login_as):
    login_as("dispatch")
    mine = make_buyer(db)
    _, own_no = invoice_for(client, db, buyer=mine)
    _, foreign_no = invoice_for(client, db)
    buyer_user = make_user(db, role="buyer", buyer_id=mine.id)
    from app.core.auth import COOKIE_NAME, create_token
    client.cookies.set(COOKIE_NAME, create_token(buyer_user.id))
    assert client.get(f"/api/invoices/{own_no}").status_code == 200
    foreign = client.get(f"/api/invoices/{foreign_no}")
    missing = client.get("/api/invoices/INV-9999999")
    assert foreign.status_code == missing.status_code == 404
    assert foreign.content == missing.content and foreign.json()["code"] == "NOT_FOUND"


def test_anonymous_gets_401_and_staff_get_404_for_a_missing_invoice(client, db, login_as):
    login_as("owner")
    assert client.get("/api/invoices/INV-9999999").status_code == 404
    client.cookies.clear()
    assert client.get("/api/invoices/INV-9999999").status_code == 401


# ---- a line too big for its column, and two requests at once ----------------------------------------------

def committed_truck(engine, rolls=1, price=Decimal("120"), metres=100):
    with Session(engine) as setup:
        s = Store(setup)
        s.order.price_per_metre = price
        s.order.qty_metres = Decimal("1000000")
        made = [s.roll(metres) for _ in range(rolls)]
        truck = Dispatch(code="DSP-9990", buyer_id=s.buyer.id, vehicle_no="KA01AB1234", state="loading")
        setup.add(truck)
        setup.flush()
        for roll in made:
            setup.add(DispatchItem(dispatch_id=truck.id, roll_id=roll.id))
        setup.commit()
        return truck.code, truck.id


def test_an_invoice_line_too_big_for_its_column_is_a_clean_422_and_the_truck_stays_loading(engine, monkeypatch):
    published = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: published.append(kind))
    code, truck_id = committed_truck(engine, price=Decimal("100000000"), metres=Decimal("1000000"))
    try:
        with Session(engine) as session:
            with pytest.raises(AppError) as err:
                service.confirm_dispatch(session, code)
            assert err.value.code == "NUMBER_TOO_LARGE" and err.value.status == 422
        with Session(engine) as check:
            assert check.scalar(select(Dispatch.state).where(Dispatch.id == truck_id)) == "loading"
            assert check.scalar(select(func.count()).select_from(Invoice)) == 0
        assert published == []
    finally:
        wipe_database(engine)


def test_two_confirms_at_once_make_exactly_one_invoice(engine):
    try:
        for _ in range(5):
            code, truck_id = committed_truck(engine, rolls=2)
            barrier = threading.Barrier(2)
            results: list[str] = []

            def go(code=code, results=results, barrier=barrier):
                with Session(engine) as session:
                    barrier.wait()
                    try:
                        service.confirm_dispatch(session, code)
                        results.append("ok")
                    except AppError as exc:
                        results.append(exc.code)

            threads = [threading.Thread(target=go) for _ in range(2)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sorted(results) == ["DISPATCH_LOCKED", "ok"], results
            with Session(engine) as check:
                assert check.scalar(select(func.count()).select_from(Invoice)) == 1
            wipe_database(engine)
    finally:
        wipe_database(engine)


def _held_dispatch(engine, action):
    """A session holds the truck's row lock and confirms it by hand while another request waits; then the waiter answers."""
    code, truck_id = committed_truck(engine, rolls=1)
    outcome: list[str] = []

    def waiter():
        with Session(engine) as session:
            try:
                action(session, code)
                outcome.append("ok")
            except AppError as exc:
                outcome.append(exc.code)

    try:
        with Session(engine) as holder:
            truck = holder.scalar(select(Dispatch).where(Dispatch.id == truck_id).with_for_update())
            thread = threading.Thread(target=waiter)
            thread.start()
            time.sleep(0.7)
            assert thread.is_alive() and outcome == [], "the second request must be waiting on the truck's lock"
            truck.state, truck.dispatched_at = "dispatched", T0
            holder.commit()
            thread.join(timeout=10)
        with Session(engine) as check:
            assert check.scalar(select(func.count()).select_from(Invoice)) == 0
        return outcome
    finally:
        wipe_database(engine)


def test_a_scan_that_waits_for_a_confirm_is_then_refused(engine):
    def scan_one(session, code):
        # the truck is checked before the roll, so a waiting scan is refused as DISPATCH_LOCKED whatever roll it names
        service.scan_roll(session, code, ds.ScanIn(roll_code="R-0001"))

    assert _held_dispatch(engine, scan_one) == ["DISPATCH_LOCKED"]


def test_a_confirm_that_waits_for_another_confirm_is_then_refused(engine):
    assert _held_dispatch(engine, service.confirm_dispatch) == ["DISPATCH_LOCKED"]
