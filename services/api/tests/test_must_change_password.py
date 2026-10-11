"""A login the owner creates or resets carries a temporary password: its owner must choose their own before doing anything else.
The flag is `users.must_change_password`. It is set when the owner creates a login or resets someone else's password, it is
cleared only by a successful change of password, and while it is set every request except the few below is refused with 403
PASSWORD_CHANGE_REQUIRED, so the rule holds on the server and not only on the screen."""
import re

import pytest

from app.core.auth import hash_password
from app.db.models import User
from app.main import app
from tests.factories import make_buyer, make_user

TEMP = "temporary-pass-1"
CHOSEN = "my-own-choice-9"

# what a person who still has to change their password may do: see who they are, change it, sign out, sign in or up, health
ALLOWED_WHILE_PENDING = {
    ("GET", "/api/auth/me"), ("POST", "/api/auth/change-password"), ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/login"), ("POST", "/api/auth/signup"), ("GET", "/api/health"),
    ("GET", "/api/events"),   # a stream of event names and row numbers only; it reads the cookie, not the database
}


def owner_creates(client, login_as, db, role="supervisor", username="ravi"):
    login_as("owner")
    r = client.post("/api/users", json={"username": username, "password": TEMP, "role": role})
    assert r.status_code == 201, r.text
    return r.json()


def sign_in(client, username, password):
    client.cookies.clear()
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


# ---- when the flag is set -------------------------------------------------------------------------------------

def test_a_login_the_owner_creates_must_change_its_password(client, db, login_as):
    created = owner_creates(client, login_as, db)
    assert created["must_change_password"] is True
    assert db.get(User, created["id"]).must_change_password is True
    assert sign_in(client, "ravi", TEMP)["must_change_password"] is True


def test_an_owner_reset_of_someone_elses_password_sets_it_again(client, db, login_as):
    worker = make_user(db, role="supervisor", password_hash=hash_password("old-secret-1"), must_change_password=False)
    login_as("owner")
    r = client.patch(f"/api/users/{worker.id}", json={"password": TEMP})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert sign_in(client, worker.username, TEMP)["must_change_password"] is True


def test_a_patch_that_does_not_touch_the_password_leaves_the_flag_alone(client, db, login_as):
    worker = make_user(db, role="supervisor", must_change_password=False)
    login_as("owner")
    client.patch(f"/api/users/{worker.id}", json={"worker_id": None})
    assert db.get(User, worker.id).must_change_password is False


def test_the_owner_choosing_their_own_new_password_is_not_forced_to_change_it_again(client, db, login_as):
    owner = login_as("owner", must_change_password=False)
    r = client.patch(f"/api/users/{owner.id}", json={"password": CHOSEN})
    assert r.status_code == 200 and r.json()["must_change_password"] is False


def test_a_login_made_directly_is_not_flagged(db):
    """Seeding and buyer sign-up build the User themselves, so the column's own default must be False."""
    assert make_user(db, role="owner").must_change_password is False


# ---- what a flagged person may do -----------------------------------------------------------------------------

def test_a_flagged_person_is_refused_everything_but_the_allowed_few(client, db, login_as):
    owner_creates(client, login_as, db)
    sign_in(client, "ravi", TEMP)
    refused = 0
    for path, operations in app.openapi()["paths"].items():
        for method in operations:
            if method not in ("get", "post", "put", "patch", "delete") or (method.upper(), path) in ALLOWED_WHILE_PENDING:
                continue
            url = re.sub(r"\{[^}]+\}", "X-1", path)
            r = client.request(method.upper(), url, json={} if method in ("post", "put", "patch") else None)
            assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED", \
                f"{method.upper()} {path} answered {r.status_code} {r.text[:80]} to someone who must change their password"
            refused += 1
    assert refused > 50          # the sweep really walked the API


def test_a_flagged_person_can_still_see_who_they_are_and_sign_out(client, db, login_as):
    owner_creates(client, login_as, db)
    sign_in(client, "ravi", TEMP)
    assert client.get("/api/auth/me").json()["must_change_password"] is True
    assert client.post("/api/auth/logout").status_code == 204


def test_a_flagged_buyer_is_held_too(client, db, login_as):
    buyer = make_buyer(db)
    login_as("owner")
    client.post("/api/users", json={"username": "kavya@kavya.example", "password": TEMP, "role": "buyer", "buyer_id": buyer.id})
    sign_in(client, "kavya@kavya.example", TEMP)
    r = client.get("/api/portal/orders")
    assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED"


# ---- clearing it ----------------------------------------------------------------------------------------------

def test_changing_the_password_clears_the_flag_and_opens_the_app(client, db, login_as):
    created = owner_creates(client, login_as, db)
    sign_in(client, "ravi", TEMP)
    r = client.post("/api/auth/change-password", json={"current_password": TEMP, "new_password": CHOSEN})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert db.get(User, created["id"]).must_change_password is False
    assert client.get("/api/orders").status_code == 200          # the same session, no new sign-in needed
    assert sign_in(client, "ravi", CHOSEN)["must_change_password"] is False


@pytest.mark.parametrize("body,code", [
    ({"current_password": "wrong-pass-123", "new_password": CHOSEN}, "WRONG_PASSWORD"),
    ({"current_password": TEMP, "new_password": TEMP}, "SAME_PASSWORD"),
    ({"current_password": TEMP, "new_password": "short"}, "WEAK_PASSWORD"),
])
def test_a_failed_change_leaves_the_flag_set(client, db, login_as, body, code):
    created = owner_creates(client, login_as, db)
    sign_in(client, "ravi", TEMP)
    r = client.post("/api/auth/change-password", json=body)
    assert r.status_code == 422 and r.json()["code"] == code
    assert db.get(User, created["id"]).must_change_password is True
    assert client.get("/api/orders").status_code == 403


def test_the_owner_sees_who_has_not_yet_changed_their_password(client, db, login_as):
    created = owner_creates(client, login_as, db)
    login_as("owner")
    rows = {u["id"]: u for u in client.get("/api/users").json()}
    assert rows[created["id"]]["must_change_password"] is True
