import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import COOKIE_NAME, create_token, hash_password, require_roles, session_user, verify_password
from app.core.enums import Role
from app.core.errors import AppError, commit
from app.core.login_guard import client_ip, guard
from app.core.passwords import DUMMY_HASH, check_new_password, needs_rehash
from app.core.schemas import BcryptSafe
from app.db.models import User
from app.db.session import get_db
from app.modules.auth import signup as signup_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("everest.auth")


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=72), BcryptSafe]


class ChangePasswordIn(BaseModel):
    current_password: Annotated[str, StringConstraints(min_length=1, max_length=72), BcryptSafe]
    new_password: Annotated[str, StringConstraints(min_length=1, max_length=72), BcryptSafe]


class Me(BaseModel):
    id: int
    username: str
    role: Role
    display_name: str
    worker_id: int | None
    buyer_id: int | None
    must_change_password: bool


def to_me(user: User) -> Me:
    display = user.worker.name if user.worker else user.buyer.name if user.buyer else user.username
    return Me(id=user.id, username=user.username, role=user.role, display_name=display,
              worker_id=user.worker_id, buyer_id=user.buyer_id,
              must_change_password=user.must_change_password)


def _start_session(response: Response, user: User) -> None:
    response.set_cookie(
        COOKIE_NAME, create_token(user.id, user.password_hash), httponly=True, samesite="lax",
        secure=settings.cookie_secure, max_age=settings.jwt_ttl_hours * 3600, path="/",
    )


@router.post("/login", response_model=Me)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> Me:
    ip = client_ip(request)
    guard.check(body.username, ip)  # a locked username or address is refused before any password is looked at
    user = db.scalar(select(User).where(User.username == body.username))
    # always do one bcrypt check, even for a username that does not exist, so the time taken gives nothing away
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok:
        guard.failure(body.username, ip)
        log.warning("failed login for %r from %s", body.username, ip)
        raise AppError("BAD_CREDENTIALS", "Wrong username or password", status=401)
    guard.success(body.username)
    if needs_rehash(user.password_hash):
        # the password is right, so this is the moment to store it with today's work factor
        user.password_hash = hash_password(body.password)
        commit(db)
    _start_session(response, user)
    return to_me(user)


@router.post("/signup", response_model=Me, status_code=201)
def signup(body: signup_service.SignupIn, request: Request, response: Response, db: Session = Depends(get_db)) -> Me:
    """A buyer makes their own login with the email the mill holds for them and the invite code the owner gave them."""
    key = f"signup:{client_ip(request)}"
    guard.check(key, client_ip(request))  # five wrong tries from one address lock sign-up there for 15 minutes
    try:
        user = signup_service.sign_up(db, body)
    except AppError as exc:
        if exc.code == "SIGNUP_REFUSED":
            guard.failure(key, client_ip(request))
            log.warning("refused buyer sign-up for %r from %s", body.email, client_ip(request))
        raise
    guard.success(key)
    _start_session(response, user)
    return to_me(user)


@router.get("/buyer-invites", response_model=list[signup_service.BuyerInviteOut], dependencies=[Depends(require_roles("owner"))])
def buyer_invites(db: Session = Depends(get_db)) -> list[signup_service.BuyerInviteOut]:
    """For the owner: each buyer's email, whether they have a login yet, and the invite code to give them."""
    return signup_service.invites(db)


@router.post("/change-password", response_model=Me)
def change_password(body: ChangePasswordIn, request: Request, response: Response, db: Session = Depends(get_db),
                    user: User = Depends(session_user)) -> Me:
    """Changes the logged-in user's own password. Every other session of theirs stops working; this one carries on."""
    ip = client_ip(request)
    guard.check(user.username, ip)  # someone on a stolen session cannot guess the old password freely either
    if not verify_password(body.current_password, user.password_hash):
        guard.failure(user.username, ip)
        log.warning("wrong current password while changing password for %r from %s", user.username, ip)
        # 422, not 401: a 401 would be read by the web app as "your session ended"
        raise AppError("WRONG_PASSWORD", "The current password is not right", field="current_password", status=422)
    problem = check_new_password(body.new_password, user.username)
    if problem:
        raise AppError("WEAK_PASSWORD", problem, field="new_password", status=422)
    if verify_password(body.new_password, user.password_hash):
        raise AppError("SAME_PASSWORD", "Choose a password different from the current one", field="new_password", status=422)
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    commit(db)
    guard.success(user.username)
    _start_session(response, user)
    return to_me(user)


@router.post("/logout", status_code=204)
def logout(response: Response) -> Response:
    response.delete_cookie(COOKIE_NAME, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=Me)
def me(user: User = Depends(session_user)) -> Me:
    return to_me(user)
