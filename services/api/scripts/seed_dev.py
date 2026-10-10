from sqlalchemy import select

from app.core.auth import hash_password
from app.db.models import Buyer, User, Worker
from app.db.session import SessionLocal

PASSWORD = "everest123"
WORKERS = [
    ("W-001", "Ravi Kumar", "operator"), ("W-002", "Meena Devi", "inspector"),
    ("W-003", "Arjun Rao", "supervisor"), ("W-004", "Kiran Shetty", "storekeeper"),
    ("W-005", "Imran Khan", "dispatch"),
]
USERS = [
    ("owner", "owner", None), ("accountant", "accountant", None), ("store", "store", "W-004"),
    ("supervisor", "supervisor", "W-003"), ("qc", "qc", "W-002"), ("dispatch", "dispatch", "W-005"),
    ("buyer", "buyer", None),
]


def main() -> None:
    with SessionLocal() as db:
        workers = {}
        for code, name, role in WORKERS:
            w = db.scalar(select(Worker).where(Worker.code == code))
            if w is None:
                w = Worker(code=code, name=name, role=role, daily_wage=800)
                db.add(w)
                db.flush()
            workers[code] = w
        buyer = db.scalar(select(Buyer).where(Buyer.name == "Sharma Fabrics"))
        if buyer is None:
            buyer = Buyer(name="Sharma Fabrics", contact_name="Anil Sharma", phone="9800000001")
            db.add(buyer)
            db.flush()
        for username, role, worker_code in USERS:
            if db.scalar(select(User).where(User.username == username)):
                continue
            db.add(User(
                username=username, password_hash=hash_password(PASSWORD), role=role,
                worker_id=workers[worker_code].id if worker_code else None,
                buyer_id=buyer.id if role == "buyer" else None,
            ))
        db.commit()
    print(f"dev users ready — password for all: {PASSWORD}")


if __name__ == "__main__":
    main()
