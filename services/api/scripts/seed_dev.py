"""Starter data for an empty database. Everything is 'create only if missing' (by its unique key), so running it again
changes nothing and never overwrites a row someone has edited. `npm run db:seed` runs seed_all()."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.db.models import (
    Buyer, FabricRecipeLine, FabricType, Machine, Shift, Supplier, User, Worker, YarnType,
)
from app.db.session import SessionLocal

PASSWORD = "everest123"
WORKERS = [
    ("W-001", "Ravi Kumar", "operator", 800), ("W-002", "Meena Devi", "inspector", 800),
    ("W-003", "Arjun Rao", "supervisor", 800), ("W-004", "Kiran Shetty", "storekeeper", 800),
    ("W-005", "Imran Khan", "dispatch", 800),
    ("W-006", "Suresh Patil", "operator", 800), ("W-007", "Lakshmi Nair", "operator", 800),
    ("W-008", "Deepak Joshi", "operator", 800), ("W-009", "Farah Sheikh", "operator", 800),
    ("W-010", "Manoj Gowda", "operator", 800), ("W-011", "Anita Rao", "operator", 800),
    ("W-012", "Sana Mirza", "inspector", 900),
]
USERS = [
    ("owner", "owner", None), ("accountant", "accountant", None), ("store", "store", "W-004"),
    ("supervisor", "supervisor", "W-003"), ("qc", "qc", "W-002"), ("dispatch", "dispatch", "W-005"),
    ("buyer", "buyer", None),
]
SHIFTS = [("A", dt.time(6), dt.time(14)), ("B", dt.time(14), dt.time(22)), ("C", dt.time(22), dt.time(6))]
# code, name, stage, rated output per hour (kg for spinning, metres otherwise), running cost per hour
MACHINES = (
    [("SPIN-01", "Ring frame 1", "spinning", 20, 55), ("SPIN-02", "Ring frame 2", "spinning", 22, 55)]
    + [(f"LOOM-{n:02d}", f"Loom {n}", "weaving", 28, 60) for n in range(1, 7)]
    + [("DYE-01", "Jet dyer 1", "dyeing", 45, 90), ("DYE-02", "Jet dyer 2", "dyeing", 45, 90)]
)
YARN_TYPES = [("30S-COT-RAW", "30s cotton", "raw white", 300), ("40S-PC-RAW", "40s poly-cotton", "raw white", 250)]
SUPPLIERS = [("Vardhman Yarns", 7), ("Coastal Spinners", 5)]
BUYERS = [("Sharma Fabrics", "Anil Sharma", "9800000001"), ("Kavya Garments", "Kavya Menon", "9800000002")]
# name, width in inches, wastage %, [(yarn type code, kg per metre)]
FABRICS = [
    ("Poplin 58in", 58, 5, [("30S-COT-RAW", Decimal("0.12"))]),
    ("Twill 58in", 58, 4, [("40S-PC-RAW", Decimal("0.16"))]),
]


def _missing(db: Session, model, column, value):
    """The existing row with this unique key, or None."""
    return db.scalar(select(model).where(column == value))


def seed_users(db: Session) -> None:
    workers = {}
    for code, name, role, wage in WORKERS:
        w = _missing(db, Worker, Worker.code, code)
        if w is None:
            w = Worker(code=code, name=name, role=role, daily_wage=wage)
            db.add(w)
            db.flush()
        workers[code] = w
    sharma = _missing(db, Buyer, Buyer.name, BUYERS[0][0])
    if sharma is None:
        sharma = Buyer(name=BUYERS[0][0], contact_name=BUYERS[0][1], phone=BUYERS[0][2])
        db.add(sharma)
        db.flush()
    for username, role, worker_code in USERS:
        if _missing(db, User, User.username, username) is not None:
            continue
        db.add(User(
            username=username, password_hash=hash_password(PASSWORD), role=role,
            worker_id=workers[worker_code].id if worker_code else None,
            buyer_id=sharma.id if role == "buyer" else None,
        ))
    db.flush()


def seed_master(db: Session) -> None:
    for name, start, end in SHIFTS:
        if _missing(db, Shift, Shift.name, name) is None:
            db.add(Shift(name=name, start_time=start, end_time=end))
    for code, name, stage, rated, cost in MACHINES:
        if _missing(db, Machine, Machine.code, code) is None:
            db.add(Machine(code=code, name=name, stage=stage, rated_output_per_hour=rated, running_cost_per_hour=cost))
    for code, name, colour, reorder in YARN_TYPES:
        if _missing(db, YarnType, YarnType.code, code) is None:
            db.add(YarnType(code=code, name=name, colour=colour, reorder_level_kg=reorder))
    for name, lead_days in SUPPLIERS:
        if _missing(db, Supplier, Supplier.name, name) is None:
            db.add(Supplier(name=name, lead_time_days=lead_days))
    for name, contact, phone in BUYERS:
        if _missing(db, Buyer, Buyer.name, name) is None:
            db.add(Buyer(name=name, contact_name=contact, phone=phone))
    db.flush()
    yarn = {y.code: y for y in db.scalars(select(YarnType))}
    for name, width, wastage, recipe in FABRICS:
        if _missing(db, FabricType, FabricType.name, name) is None:
            fabric = FabricType(name=name, width_in=width, wastage_pct=wastage)
            for code, kg_per_metre in recipe:
                fabric.recipe_lines.append(FabricRecipeLine(yarn_type_id=yarn[code].id, kg_per_metre=kg_per_metre))
            db.add(fabric)
    db.flush()


def seed_all(db: Session) -> None:
    seed_users(db)
    seed_master(db)


def main() -> None:
    with SessionLocal() as db:
        seed_all(db)
        db.commit()
    print(f"starter data ready (shifts, machines, master data, people); dev logins use the password {PASSWORD}")


if __name__ == "__main__":
    main()
