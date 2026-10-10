import datetime as dt
from itertools import count

from sqlalchemy.orm import Session

from app.db.models import (
    Buyer, Dispatch, FabricRecipeLine, FabricType, Machine, Order, ProductionRun, Roll, RollRun, Shift,
    Supplier, SupplierBill, User, Worker, YarnLot, YarnMovement, YarnType,
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


def make_order(db: Session, buyer=None, fabric_type=None, state: str = "confirmed", **kw) -> Order:
    n = next(_n)
    fields = {
        "code": f"ORD-{n:04d}", "buyer_id": (buyer or make_buyer(db)).id,
        "fabric_type_id": (fabric_type or make_fabric_type(db)).id, "colour": "navy",
        "qty_metres": 1000, "price_per_metre": 120, "deadline": dt.date(2026, 10, 30), "state": state,
        "confirmed_at": dt.datetime(2026, 10, 1, tzinfo=dt.UTC) if state == "confirmed" else None,
    }
    return _add(db, Order(**{**fields, **kw}))


def make_run(db: Session, order: Order, machine: Machine, operator: Worker | None = None, **kw) -> ProductionRun:
    if machine.stage == "weaving" and "input_run_id" not in kw:
        spinner = make_machine(db, stage="spinning")
        spin = make_run(db, order, spinner, operator)
        spin.ended_at = spin.started_at
        db.flush()
        kw["input_run_id"] = spin.id
    fields = {"order_id": order.id, "machine_id": machine.id, "stage": machine.stage,
              "operator_worker_id": (operator or make_worker(db)).id}
    return _add(db, ProductionRun(**{**fields, **kw}))


def make_roll(db: Session, order: Order, weaving_run: ProductionRun, metres: float = 100) -> Roll:
    roll = _add(db, Roll(code=f"R-{next(_n):04d}", order_id=order.id, metres=metres))
    _add(db, RollRun(roll_id=roll.id, run_id=weaving_run.id, purpose="produce"))
    return roll


def make_lot(db: Session, yarn_type=None, supplier=None, qty_kg: float = 500, cost_per_kg: float = 250, **kw) -> YarnLot:
    n = next(_n)
    supplier = supplier or make_supplier(db)
    receiver = kw.pop("received_by", None) or make_user(db, role="store").id
    lot = _add(db, YarnLot(**{
        "lot_code": f"L-{n:04d}", "yarn_type_id": (yarn_type or make_yarn_type(db)).id,
        "supplier_id": supplier.id, "cost_per_kg": cost_per_kg, "challan_no": f"CH-{n}",
        "received_by": receiver, **kw,
    }))
    _add(db, YarnMovement(yarn_lot_id=lot.id, kind="receipt", qty_kg=qty_kg, moved_by=receiver))
    _add(db, SupplierBill(supplier_id=supplier.id, yarn_lot_id=lot.id, bill_no=lot.challan_no,
                          amount=qty_kg * cost_per_kg, bill_date=dt.date(2026, 10, 1), due_date=dt.date(2026, 10, 31)))
    db.refresh(lot)
    return lot


def make_dispatch(db: Session, buyer: Buyer, **kw) -> Dispatch:
    return _add(db, Dispatch(**{"code": f"DSP-{next(_n):04d}", "buyer_id": buyer.id, "vehicle_no": "KA01AB1234", **kw}))
