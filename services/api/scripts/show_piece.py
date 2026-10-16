"""Set up the show-piece demo: a read-only `<name>-demo` login for every normal login (see app/core/demo_readonly.py).

Safe to run on every start: it only adds the demo logins that are missing. Set RESET_LOGINS=owner,accountant to also give
those logins a fresh random password, which is printed once to the log; leave RESET_LOGINS unset otherwise."""
import os
import secrets
import string

from sqlalchemy import select

from app.core.auth import hash_password
from app.core.demo_readonly import DEMO_SUFFIX
from app.db.models import User
from app.db.session import SessionLocal

PUBLIC_PASSWORD = "everest123"
ROLES = ("owner", "accountant", "store", "supervisor", "qc", "dispatch", "buyer")


def random_password() -> str:
    while True:
        p = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(14))
        if any(c.islower() for c in p) and any(c.isupper() for c in p) and any(c.isdigit() for c in p):
            return p


def main() -> None:
    resets = [n.strip() for n in os.environ.get("RESET_LOGINS", "").split(",") if n.strip()]
    with SessionLocal() as db:
        for name in resets:
            user = db.scalar(select(User).where(User.username == name))
            if user is None:
                print(f"reset: no login called {name}")
                continue
            fresh = random_password()
            user.password_hash = hash_password(fresh)
            user.must_change_password = False
            print(f"RESET {name} {fresh}")
        for name in ROLES:
            base = db.scalar(select(User).where(User.username == name))
            demo = f"{name}{DEMO_SUFFIX}"
            if base is None or db.scalar(select(User).where(User.username == demo)) is not None:
                continue
            db.add(User(username=demo, password_hash=hash_password(PUBLIC_PASSWORD), role=base.role,
                        worker_id=base.worker_id, buyer_id=base.buyer_id, must_change_password=False))
            print(f"added read-only login {demo}")
        db.commit()


if __name__ == "__main__":
    main()
