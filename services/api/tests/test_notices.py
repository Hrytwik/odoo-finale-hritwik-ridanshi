"""Delay notices: the owner picks a reason, a sentence is drafted and edited, and it reaches only that order's buyer."""
import pytest

from app.core.auth import COOKIE_NAME, create_token
from app.core.events import broadcaster
from app.modules.llm.runtime import LlmConfig
from app.modules.llm.types import AdapterError, Completion
from app.modules.notices import service
from tests.factories import make_buyer, make_order, make_user


@pytest.fixture
def events(monkeypatch):
    seen = []
    monkeypatch.setattr(broadcaster, "publish", lambda kind, id=None: seen.append((kind, id)))
    return seen


def as_user(client, user):
    client.cookies.set(COOKIE_NAME, create_token(user.id))


class FakeAdapter:
    def __init__(self, text="", error=None):
        self.text, self.error, self.prompts = text, error, []

    def complete(self, system, turns, tools, options=None):
        self.prompts.append(turns[0].text)
        if self.error:
            raise self.error
        return Completion(self.text, [])


def with_model(monkeypatch, adapter):
    monkeypatch.setattr(service, "load_config", lambda db: LlmConfig("openai_compatible", "m", "http://localhost:1/v1", None, True, False))
    monkeypatch.setattr(service, "build_adapter", lambda cfg: adapter)


def test_without_a_model_the_draft_comes_from_a_fixed_template(client, login_as, db):
    order = make_order(db)
    login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "yarn_shortage"})
    assert r.status_code == 200 and r.json()["drafted_by_ai"] is False
    assert order.code in r.json()["message"] and "waiting for yarn" in r.json()["message"]


def test_with_a_model_the_sentence_is_written_by_it_from_the_reason_only(client, login_as, db, monkeypatch):
    order = make_order(db)
    adapter = FakeAdapter("We are sorry: your order is delayed by a machine repair.")
    with_model(monkeypatch, adapter)
    login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "machine_breakdown"})
    assert r.json() == {"message": "We are sorry: your order is delayed by a machine repair.", "drafted_by_ai": True}
    assert "Machine breakdown" in adapter.prompts[0] and order.code in adapter.prompts[0]


def test_when_the_model_fails_the_template_is_used_not_an_error(client, login_as, db, monkeypatch):
    order = make_order(db)
    with_model(monkeypatch, FakeAdapter(error=AdapterError("unreachable", "down")))
    login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "power_cut"})
    assert r.status_code == 200 and r.json()["drafted_by_ai"] is False and "power cut" in r.json()["message"]


def test_sending_a_notice_puts_it_in_that_buyers_bell_and_announces_it(client, login_as, db, events):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    owner = login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "yarn_shortage", "message": "  Your order is late: yarn.  "})
    assert r.status_code == 201 and r.json()["message"] == "Your order is late: yarn." and r.json()["reason_label"] == "Yarn shortage"
    assert ("notice.changed", r.json()["id"]) in events
    as_user(client, make_user(db, role="buyer", buyer_id=buyer.id))
    mine = client.get("/api/portal/notifications").json()
    assert mine["unread"] == 1 and mine["items"][0]["order_code"] == order.code and mine["items"][0]["read"] is False
    assert owner.id  # the owner was the sender


def test_a_buyer_never_sees_another_buyers_notices(client, login_as, db):
    a, b = make_buyer(db), make_buyer(db)
    order = make_order(db, buyer=a)
    login_as("owner")
    client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "Delayed."})
    as_user(client, make_user(db, role="buyer", buyer_id=b.id))
    assert client.get("/api/portal/notifications").json() == {"unread": 0, "items": []}


def test_opening_the_bell_marks_them_read_and_a_new_one_counts_again(client, login_as, db):
    buyer = make_buyer(db)
    order = make_order(db, buyer=buyer)
    login_as("owner")
    for text in ("First.", "Second."):
        client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": text})
    as_user(client, make_user(db, role="buyer", buyer_id=buyer.id))
    assert client.get("/api/portal/notifications").json()["unread"] == 2
    after = client.post("/api/portal/notifications/read").json()
    assert after["unread"] == 0 and [i["message"] for i in after["items"]] == ["Second.", "First."] and all(i["read"] for i in after["items"])
    owner_session = login_as("owner")
    client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "Third."})
    as_user(client, db.query(type(owner_session)).filter_by(buyer_id=buyer.id).first())
    assert client.get("/api/portal/notifications").json()["unread"] == 1


@pytest.mark.parametrize("role", ["accountant", "supervisor", "store", "qc", "dispatch", "buyer"])
def test_only_the_owner_may_draft_or_send(client, login_as, db, role):
    order = make_order(db)
    login_as(role)
    assert client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "other"}).status_code == 403
    assert client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "x"}).status_code == 403


@pytest.mark.parametrize("role", ["owner", "accountant", "supervisor", "store", "qc", "dispatch"])
def test_only_a_buyer_has_a_bell(client, login_as, role):
    login_as(role)
    assert client.get("/api/portal/notifications").status_code == 403
    assert client.post("/api/portal/notifications/read").status_code == 403


def test_a_draft_order_gets_no_notice(client, login_as, db):
    order = make_order(db, state="draft")
    login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice", json={"reason": "other", "message": "x"})
    assert r.status_code == 409 and r.json()["code"] == "ORDER_NOT_CONFIRMED"


def test_a_missing_order_is_a_404(client, login_as):
    login_as("owner")
    assert client.post("/api/orders/ORD-9999/delay-notice", json={"reason": "other", "message": "x"}).status_code == 404
    assert client.post("/api/orders/ORD-9999/delay-notice/draft", json={"reason": "other"}).status_code == 404


@pytest.mark.parametrize("body", [{"reason": "weather", "message": "x"}, {"reason": "other", "message": "   "}, {"reason": "other", "message": "x" * 401}, {"reason": "other"}])
def test_a_bad_notice_is_refused(client, login_as, db, body):
    order = make_order(db)
    login_as("owner")
    assert client.post(f"/api/orders/{order.code}/delay-notice", json=body).status_code == 422


def test_special_hyphens_and_spaces_from_the_model_become_ordinary_ones(client, login_as, db, monkeypatch):
    order = make_order(db)
    with_model(monkeypatch, FakeAdapter("Your order ORD\u20110001 is late\u202ftoday\u00a0sorry."))
    login_as("owner")
    r = client.post(f"/api/orders/{order.code}/delay-notice/draft", json={"reason": "other"})
    assert r.json()["message"] == "Your order ORD-0001 is late today sorry."
