import datetime as dt
from itertools import count

from sqlalchemy.orm import Session

from app.db.models import (
    Buyer, FabricRecipeLine, FabricType, Machine, Shift, Supplier, User, Worker, YarnType,
)

_n = count(1)


def _add(db: Session, obj):
    db.add(obj)
    db.flush()
    return obj


def make_supplier(db: Session, **kw) -> Supplier:
    return _add(db, Supplier(**{"name": f"Supplier {next(_n)}", "lead_time_days": 5, **kw}))


def make_buyer(db: Session, **kw) -> Buyer:
    return _add(db, Buyer(**{"name": f"Buyer {next(_n)}", **kw}))


def make_yarn_type(db: Session, **kw) -> YarnType:
    n = next(_n)
    return _add(db, YarnType(**{"code": f"YT-{n}", "name": "30s cotton", "colour": "raw white",
                               "reorder_level_kg": 100, **kw}))


def make_fabric_type(db: Session, yarn_type: YarnType | None = None, kg_per_metre: float = 0.12, **kw) -> FabricType:
    yt = yarn_type or make_yarn_type(db)
    ft = FabricType(**{"name": f"Poplin {next(_n)}", "width_in": 58, "wastage_pct": 5, **kw})
    ft.recipe_lines.append(FabricRecipeLine(yarn_type_id=yt.id, kg_per_metre=kg_per_metre))
    return _add(db, ft)


def make_machine(db: Session, stage: str = "weaving", **kw) -> Machine:
    n = next(_n)
    return _add(db, Machine(**{"code": f"M-{n}", "name": f"Machine {n}", "stage": stage,
                              "rated_output_per_hour": 20, "running_cost_per_hour": 50, **kw}))


def make_shift(db: Session, **kw) -> Shift:
    return _add(db, Shift(**{"name": f"S{next(_n)}", "start_time": dt.time(6), "end_time": dt.time(14), **kw}))


def make_worker(db: Session, **kw) -> Worker:
    n = next(_n)
    return _add(db, Worker(**{"code": f"W-{n}", "name": f"Worker {n}", "role": "operator",
                             "daily_wage": 800, **kw}))


def make_user(db: Session, role: str = "owner", **kw) -> User:
    if role == "buyer" and "buyer_id" not in kw:
        kw["buyer_id"] = make_buyer(db).id
    if role == "qc" and "worker_id" not in kw:
        kw["worker_id"] = make_worker(db, role="inspector").id
    return _add(db, User(**{"username": f"user{next(_n)}", "password_hash": "x", "role": role, **kw}))
