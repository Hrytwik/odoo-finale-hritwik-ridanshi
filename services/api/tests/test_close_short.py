"""Closing an order short: the owner ends an order that will never reach its ordered metres.
Worked numbers: 1,000 m ordered; one roll of 400 m passed and dispatched; the other 600 m will never be made.
Closed short is a stage derived from `closed_short_at`, not a new order state."""
import datetime as dt

import pytest
from app.core.events import broadcaster
from app.db.models import Order
from tests.factories import (
    dye, make_buyer, make_dispatch, make_fabric_type, make_inspection, make_lot, make_machine, make_order, make_roll,
    make_run, make_user, make_yarn_type, put_on_dispatch,
)
from tests.helpers import violates
from tests.insights_world import build_mill
from tests.test_stock_views import one

BEGAN = dt.datetime(2026, 10, 8, tzinfo=dt.UTC)
SENT = dt.datetime(2026, 10, 9, tzinfo=dt.UTC)


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, object]] = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


def ship(db, order, weave, dyer, metres):
    """One roll woven, dyed, passed and sent on a confirmed truck."""
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=metres)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, roll, "pass")
    put_on_dispatch(db, roll, make_dispatch(db, order.buyer, state="dispatched", dispatched_at=SENT))
    return roll


def shipped_order(db, **kw):
    """1,000 m ordered, one 400 m roll woven, dyed, passed and sent. Nothing else is being made."""
    order = make_order(db, **kw)
    weave, dyer = make_machine(db, stage="weaving"), make_machine(db, stage="dyeing")
    return order, ship(db, order, weave, dyer, 400), weave, dyer


def close(client, order, reason="Buyer agreed to take less"):
    return client.post(f"/api/orders/{order.code}/close-short", json={"reason": reason})


# ---- the happy path -------------------------------------------------------------------------------------------

def test_the_owner_closes_an_order_short(client, db, login_as, events):
    owner = login_as("owner")
    order, *_ = shipped_order(db)
    assert client.get(f"/api/orders/{order.code}").json()["stage"] == "partly_dispatched"
    events.clear()
    r = close(client, order, "  Buyer agreed to take less  ")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "closed_short" and body["state"] == "confirmed"
    assert body["closed_short_reason"] == "Buyer agreed to take less"     # trimmed
    assert body["closed_short_at"] is not None
    assert body["yarn_status"] == "not_needed" and body["short_kg"] == 0
    row = db.get(Order, order.id)
    db.refresh(row)
    assert row.closed_short_by == owner.id
    assert events == [("order.changed", order.id), ("stock.changed", None)]    # its yarn reservation is released
    assert client.get(f"/api/orders/{order.code}").json()["stage"] == "closed_short"


def test_closing_leaves_the_progress_numbers_alone(client, db, login_as):
    login_as("owner")
    order, *_ = shipped_order(db)
    before = client.get(f"/api/orders/{order.code}").json()["progress"]
    after = close(client, order).json()["progress"]
    assert after == before and after["dispatched_m"] == 400.0


# ---- who may, and when ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["accountant", "supervisor", "store", "qc", "dispatch", "buyer"])
def test_only_the_owner_may_close_short(client, db, login_as, role):
    login_as(role)
    order, *_ = shipped_order(db)
    assert close(client, order).status_code == 403
    assert db.get(Order, order.id).closed_short_at is None


def test_not_signed_in_is_refused(client, db):
    order, *_ = shipped_order(db)
    assert close(client, order).status_code == 401


def test_a_missing_order_is_a_404(client, login_as):
    login_as("owner")
    assert client.post("/api/orders/ORD-9999/close-short", json={"reason": "gone"}).status_code == 404


@pytest.mark.parametrize("state", ["draft", "cancelled"])
def test_only_a_confirmed_order_can_be_closed_short(client, db, login_as, state):
    login_as("owner")
    r = close(client, make_order(db, state=state))
    assert r.status_code == 409 and r.json()["code"] == "ORDER_NOT_CONFIRMED"


def test_closing_twice_is_refused(client, db, login_as):
    login_as("owner")
    order, *_ = shipped_order(db)
    assert close(client, order).status_code == 200
    r = close(client, order, "second try")
    assert r.status_code == 409 and r.json()["code"] == "ORDER_ALREADY_CLOSED_SHORT"
    assert client.get(f"/api/orders/{order.code}").json()["closed_short_reason"] == "Buyer agreed to take less"


def test_nothing_dispatched_means_cancel_not_close_short(client, db, login_as):
    login_as("owner")
    r = close(client, make_order(db))
    assert r.status_code == 409 and r.json()["code"] == "NOTHING_DISPATCHED"


def test_an_order_dispatched_in_full_cannot_be_closed_short(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db, qty_metres=400)
    r = close(client, order)
    assert r.status_code == 409 and r.json()["code"] == "ORDER_FULLY_DISPATCHED"


def test_a_truck_still_loading_does_not_count_as_dispatched(client, db, login_as):
    login_as("owner")
    order = make_order(db)
    weaving = make_run(db, order, make_machine(db, stage="weaving"), started_at=BEGAN, ended_at=SENT)
    roll = make_roll(db, order, weaving)
    put_on_dispatch(db, roll, make_dispatch(db, order.buyer))               # state "loading"
    assert close(client, order).json()["code"] == "NOTHING_DISPATCHED"


@pytest.mark.parametrize("reason", ["", "   ", "ab", " ab ", "x" * 201])
def test_the_reason_is_three_to_two_hundred_characters_after_trimming(client, db, login_as, reason):
    login_as("owner")
    order, *_ = shipped_order(db)
    assert close(client, order, reason).status_code == 422
    assert db.get(Order, order.id).closed_short_at is None


@pytest.mark.parametrize("reason", ["abc", "x" * 200, "  abc  "])
def test_the_reason_boundaries_are_accepted(client, db, login_as, reason):
    login_as("owner")
    order, *_ = shipped_order(db)
    assert close(client, order, reason).status_code == 200


def test_a_missing_reason_is_a_422(client, db, login_as):
    login_as("owner")
    order, *_ = shipped_order(db)
    assert client.post(f"/api/orders/{order.code}/close-short", json={}).status_code == 422


# ---- nothing may still be in progress -------------------------------------------------------------------------

def refused_in_progress(client, order):
    r = close(client, order)
    assert r.status_code == 409 and r.json()["code"] == "ORDER_STILL_IN_PROGRESS", r.text


def test_refused_while_a_run_is_still_going(client, db, login_as):
    login_as("owner")
    order, _, weave, _ = shipped_order(db)
    make_run(db, order, weave)                          # started, not ended
    refused_in_progress(client, order)


def test_refused_while_a_roll_awaits_its_quality_check(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))      # dyed, no inspection yet
    refused_in_progress(client, order)


def test_refused_while_a_roll_is_in_rework(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, roll, "rework")
    refused_in_progress(client, order)


def test_refused_while_a_roll_is_on_a_truck_not_yet_confirmed(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, roll, "pass")
    put_on_dispatch(db, roll, make_dispatch(db, order.buyer))   # loading
    refused_in_progress(client, order)


def test_a_rejected_roll_does_not_block_closing(client, db, login_as):
    """The common case: a roll was rejected, nothing replaces it, the buyer takes less."""
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, roll, "reject")
    assert close(client, order).status_code == 200


def test_a_passed_roll_left_in_the_store_does_not_block_closing(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    roll = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, roll, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, roll, "pass")
    assert close(client, order).status_code == 200


# ---- reads treat it as finished -------------------------------------------------------------------------------

def late_codes(client):
    return {o["order_code"] for o in client.get("/api/insights/late-orders").json()}


def test_a_closed_order_leaves_the_late_list_and_has_no_delivery_estimate(client, db, login_as):
    login_as("owner")
    mill = build_mill(db)                      # order A: 480 m; order B: 480 m, due in 10 days
    order, other = mill.order_a, mill.order_b
    order.deadline = mill.today + dt.timedelta(days=1)         # cannot be met: weaving alone takes 2 days
    ship(db, order, mill.machines["weaving"], mill.machines["dyeing"], 100)
    assert order.code in late_codes(client)
    assert client.get(f"/api/orders/{order.code}/eta").status_code == 200
    assert close(client, order).status_code == 200
    assert order.code not in late_codes(client)
    r = client.get(f"/api/orders/{order.code}/eta")
    assert r.status_code == 409 and r.json()["code"] == "NOT_SCHEDULED"
    assert client.get(f"/api/orders/{order.code}").json()["delivery_date"] is None
    assert client.get(f"/api/orders/{other.code}/eta").status_code == 200       # the other order is still scheduled


def yarn_world(db):
    cotton = make_yarn_type(db, reorder_level_kg=10)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    make_lot(db, yarn_type=cotton, qty_kg=500)
    return cotton, fabric


def test_a_closed_order_asks_for_no_more_yarn(client, db, login_as):
    """1,000 m x 0.12 kg/m x 1.05 = 126 kg reserved while open; none once closed."""
    login_as("owner")
    cotton, fabric = yarn_world(db)
    order, *_ = shipped_order(db, fabric_type=fabric)

    def reserved():
        return float(one(db, "SELECT outstanding_kg FROM v_yarn_type_stock WHERE yarn_type_id = :y", y=cotton.id)["outstanding_kg"])

    assert reserved() == 126.0
    assert client.get(f"/api/orders/{order.code}").json()["yarn_status"] == "can_start"
    close(client, order)
    db.expire_all()
    assert reserved() == 0.0
    assert client.get(f"/api/orders/{order.code}").json()["yarn_status"] == "not_needed"
    assert client.get(f"/api/orders/{order.code}/yarn-check").json()["can_start"] is True
    assert float(one(db, "SELECT free_kg FROM v_yarn_type_stock WHERE yarn_type_id = :y", y=cotton.id)["free_kg"]) == 500.0


def test_a_closed_order_frees_yarn_for_another_orders_check(client, db, login_as):
    """Two orders want 126 kg each from 200 kg on hand: B is short while A is open, and not once A is closed."""
    login_as("owner")
    cotton = make_yarn_type(db, reorder_level_kg=10)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.12, wastage_pct=5)
    make_lot(db, yarn_type=cotton, qty_kg=200)
    a, *_ = shipped_order(db, fabric_type=fabric)
    b = make_order(db, fabric_type=fabric)
    assert client.get(f"/api/orders/{b.code}").json()["yarn_status"] == "short"
    close(client, a)
    assert client.get(f"/api/orders/{b.code}").json()["yarn_status"] == "can_start"


def test_a_closed_order_cannot_get_a_new_run_or_yarn_issue(client, db, login_as):
    login_as("supervisor")
    cotton, fabric = yarn_world(db)
    order, *_ = shipped_order(db, fabric_type=fabric)
    spin_machine = make_machine(db, stage="spinning")
    spinning = make_run(db, order, spin_machine, started_at=BEGAN, ended_at=SENT)
    login_as("owner")
    assert close(client, order).status_code == 200
    login_as("supervisor")
    worker_id = spinning.operator_worker_id
    r = client.post("/api/runs", json={"order_code": order.code, "machine_code": spin_machine.code,
                                             "operator_worker_id": worker_id})
    assert r.status_code == 409 and r.json()["code"] == "ORDER_CLOSED_SHORT", r.text


def test_a_closed_order_cannot_be_issued_yarn(client, db, login_as):
    """A spinning run left open after closing (a stale one) must still be refused yarn."""
    login_as("owner")
    cotton, fabric = yarn_world(db)
    order, *_ = shipped_order(db, fabric_type=fabric)
    spinning = make_run(db, order, make_machine(db, stage="spinning"), started_at=BEGAN, ended_at=SENT)
    lot = make_lot(db, yarn_type=cotton, qty_kg=100)
    assert close(client, order).status_code == 200
    spinning.ended_at = None
    db.flush()
    login_as("store")
    r = client.post("/api/movements/issue", json={"lot_code": lot.lot_code, "run_id": spinning.id, "qty_kg": 5})
    assert r.status_code == 409 and r.json()["code"] == "ORDER_CLOSED_SHORT", r.text


def test_a_closed_orders_rolls_cannot_be_loaded_on_a_truck(client, db, login_as):
    login_as("owner")
    order, _, weave, dyer = shipped_order(db)
    left = make_roll(db, order, make_run(db, order, weave, started_at=BEGAN, ended_at=SENT), metres=200)
    dye(db, left, make_run(db, order, dyer, started_at=BEGAN, ended_at=SENT))
    make_inspection(db, left, "pass")
    assert close(client, order).status_code == 200
    login_as("dispatch")
    truck = make_dispatch(db, order.buyer)
    r = client.post(f"/api/dispatches/{truck.code}/items", json={"roll_code": left.code})
    assert r.status_code == 409 and r.json()["code"] == "ORDER_CLOSED_SHORT", r.text


# ---- what the buyer sees --------------------------------------------------------------------------------------

def test_the_buyer_sees_the_closing_without_the_internal_user(client, db, login_as):
    buyer = make_buyer(db)
    order, *_ = shipped_order(db, buyer=buyer)
    login_as("owner")
    close(client, order, "Cloth rejected, buyer takes 400 m")
    login_as("buyer", buyer_id=buyer.id)
    r = client.get(f"/api/portal/orders/{order.code}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stage"] == "closed_short" and body["closed_short_reason"] == "Cloth rejected, buyer takes 400 m"
    assert body["closed_short_at"] is not None and "closed_short_by" not in body
    assert body["progress_pct"] == 40.0                          # 400 m of the 1,000 m ordered
    assert body["timeline"][-1]["label"] == "Order closed short: the rest will not be made"
    listed = client.get("/api/portal/orders").json()
    assert listed[0]["stage"] == "closed_short" and "closed_short_by" not in listed[0]


# ---- the database refuses a half-closed order -----------------------------------------------------------------

def test_the_database_wants_all_three_closing_fields_or_none(db):
    order, *_ = shipped_order(db)
    owner = make_user(db, role="owner")
    for fields in ({"closed_short_at": SENT}, {"closed_short_reason": "only a reason"},
                   {"closed_short_at": SENT, "closed_short_by": owner.id}):
        with violates("ck_orders_closed_short_all_or_none"), db.begin_nested():
            for key, value in fields.items():
                setattr(order, key, value)
            db.flush()
        db.expire(order)
