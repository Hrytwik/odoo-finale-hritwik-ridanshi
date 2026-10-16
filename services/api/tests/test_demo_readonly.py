"""The show-piece mode: a login ending in -demo can look at everything and change nothing; other logins are untouched."""
from contextlib import contextmanager

import pytest

from app.core import demo_readonly
from app.core.auth import COOKIE_NAME, create_token
from tests.factories import make_user


@pytest.fixture(autouse=True)
def same_session(db, monkeypatch):
    """The guard looks the user up itself; in a test the user only exists inside the test's own transaction."""
    @contextmanager
    def use():
        yield db

    monkeypatch.setattr(demo_readonly, "SessionLocal", use)


def sign_in(client, db, username, role="owner"):
    user = make_user(db, role=role, username=username)
    client.cookies.set(COOKIE_NAME, create_token(user.id))
    return user


NEW_ORDER = {"buyer_id": 1, "fabric_type_id": 1, "colour": "navy", "qty_metres": 100, "price_per_metre": 10, "deadline": "2026-12-01"}


def test_a_demo_login_can_read_everything(client, db):
    sign_in(client, db, "owner-demo")
    assert client.get("/api/orders").status_code == 200
    assert client.get("/api/stock").status_code == 200


def test_a_demo_login_cannot_write(client, db):
    sign_in(client, db, "owner-demo")
    for method, path in (("post", "/api/orders"), ("post", "/api/payments/buyer"), ("post", "/api/auth/change-password"), ("put", "/api/ai/settings"), ("post", "/api/uploads")):
        r = getattr(client, method)(path, json=NEW_ORDER)
        assert r.status_code == 403, (path, r.status_code)
        assert r.json()["code"] == "DEMO_READ_ONLY"


def test_a_demo_login_may_still_sign_out_and_ask_questions(client, db):
    sign_in(client, db, "owner-demo")
    assert client.post("/api/ai/copilot", json={"question": "hi", "history": [], "language": "English"}).status_code != 403
    assert client.post("/api/auth/logout").status_code == 204


def test_a_normal_login_is_never_blocked(client, db):
    sign_in(client, db, "owner")
    r = client.post("/api/orders", json=NEW_ORDER)
    assert r.status_code != 403 or r.json()["code"] != "DEMO_READ_ONLY"


def test_a_visitor_with_no_login_is_not_treated_as_a_demo_login(client):
    r = client.post("/api/orders", json=NEW_ORDER)
    assert r.status_code == 401
