import datetime as dt
from collections.abc import Callable

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import AppError
from app.db.models import User
from app.db.session import get_db

COOKIE_NAME = "everest_session"
ALL_ROLES = ("owner", "accountant", "store", "supervisor", "qc", "dispatch", "buyer")
STAFF = tuple(r for r in ALL_ROLES if r != "buyer")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int) -> str:
    exp = dt.datetime.now(dt.UTC) + dt.timedelta(hours=settings.jwt_ttl_hours)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.jwt_secret, algorithm="HS256")


def read_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
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
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise AppError("FORBIDDEN", "You don't have access to this", status=403)
        return user

    return dependency
