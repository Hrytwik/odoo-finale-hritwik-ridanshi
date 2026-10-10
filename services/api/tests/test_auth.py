import datetime as dt

import jwt

from app.config import settings
from app.core.auth import COOKIE_NAME, hash_password
from tests.factories import make_user


def test_login_sets_cookie_and_me_works(client, db):
    make_user(db, username="ravi", password_hash=hash_password("secret12"), role="supervisor")
    r = client.post("/api/auth/login", json={"username": "ravi", "password": "secret12"})
    assert r.status_code == 200
    assert r.json()["role"] == "supervisor"
    assert COOKIE_NAME in r.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["username"] == "ravi"


def test_wrong_password_is_401(client, db):
    make_user(db, username="meena", password_hash=hash_password("rightpass"))
    r = client.post("/api/auth/login", json={"username": "meena", "password": "wrongpass"})
    assert r.status_code == 401
    assert r.json()["code"] == "BAD_CREDENTIALS"


def test_unknown_user_is_401(client):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever1"})
    assert r.status_code == 401


def test_password_over_72_bytes_is_422(client):
    r = client.post("/api/auth/login", json={"username": "x", "password": "a" * 73})
    assert r.status_code == 422


def test_multibyte_password_over_72_bytes_is_422(client):
    # 40 characters but 80 bytes: bcrypt cannot hash it, so it must be rejected up front
    r = client.post("/api/auth/login", json={"username": "x", "password": "é" * 40})
    assert r.status_code == 422 and r.json()["field"] == "password"


def test_no_cookie_is_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "NOT_AUTHENTICATED"


def test_garbage_cookie_is_401(client):
    client.cookies.set(COOKIE_NAME, "not-a-token")
    assert client.get("/api/auth/me").status_code == 401


def test_expired_cookie_is_401(client, db):
    user = make_user(db)
    expired = jwt.encode(
        {"sub": str(user.id), "exp": dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)},
        settings.jwt_secret, algorithm="HS256",
    )
    client.cookies.set(COOKIE_NAME, expired)
    assert client.get("/api/auth/me").status_code == 401


def test_token_signed_with_other_secret_is_401(client, db):
    user = make_user(db)
    forged = jwt.encode({"sub": str(user.id)}, "a-different-secret-of-sufficient-length", algorithm="HS256")
    client.cookies.set(COOKIE_NAME, forged)
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_cookie(client, login_as):
    login_as("owner")
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_display_name_prefers_worker_then_buyer(client, login_as):
    user = login_as("buyer")
    assert client.get("/api/auth/me").json()["display_name"] == user.buyer.name


def _role_client(db):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient

    from app.core.auth import STAFF, require_roles
    from app.core.errors import install_error_handlers
    from app.db.session import get_db

    app = FastAPI()
    install_error_handlers(app)
    app.dependency_overrides[get_db] = lambda: db

    @app.get("/owner-only", dependencies=[Depends(require_roles("owner"))])
    def owner_only():
        return {"ok": True}

    @app.get("/staff", dependencies=[Depends(require_roles(*STAFF))])
    def staff():
        return {"ok": True}

    return TestClient(app)


def test_staff_roles_exclude_buyer():
    from app.core.auth import ALL_ROLES, STAFF

    assert "buyer" not in STAFF and set(STAFF) | {"buyer"} == set(ALL_ROLES)


def test_wrong_role_is_403(db):
    from app.core.auth import COOKIE_NAME, create_token

    c = _role_client(db)
    c.cookies.set(COOKIE_NAME, create_token(make_user(db, role="store").id))
    r = c.get("/owner-only")
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_buyer_is_refused_on_staff_endpoints(db):
    from app.core.auth import COOKIE_NAME, create_token

    c = _role_client(db)
    c.cookies.set(COOKIE_NAME, create_token(make_user(db, role="buyer").id))
    assert c.get("/staff").status_code == 403


def test_right_role_is_allowed_and_no_cookie_is_401(db):
    from app.core.auth import COOKIE_NAME, create_token

    c = _role_client(db)
    assert c.get("/owner-only").status_code == 401
    c.cookies.set(COOKIE_NAME, create_token(make_user(db, role="owner").id))
    assert c.get("/owner-only").status_code == 200


def test_valid_token_for_deleted_user_is_401(client):
    from app.core.auth import COOKIE_NAME, create_token

    client.cookies.set(COOKIE_NAME, create_token(999_999))
    assert client.get("/api/auth/me").status_code == 401
