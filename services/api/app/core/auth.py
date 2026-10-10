import datetime as dt
from collections.abc import Callable

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.core.passwords import BCRYPT_COST, fingerprint
from app.db.models import User
from app.db.session import get_db

COOKIE_NAME = "everest_session"
ALL_ROLES = ("owner", "accountant", "store", "supervisor", "qc", "dispatch", "buyer")
STAFF = tuple(r for r in ALL_ROLES if r != "buyer")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_COST)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, password_hash: str | None = None) -> str:
    """A signed session. With the user's password hash it also carries a fingerprint of it, so changing the password ends the session."""
    exp = dt.datetime.now(dt.UTC) + dt.timedelta(hours=settings.jwt_ttl_hours)
    claims: dict = {"sub": str(user_id), "exp": exp}
    if password_hash:
        claims["pwd"] = fingerprint(password_hash)
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def read_claims(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def read_token(token: str) -> int | None:
    claims = read_claims(token)
    try:
        return int(claims["sub"]) if claims else None
    except (KeyError, ValueError, TypeError):
        return None


def _not_authenticated() -> AppError:
    return AppError("NOT_AUTHENTICATED", "Please log in", status=401)


def session_user_id(request: Request) -> int:
    token = request.cookies.get(COOKIE_NAME)
    user_id = read_token(token) if token else None
    if user_id is None:
        raise _not_authenticated()
    return user_id


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = db.get(User, session_user_id(request))
    if user is None:
        raise _not_authenticated()
    claims = read_claims(request.cookies.get(COOKIE_NAME, "")) or {}
    # a session made before the password was last changed is no longer good
    if "pwd" in claims and claims["pwd"] != fingerprint(user.password_hash):
        raise _not_authenticated()
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "You don't have access to this", status=403)
        return user

    return dependency
