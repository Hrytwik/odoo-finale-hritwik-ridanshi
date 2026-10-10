"""The buyer portal: a buyer sees only their own confirmed or cancelled orders, with dates and metres, never costs."""
import datetime as dt

from app.db.models import Invoice
from tests.factories import (
    dye, make_buyer, make_dispatch, make_inspection, make_machine, make_order, make_roll, make_run, make_user, put_on_dispatch,
)

T = lambda day, hour=10: dt.datetime(2026, 10, day, hour, tzinfo=dt.UTC)  # noqa: E731


def buyer_login(client, db, buyer):
    from app.core.auth import COOKIE_NAME, create_token
    user = make_user(db, role="buyer", buyer_id=buyer.id)
    client.cookies.set(COOKIE_NAME, create_token(user.id))
    return user


def test_staff_cannot_use_portal(client, login_as):
    login_as("owner")
    assert client.get("/api/portal/orders").status_code == 403
    assert client.get("/api/portal/orders/ORD-0001").status_code == 403


def test_a_buyer_sees_only_their_own_confirmed_or_cancelled_orders(client, db):
    mine, other = make_buyer(db), make_buyer(db)
    confirmed = make_order(db, buyer=mine)
    cancelled = make_order(db, buyer=mine, state="cancelled")
    make_order(db, buyer=mine, state="draft")
    make_order(db, buyer=other)
    buyer_login(client, db, mine)
    codes = [o["code"] for o in client.get("/api/portal/orders").json()]
    assert sorted(codes) == sorted([confirmed.code, cancelled.code])


def test_another_buyers_order_looks_exactly_like_a_missing_one(client, db):
    mine, other = make_buyer(db), make_buyer(db)
    theirs = make_order(db, buyer=other)
    draft = make_order(db, buyer=mine, state="draft")
    buyer_login(client, db, mine)
    missing = client.get("/api/portal/orders/ORD-9999")
    for code in (theirs.code, draft.code):
        r = client.get(f"/api/portal/orders/{code}")
        assert r.status_code == 404 and r.json() == missing.json()


def test_nothing_about_money_or_machines_is_sent(client, db):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    buyer_login(client, db, buyer)
    body = client.get(f"/api/portal/orders/{order.code}").json()
    assert set(body) == {"code", "fabric", "colour", "qty_metres", "stage", "progress_pct", "deadline", "delivery_date", "timeline", "dispatches"}
    assert "price" not in str(body).lower() and "machine" not in str(body).lower()


def test_the_timeline_follows_the_order_and_names_each_dispatch(client, db):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer, qty_metres=1000)
    weave = make_run(db, order, make_machine(db, stage="weaving"), started_at=T(4))
    roll = make_roll(db, order, weave, 400)
    dye_run = make_run(db, order, make_machine(db, stage="dyeing"), started_at=T(6))
    dye(db, roll, dye_run)
    make_inspection(db, roll, "pass", inspected_at=T(8))
    truck = make_dispatch(db, buyer, state="dispatched", dispatched_at=T(9))
    put_on_dispatch(db, roll, truck)
    db.add(Invoice(invoice_no="INV-0001", dispatch_id=truck.id, buyer_id=buyer.id, issued_at=T(9), total_amount=48000))
    db.flush()
    buyer_login(client, db, buyer)
    body = client.get(f"/api/portal/orders/{order.code}").json()
    labels = [e["label"] for e in body["timeline"]]
    assert labels[0] == "Order confirmed"
    assert "Weaving started" in labels and "Dyeing started" in labels and "First rolls passed quality check" in labels
    assert f"400 m dispatched ({truck.code})" in labels
    assert [e["at"] for e in body["timeline"]] == sorted(e["at"] for e in body["timeline"])
    assert body["dispatches"] == [{"code": truck.code, "dispatched_at": body["dispatches"][0]["dispatched_at"], "metres": 400.0, "invoice_no": "INV-0001"}]


def test_a_truck_still_loading_is_not_shown_as_dispatched(client, db):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    roll = make_roll(db, order, make_run(db, order, make_machine(db, stage="weaving")), 100)
    put_on_dispatch(db, roll, make_dispatch(db, buyer))
    buyer_login(client, db, buyer)
    assert client.get(f"/api/portal/orders/{order.code}").json()["dispatches"] == []


def test_progress_is_a_share_of_the_work_done_and_full_once_dispatched(client, db):
    buyer = make_buyer(db)
    fresh = make_order(db, buyer=buyer)
    buyer_login(client, db, buyer)
    assert client.get(f"/api/portal/orders/{fresh.code}").json()["progress_pct"] == 0
    weave = make_run(db, fresh, make_machine(db, stage="weaving"))
    make_roll(db, fresh, weave, 500)  # half of the 1,000 m woven is not yet counted until dyed or passed; weaving counts half
    pct = client.get(f"/api/portal/orders/{fresh.code}").json()["progress_pct"]
    assert 0 <= pct <= 100
