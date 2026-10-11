"""A buyer signs up with the email on their record and the invite code the owner gave them."""
import pytest

from app.core.auth import COOKIE_NAME
from app.modules.auth.signup import invite_code
from tests.factories import make_buyer, make_order

GOOD = "Sharma-pass9"


def body(buyer, **over):
    return {"email": buyer.email, "invite_code": invite_code(buyer), "password": GOOD, **over}


@pytest.fixture
def buyer(db):
    return make_buyer(db, name="Sharma Fabrics", email="Accounts@Sharma.example")


def test_the_invite_code_is_stable_and_belongs_to_one_buyer_and_email(db, buyer):
    other = make_buyer(db, email="b@other.example")
    assert invite_code(buyer) == invite_code(buyer) and len(invite_code(buyer)) == 9
    assert invite_code(buyer) != invite_code(other)
    before = invite_code(buyer)
    buyer.email = "new@sharma.example"
    assert invite_code(buyer) != before


def test_a_buyer_with_no_email_has_no_code(db):
    assert invite_code(make_buyer(db, email=None)) is None and invite_code(make_buyer(db, email="  ")) is None


def test_signing_up_makes_a_buyer_login_linked_to_the_buyer_and_starts_the_session(client, db, buyer):
    mine = make_order(db, buyer=buyer)
    make_order(db, buyer=make_buyer(db))
    r = client.post("/api/auth/signup", json=body(buyer))
    assert r.status_code == 201
    assert r.json()["role"] == "buyer" and r.json()["buyer_id"] == buyer.id and r.json()["username"] == "accounts@sharma.example"
    assert r.json()["display_name"] == "Sharma Fabrics" and COOKIE_NAME in client.cookies
    assert [o["code"] for o in client.get("/api/portal/orders").json()] == [mine.code]  # only their own


def test_the_email_may_be_typed_in_any_case_and_the_code_with_or_without_the_dash(client, db, buyer):
    r = client.post("/api/auth/signup", json=body(buyer, email=" ACCOUNTS@sharma.EXAMPLE ", invite_code=invite_code(buyer).replace("-", "").lower()))
    assert r.status_code == 201


def test_the_new_login_works_at_the_ordinary_login(client, db, buyer):
    client.post("/api/auth/signup", json=body(buyer))
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"username": "accounts@sharma.example", "password": GOOD})
    assert r.status_code == 200 and r.json()["role"] == "buyer"


@pytest.mark.parametrize("what", ["wrong_code", "unknown_email", "bad_email"])
def test_a_wrong_code_or_unknown_email_gets_the_same_answer(client, db, buyer, what):
    data = body(buyer)
    if what == "wrong_code":
        data["invite_code"] = "AAAA-AAAA"
    elif what == "unknown_email":
        data["email"] = "nobody@nowhere.example"
    else:
        data["email"] = "not-an-email"
    r = client.post("/api/auth/signup", json=data)
    assert r.status_code == 422 and r.json()["code"] == "SIGNUP_REFUSED" and COOKIE_NAME not in client.cookies


def test_a_code_from_another_buyer_does_not_work(client, db, buyer):
    other = make_buyer(db, email="b@other.example")
    assert client.post("/api/auth/signup", json=body(buyer, invite_code=invite_code(other))).status_code == 422


def test_one_account_per_email(client, db, buyer):
    assert client.post("/api/auth/signup", json=body(buyer)).status_code == 201
    client.cookies.clear()
    r = client.post("/api/auth/signup", json=body(buyer))
    assert r.status_code == 409 and r.json()["code"] == "ALREADY_REGISTERED"


@pytest.mark.parametrize("password", ["short1", "allletters", "12345678", "accounts-1"])
def test_a_weak_password_is_refused_with_the_reason(client, db, buyer, password):
    r = client.post("/api/auth/signup", json=body(buyer, password=password))
    assert r.status_code == 422 and r.json()["code"] == "WEAK_PASSWORD" and r.json()["field"] == "password"


def test_five_wrong_tries_lock_sign_up_for_that_address(client, db, buyer):
    for _ in range(5):
        assert client.post("/api/auth/signup", json=body(buyer, invite_code="AAAA-AAAA")).status_code == 422
    r = client.post("/api/auth/signup", json=body(buyer))
    assert r.status_code == 429 and r.json()["code"] == "TOO_MANY_ATTEMPTS"


def test_a_sign_up_never_makes_anything_but_a_buyer(client, db, buyer):
    r = client.post("/api/auth/signup", json={**body(buyer), "role": "owner", "buyer_id": 999})
    assert r.status_code == 201 and r.json()["role"] == "buyer" and r.json()["buyer_id"] == buyer.id


def test_the_owner_sees_each_buyers_code_and_whether_they_have_a_login(client, login_as, db, buyer):
    make_buyer(db, name="No Email Co", email=None)
    client.post("/api/auth/signup", json=body(buyer))
    login_as("owner")
    rows = {r["buyer_name"]: r for r in client.get("/api/auth/buyer-invites").json()}
    assert rows["Sharma Fabrics"]["invite_code"] == invite_code(buyer) and rows["Sharma Fabrics"]["has_account"] is True
    assert rows["No Email Co"]["invite_code"] is None and rows["No Email Co"]["has_account"] is False


@pytest.mark.parametrize("role", ["accountant", "supervisor", "store", "qc", "dispatch", "buyer"])
def test_only_the_owner_may_see_invite_codes(client, login_as, role):
    login_as(role)
    assert client.get("/api/auth/buyer-invites").status_code == 403
