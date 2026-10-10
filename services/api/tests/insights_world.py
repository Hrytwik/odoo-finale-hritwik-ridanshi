"""Small mills with every figure worked out by hand (docs/plans/B7-intelligence.md, 'Hand-worked numbers').
Dates are relative to today, because the delivery-date schedule counts days from today."""
import datetime as dt
from dataclasses import dataclass, field

from app.core.clock import today_ist
from app.db.models import QcDefect, YarnMovement
from tests.factories import (
    dye, make_buyer, make_dispatch, make_fabric_type, make_inspection, make_lot, make_machine, make_order, make_roll,
    make_run, make_shift, make_supplier, make_user, make_worker, make_yarn_type, put_on_dispatch,
)

LONG_AGO = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


@dataclass
class Mill:
    today: dt.date
    cotton: object
    supplier: object
    buyer: object
    fabric: object
    order_a: object            # 480 m, due in 3 days
    order_b: object            # 480 m, due in 10 days
    machines: dict = field(default_factory=dict)
    lot: object = None


def build_mill(db) -> Mill:
    """Three 8-hour shifts, one machine per stage, efficiency at its 0.8 default (no run has ended), so per day:
    spinning 25 x 0.8 x 24 = 480 kg, weaving 12.5 x 0.8 x 24 = 240 m, dyeing 25 x 0.8 x 24 = 480 m. Two untouched orders of 480 m
    (fabric 0.5 kg a metre, no wastage: 240 kg of yarn each)."""
    today = today_ist()
    for name, start, end in (("A", 6, 14), ("B", 14, 22), ("C", 22, 6)):
        make_shift(db, name=name, start_time=dt.time(start), end_time=dt.time(end))
    machines = {stage: make_machine(db, stage=stage, rated_output_per_hour=rated, running_cost_per_hour=0, created_at=LONG_AGO)
                for stage, rated in (("spinning", 25), ("weaving", 12.5), ("dyeing", 25))}
    cotton = make_yarn_type(db, reorder_level_kg=50)
    supplier = make_supplier(db, name="Vardhman Yarns", lead_time_days=4)
    fabric = make_fabric_type(db, yarn_type=cotton, kg_per_metre=0.5, wastage_pct=0)
    buyer = make_buyer(db, name="Sharma Fabrics")
    a = make_order(db, buyer=buyer, fabric_type=fabric, qty_metres=480, deadline=today + dt.timedelta(days=3),
                   confirmed_at=dt.datetime(2026, 10, 1, tzinfo=dt.UTC))
    b = make_order(db, buyer=buyer, fabric_type=fabric, qty_metres=480, deadline=today + dt.timedelta(days=10),
                   confirmed_at=dt.datetime(2026, 10, 2, tzinfo=dt.UTC))
    lot = make_lot(db, yarn_type=cotton, supplier=supplier, qty_kg=100)
    return Mill(today, cotton, supplier, buyer, fabric, a, b, machines, lot)


@dataclass
class DefectMill:
    lot_a: object
    lot_b: object
    loom_a: object
    loom_b: object
    operator_a: object
    dyer: object


def build_defect_mill(db) -> DefectMill:
    """Twenty inspected rolls in two groups of ten that line up with a lot, a loom, an operator and a shift each; group A
    (alone) is also dyed on one dye machine. Six rolls from group A have a confirmed defect, none from group B: 6 of 10
    against 0 of 10, p = 1001 / 184756. Nine groups are big enough to test (two lots, two looms, two operators, two shifts,
    one dye machine), so the flag threshold is 0.05 / 9 = 0.00556 and all five of group A's factors are flagged."""
    order = make_order(db)
    make_shift(db, name="Day", start_time=dt.time(6), end_time=dt.time(22))
    make_shift(db, name="Night", start_time=dt.time(22), end_time=dt.time(6))
    dyer = make_machine(db, stage="dyeing")
    cotton = make_yarn_type(db)
    lots, looms, operators = [], [], []
    inspector = make_worker(db, role="inspector").id
    for _ in range(2):
        lot = make_lot(db, yarn_type=cotton, qty_kg=500)
        spin = make_run(db, order, make_machine(db, stage="spinning"), started_at=LONG_AGO, ended_at=LONG_AGO)
        db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-100, production_run_id=spin.id,
                            moved_by=make_user(db).id))
        loom, operator = make_machine(db, stage="weaving"), make_worker(db, name=f"Operator {len(lots) + 1}")
        dye_run = make_run(db, order, dyer, started_at=LONG_AGO, ended_at=LONG_AGO) if not lots else None
        # group A starts at 05:30 IST (the night shift), group B eight hours later (the day shift)
        weave = make_run(db, order, loom, operator, input_run_id=spin.id, started_at=LONG_AGO + dt.timedelta(hours=8 * len(lots)))
        lots.append(lot)
        looms.append(loom)
        operators.append(operator)
        for n in range(10):
            roll = make_roll(db, order, weave, 100)
            bad = len(lots) == 1 and n < 6
            inspection = make_inspection(db, roll, "rework" if bad else "pass", inspector_worker_id=inspector)
            if bad:
                db.add(QcDefect(inspection_id=inspection.id, defect_type="hole", count=1))
            if len(lots) == 1:
                dye(db, roll, dye_run)
    db.flush()
    return DefectMill(lots[0], lots[1], looms[0], looms[1], operators[0], dyer)
