"""A buyer creates their own login, and it is linked to their buyer record at the same moment.

There is no email to verify (the emails are the mill's own records), so the proof is an invite code the owner gives the
buyer. The code is worked out from the buyer's id, their email and the server secret, so nothing new is stored and the
owner can always look it up; it changes if the email on the buyer record changes.
"""
import base64
import hashlib
import hmac
import re
from typing import Annotated

from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import hash_password
from app.core.errors import AppError, commit
from app.core.passwords import check_new_password
from app.core.schemas import BcryptSafe
from app.db.models import Buyer, User

USERNAME_MAX = 60  # the users.username column
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupIn(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    invite_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=72), BcryptSafe]


class BuyerInviteOut(BaseModel):
    buyer_id: int
    buyer_name: str
    email: str | None
    invite_code: str | None  # None until the buyer record has an email
    has_account: bool


def invite_code(buyer: Buyer) -> str | None:
    """Eight letters and numbers, like ABCD-2FGH, for this buyer and the email now on their record."""
    if not buyer.email or not buyer.email.strip():
        return None
    message = f"buyer-invite:{buyer.id}:{buyer.email.strip().lower()}".encode()
    digest = hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).digest()
    text = base64.b32encode(digest).decode()[:8]
    return f"{text[:4]}-{text[4:]}"


def _plain(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", code.upper())


def _refused() -> AppError:
    # one answer for "no such email" and "wrong code", so nobody can use this to find out which emails the mill holds
    return AppError("SIGNUP_REFUSED", "That email and invite code do not match a buyer. Check both, or ask the mill.", status=422)


def find_buyer(db: Session, email: str, code: str) -> Buyer | None:
    buyer = db.scalar(select(Buyer).where(func.lower(func.trim(Buyer.email)) == email.strip().lower()))
    expected = invite_code(buyer) if buyer else None
    if buyer is None or expected is None or not hmac.compare_digest(_plain(code), _plain(expected)):
        return None
    return buyer


def sign_up(db: Session, body: SignupIn) -> User:
    email = body.email.strip().lower()
    if not _EMAIL.match(email) or len(email) > USERNAME_MAX:
        raise _refused()
    buyer = find_buyer(db, email, body.invite_code)
    if buyer is None:
        raise _refused()
    if db.scalar(select(User).where(User.username == email)):
        raise AppError("ALREADY_REGISTERED", "This email already has an account. Log in instead.", status=409)
    # the username is the whole email, so the rule against putting it in the password is also checked on the part before the @
    problem = check_new_password(body.password, email) or check_new_password(body.password, email.split("@")[0])
    if problem:
        raise AppError("WEAK_PASSWORD", problem, field="password", status=422)
    user = User(username=email, password_hash=hash_password(body.password), role="buyer", buyer_id=buyer.id)
    db.add(user)
    commit(db)
    db.refresh(user)
    return user


def invites(db: Session) -> list[BuyerInviteOut]:
    with_account = set(db.scalars(select(User.buyer_id).where(User.role == "buyer")))
    return [BuyerInviteOut(buyer_id=b.id, buyer_name=b.name, email=(b.email or "").strip() or None, invite_code=invite_code(b),
                           has_account=b.id in with_account)
            for b in db.scalars(select(Buyer).order_by(Buyer.name))]
