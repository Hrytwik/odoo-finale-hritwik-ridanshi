"""When a truck is confirmed the buyer is told, in the bell and on WhatsApp, how much has left the mill and the invoice."""
import json
from decimal import Decimal

import pytest

from app.core.auth import COOKIE_NAME, create_token
from app.core.events import broadcaster
from app.modules.notices import service, whatsapp
from tests.factories import make_buyer, make_user
from tests.test_dispatch_confirm import Store, confirm, truck_with


@pytest.fixture
def clerk(login_as):
    return login_as("dispatch")


@pytest.fixture
def events(monkeypatch):
    seen = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


@pytest.fixture
def outbox(monkeypatch):
    sent = []

    def fake(config, to, message, link=None, post=None):
        sent.append({"to": to, "message": message, "link": link})
        return whatsapp.SendResult("sent", None, "SM1")

    monkeypatch.setattr(whatsapp, "send_text", fake)
    return sent


def as_buyer(client, db, buyer):
    client.cookies.set(COOKIE_NAME, create_token(make_user(db, role="buyer", buyer_id=buyer.id).id))


def connect_whatsapp(client, login_as):
    login_as("owner")
    client.put("/api/messaging/settings", json={"account_sid": "ACtest", "auth_token": "tok", "from_number": "+17372508034",
                                                 "public_url": "https://mill.example", "enabled": True})
    login_as("dispatch")


@pytest.mark.parametrize("amount,text", [(216000, "\u20b92,16,000.00"), (1234567.5, "\u20b912,34,567.50"), (999, "\u20b9999.00"), (0, "\u20b90.00"), (100000, "\u20b91,00,000.00")])
def test_rupees_are_written_with_indian_grouping(amount, text):
    assert service.inr(amount) == text


def test_confirming_a_truck_tells_the_buyer_in_the_bell(client, db, clerk, events):
    store = Store(db, buyer=make_buyer(db, name="Sharma Fabrics"))
    roll = store.roll(1000)
    code = truck_with(client, db, (store, roll))
    out = confirm(client, code).json()
    as_buyer(client, db, store.buyer)
    mine = client.get("/api/portal/notifications").json()
    assert mine["unread"] == 1
    n = mine["items"][0]
    assert n["kind"] == "dispatch" and n["reason_label"] == "Order dispatched" and n["order_code"] == store.order.code
    assert f"1000 m of your order {store.order.code} has left the mill on truck KA01AB1234 (dispatch {code})" in n["message"]
    assert f"Your invoice {out['invoice_no']} is \u20b9" in n["message"]
    assert any(k == "notice.changed" for k, _ in events)


def test_the_invoice_amount_in_the_notice_is_the_invoice_line(client, db, clerk):
    store = Store(db, buyer=make_buyer(db))
    store.order.price_per_metre = Decimal("120.50")
    db.flush()
    code = truck_with(client, db, (store, store.roll(800)))
    out = confirm(client, code).json()
    inv = client.get(f"/api/invoices/{out['invoice_no']}").json()
    as_buyer(client, db, store.buyer)
    message = client.get("/api/portal/notifications").json()["items"][0]["message"]
    assert service.inr(inv["lines"][0]["amount"]) in message


def test_a_truck_with_two_orders_tells_the_buyer_once_for_each(client, db, clerk):
    a = Store(db, buyer=make_buyer(db))
    b = Store(db, buyer=a.buyer)
    code = truck_with(client, db, (a, a.roll(500)), (b, b.roll(300)))
    confirm(client, code)
    as_buyer(client, db, a.buyer)
    items = client.get("/api/portal/notifications").json()["items"]
    assert sorted(i["order_code"] for i in items) == sorted([a.order.code, b.order.code])
    assert all(i["kind"] == "dispatch" for i in items)


def test_it_also_goes_to_whatsapp_with_the_tracking_link(client, db, clerk, login_as, outbox):
    connect_whatsapp(client, login_as)
    store = Store(db, buyer=make_buyer(db, phone="98450 12345"))
    code = truck_with(client, db, (store, store.roll(1000)))
    confirm(client, code)
    assert len(outbox) == 1 and outbox[0]["to"] == "+919845012345"
    assert outbox[0]["link"] == f"https://mill.example/portal/orders/{store.order.code}" and "has left the mill" in outbox[0]["message"]
    as_buyer(client, db, store.buyer)
    assert client.get("/api/portal/notifications").json()["items"][0]["whatsapp_status"] == "sent"


def test_a_buyer_without_a_phone_still_gets_the_bell_notice(client, db, clerk, login_as, outbox):
    connect_whatsapp(client, login_as)
    store = Store(db, buyer=make_buyer(db, phone=None))
    confirm(client, truck_with(client, db, (store, store.roll(400))))
    assert outbox == []
    as_buyer(client, db, store.buyer)
    item = client.get("/api/portal/notifications").json()["items"][0]
    assert item["whatsapp_status"] == "skipped" and "no phone number" in item["whatsapp_detail"]


def test_a_failure_in_telling_the_buyer_never_undoes_the_confirmed_truck(client, db, clerk, monkeypatch):
    store = Store(db, buyer=make_buyer(db))
    code = truck_with(client, db, (store, store.roll(400)))
    monkeypatch.setattr(service, "notify_dispatched", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = confirm(client, code)
    assert r.status_code == 200 and r.json()["state"] == "dispatched" and r.json()["invoice_no"].startswith("INV-")


def test_another_buyer_is_not_told(client, db, clerk):
    store = Store(db, buyer=make_buyer(db))
    other = make_buyer(db)
    confirm(client, truck_with(client, db, (store, store.roll(400))))
    as_buyer(client, db, other)
    assert client.get("/api/portal/notifications").json() == {"unread": 0, "items": []}


def test_nothing_is_sent_for_a_truck_that_is_still_loading(db):
    from tests.factories import make_dispatch
    store = Store(db, buyer=make_buyer(db))
    truck = make_dispatch(db, store.buyer)
    assert service.notify_dispatched(db, truck.code) == []
