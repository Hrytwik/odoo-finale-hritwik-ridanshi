"""Login hardening: guess limiting, no timing hint about usernames, password rules, changing a password, session binding, headers."""
import bcrypt
import pytest

from app.config import settings
from app.core import auth as auth_module
from app.core.auth import COOKIE_NAME, hash_password
from app.core.login_guard import LoginGuard, guard
from app.core.passwords import (
    BCRYPT_COST, DUMMY_HASH, bcrypt_cost, check_new_password, fingerprint, needs_rehash,
)
from tests.factories import make_user


def login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def user_with(db, username="ravi", password="rightpass1", **kw):
    return make_user(db, username=username, password_hash=hash_password(password), **kw)


# ---------- the hash itself ----------

def test_passwords_are_stored_as_bcrypt_at_the_set_work_factor(db):
    user = user_with(db)
    assert user.password_hash.startswith("$2b$") and bcrypt_cost(user.password_hash) == BCRYPT_COST == 12
    assert "rightpass1" not in user.password_hash


def test_two_users_with_the_same_password_have_different_hashes(db):
    a, b = user_with(db, "a1"), user_with(db, "b1")
    assert a.password_hash != b.password_hash


def test_a_weaker_stored_hash_is_replaced_on_the_next_good_login(client, db):
    weak = bcrypt.hashpw(b"rightpass1", bcrypt.gensalt(rounds=4)).decode()
    user = make_user(db, username="old", password_hash=weak)
    assert needs_rehash(user.password_hash)
    assert login(client, "old", "rightpass1").status_code == 200
    db.refresh(user)
    assert bcrypt_cost(user.password_hash) == BCRYPT_COST and not needs_rehash(user.password_hash)
    assert login(client, "old", "rightpass1").status_code == 200


def test_a_wrong_password_never_rehashes_anything(client, db):
    weak = bcrypt.hashpw(b"rightpass1", bcrypt.gensalt(rounds=4)).decode()
    user = make_user(db, username="old", password_hash=weak)
    login(client, "old", "wrong-wrong1")
    db.refresh(user)
    assert user.password_hash == weak


def test_rehash_is_only_for_bcrypt_hashes_that_are_too_weak():
    assert not needs_rehash(hash_password("x" * 10))
    assert not needs_rehash("not-a-bcrypt-hash")


# ---------- no hint about which usernames exist ----------

def test_an_unknown_username_costs_a_password_check_like_a_wrong_password(client, db, monkeypatch):
    seen = []
    real = auth_module.verify_password
    monkeypatch.setattr("app.modules.auth.router.verify_password", lambda p, h: seen.append(h) or real(p, h))
    user_with(db, "ravi")
    login(client, "nobody", "whatever12")
    assert seen == [DUMMY_HASH]


def test_the_error_is_the_same_for_a_wrong_username_and_a_wrong_password(client, db):
    user_with(db, "ravi")
    a, b = login(client, "nobody", "whatever12"), login(client, "ravi", "wrong-pass1")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


# ---------- limiting guesses ----------

def test_five_wrong_passwords_lock_the_username(client, db):
    user_with(db, "ravi")
    for _ in range(5):
        assert login(client, "ravi", "wrong-pass1").status_code == 401
    r = login(client, "ravi", "wrong-pass1")
    assert r.status_code == 429 and r.json()["code"] == "TOO_MANY_ATTEMPTS"
    assert "15 minutes" in r.json()["message"]


def test_a_locked_username_is_refused_even_with_the_right_password(client, db):
    user_with(db, "ravi")
    for _ in range(5):
        login(client, "ravi", "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 429


def test_the_lock_is_per_username_and_names_that_do_not_exist_lock_too(client, db):
    user_with(db, "ravi")
    user_with(db, "meena")
    for _ in range(5):
        login(client, "ravi", "wrong-pass1")
        login(client, "ghost", "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 429
    assert login(client, "ghost", "wrong-pass1").status_code == 429  # a lock reveals nothing about whether the name exists
    assert login(client, "meena", "rightpass1").status_code == 200


def test_the_username_is_not_case_sensitive_for_the_lock(client, db):
    user_with(db, "ravi")
    for name in ("ravi", "RAVI", "Ravi", "rAvI", "ravi"):
        login(client, name, "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 429


def test_a_correct_password_resets_the_count(client, db):
    user_with(db, "ravi")
    for _ in range(4):
        login(client, "ravi", "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 200
    for _ in range(4):
        login(client, "ravi", "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 200


def test_four_wrong_passwords_do_not_lock(client, db):
    user_with(db, "ravi")
    for _ in range(4):
        login(client, "ravi", "wrong-pass1")
    assert login(client, "ravi", "rightpass1").status_code == 200


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_the_lock_ends_after_fifteen_minutes():
    clock = Clock()
    g = LoginGuard(clock=clock)
    for _ in range(5):
        g.failure("ravi", "1.2.3.4")
    with pytest.raises(Exception) as e:
        g.check("ravi", "1.2.3.4")
    assert e.value.status == 429
    clock.now += 14 * 60
    with pytest.raises(Exception):
        g.check("ravi", "1.2.3.4")
    clock.now += 61
    g.check("ravi", "1.2.3.4")


def test_failures_older_than_the_window_do_not_count():
    clock = Clock()
    g = LoginGuard(clock=clock)
    for _ in range(4):
        g.failure("ravi", "1.2.3.4")
    clock.now += 16 * 60
    g.failure("ravi", "1.2.3.4")
    g.check("ravi", "1.2.3.4")


def test_the_time_left_is_told_in_minutes():
    clock = Clock()
    g = LoginGuard(clock=clock)
    for _ in range(5):
        g.failure("ravi", "ip")
    clock.now += 14 * 60 + 30
    with pytest.raises(Exception) as e:
        g.check("ravi", "ip")
    assert "1 minute." in e.value.message


def test_one_address_trying_many_usernames_is_stopped():
    g = LoginGuard(ip_limit=10)
    for i in range(10):
        g.failure(f"user{i}", "9.9.9.9")
    with pytest.raises(Exception) as e:
        g.check("someone-new", "9.9.9.9")
    assert e.value.status == 429
    g.check("someone-new", "8.8.8.8")


def test_the_tracking_does_not_grow_without_end():
    g = LoginGuard()
    for i in range(6000):
        g.failure(f"name{i}", f"ip{i}")
    assert len(g._users) <= 5000 and len(g._ips) <= 5000
    # the newest names are the ones kept
    assert "name5999" in g._users


def test_the_real_guard_is_reset_between_tests():
    assert guard._users == {} and guard._ips == {}


# ---------- changing a password ----------

def change(client, current, new):
    return client.post("/api/auth/change-password", json={"current_password": current, "new_password": new})


def test_a_password_can_be_changed_and_the_new_one_logs_in(client, db):
    user_with(db, "ravi")
    assert login(client, "ravi", "rightpass1").status_code == 200
    r = change(client, "rightpass1", "brandnew-pass9")
    assert r.status_code == 200 and r.json()["username"] == "ravi"
    client.cookies.clear()
    assert login(client, "ravi", "rightpass1").status_code == 401
    assert login(client, "ravi", "brandnew-pass9").status_code == 200


def test_the_new_password_is_stored_hashed(client, db):
    user = user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    change(client, "rightpass1", "brandnew-pass9")
    db.refresh(user)
    assert "brandnew" not in user.password_hash and bcrypt.checkpw(b"brandnew-pass9", user.password_hash.encode())


def test_the_session_that_changed_it_stays_logged_in(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    change(client, "rightpass1", "brandnew-pass9")
    assert client.get("/api/auth/me").status_code == 200


def test_other_sessions_end_when_the_password_changes(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    old_session = client.cookies.get(COOKIE_NAME)
    change(client, "rightpass1", "brandnew-pass9")
    new_session = client.cookies.get(COOKIE_NAME)
    assert old_session != new_session
    client.cookies.set(COOKIE_NAME, old_session)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(COOKIE_NAME, new_session)
    assert client.get("/api/auth/me").status_code == 200


def test_a_wrong_current_password_is_refused_with_the_field(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    r = change(client, "not-right-1", "brandnew-pass9")
    assert r.status_code == 422 and r.json()["code"] == "WRONG_PASSWORD" and r.json()["field"] == "current_password"
    client.cookies.clear()
    assert login(client, "ravi", "rightpass1").status_code == 200


def test_guessing_the_current_password_from_a_session_locks_out_too(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    for _ in range(5):
        assert change(client, "not-right-1", "brandnew-pass9").status_code == 422
    assert change(client, "rightpass1", "brandnew-pass9").status_code == 429


@pytest.mark.parametrize("new,fragment", [
    ("short1", "at least 8"),
    ("onlyletters", "letters and at least one number"),
    ("12345678901", "letters and at least one number"),
    ("password123", "too common"),
    ("xxravi-pass9", "username"),
])
def test_a_weak_new_password_is_refused_and_says_why(client, db, new, fragment):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    r = change(client, "rightpass1", new)
    assert r.status_code == 422 and r.json()["code"] == "WEAK_PASSWORD" and r.json()["field"] == "new_password"
    assert fragment in r.json()["message"]


def test_the_same_password_again_is_refused(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    r = change(client, "rightpass1", "rightpass1")
    assert r.status_code == 422 and r.json()["code"] == "SAME_PASSWORD"


def test_a_password_longer_than_bcrypt_can_use_is_refused(client, db):
    user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    assert change(client, "rightpass1", "a1" * 40).status_code == 422


def test_changing_a_password_needs_a_login(client):
    assert change(client, "a", "b").status_code == 401


def test_the_policy_in_one_place():
    assert check_new_password("good-pass-9", "ravi") is None
    assert check_new_password("Abcdefg1", "ravi") is None
    assert "8" in check_new_password("a1", "ravi")
    assert check_new_password("ab1", "ab") is not None
    assert check_new_password("ravi12345", "ra") is None  # a very short username is not matched against


# ---------- the session ----------

def test_the_session_cookie_is_http_only_and_lax(client, db):
    user_with(db, "ravi")
    header = login(client, "ravi", "rightpass1").headers["set-cookie"].lower()
    assert "httponly" in header and "samesite=lax" in header and "path=/" in header


def test_the_cookie_is_marked_secure_when_the_site_runs_on_https(client, db, monkeypatch):
    user_with(db, "ravi")
    monkeypatch.setattr(settings, "cookie_secure", True)
    assert "secure" in login(client, "ravi", "rightpass1").headers["set-cookie"].lower()


def test_a_session_carries_a_fingerprint_of_the_password_not_the_password(client, db):
    user = user_with(db, "ravi")
    login(client, "ravi", "rightpass1")
    claims = auth_module.read_claims(client.cookies.get(COOKIE_NAME))
    assert claims["pwd"] == fingerprint(user.password_hash)
    assert "rightpass1" not in str(claims) and user.password_hash not in str(claims)


def test_a_session_without_a_fingerprint_still_works(client, db):
    user = user_with(db, "ravi")
    client.cookies.set(COOKIE_NAME, auth_module.create_token(user.id))
    assert client.get("/api/auth/me").status_code == 200


def test_a_session_with_the_wrong_fingerprint_is_refused(client, db):
    user = user_with(db, "ravi")
    client.cookies.set(COOKIE_NAME, auth_module.create_token(user.id, hash_password("another-pass1")))
    assert client.get("/api/auth/me").status_code == 401


def test_an_owner_changing_a_password_in_master_data_ends_that_users_sessions(client, db, login_as):
    target = user_with(db, "ravi")
    client.cookies.set(COOKIE_NAME, auth_module.create_token(target.id, target.password_hash))
    assert client.get("/api/auth/me").status_code == 200
    old_session = client.cookies.get(COOKIE_NAME)
    client.cookies.clear()
    login_as("owner")
    assert client.patch(f"/api/users/{target.id}", json={"password": "set-by-owner9"}).status_code == 200
    client.cookies.set(COOKIE_NAME, old_session)
    assert client.get("/api/auth/me").status_code == 401


# ---------- headers ----------

def test_every_response_carries_the_protective_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "same-origin"


def test_login_answers_are_never_cached(client, db):
    user_with(db, "ravi")
    assert login(client, "ravi", "rightpass1").headers["cache-control"] == "no-store"
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
    assert "no-store" not in client.get("/api/health").headers.get("cache-control", "")


def test_error_answers_keep_the_headers_too(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.headers["x-frame-options"] == "DENY"


def test_no_password_or_hash_ever_appears_in_an_answer(client, db):
    user = user_with(db, "ravi")
    body = login(client, "ravi", "rightpass1").text + client.get("/api/auth/me").text
    # the one place the word may appear is the yes/no flag that tells the web app to ask for a new password
    assert "rightpass1" not in body and user.password_hash not in body
    assert "password" not in body.lower().replace('"must_change_password":false', "")
