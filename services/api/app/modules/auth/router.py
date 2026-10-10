from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import COOKIE_NAME, create_token, current_user, verify_password
from app.core.enums import Role
from app.core.errors import AppError
from app.core.schemas import BcryptSafe
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=72), BcryptSafe]


class Me(BaseModel):
    id: int
    username: str
    role: Role
    display_name: str
    worker_id: int | None
    buyer_id: int | None


def to_me(user: User) -> Me:
    display = user.worker.name if user.worker else user.buyer.name if user.buyer else user.username
    return Me(id=user.id, username=user.username, role=user.role, display_name=display,
              worker_id=user.worker_id, buyer_id=user.buyer_id)


@router.post("/login", response_model=Me)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> Me:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError("BAD_CREDENTIALS", "Wrong username or password", status=401)
    response.set_cookie(
        COOKIE_NAME, create_token(user.id), httponly=True, samesite="lax",
        secure=settings.cookie_secure, max_age=settings.jwt_ttl_hours * 3600, path="/",
    )
    return to_me(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=Me)
def me(user: User = Depends(current_user)) -> Me:
    return to_me(user)
