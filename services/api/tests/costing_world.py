"""A small September 2026 mill with every figure worked out by hand (docs/plans/B6-costing.md, 'Hand-worked numbers').
All dates are IST and in the past, so the results do not depend on when the test runs."""
import datetime as dt
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models import (
    Attendance, BuyerPayment, Invoice, InvoiceLine, SupplierBill, SupplierPayment, WagePayment, YarnMovement,
)
from tests.factories import (
    dye, make_buyer, make_dispatch, make_inspection, make_lot, make_machine, make_order, make_roll, make_run,
    make_shift, make_user, make_worker, put_on_dispatch,
)

IST = ZoneInfo("Asia/Kolkata")


def at(day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2026, 9, day, hour, minute, tzinfo=IST)


@dataclass
class World:
    order: object
    buyer: object
    r1: object                  # 500 m, passed
    r2: object                  # 500 m, rejected
    runs: dict = field(default_factory=dict)
    machines: dict = field(default_factory=dict)
    workers: dict = field(default_factory=dict)
    invoice: object = None
    bill: object = None


def build_world(db) -> World:
    marker = make_user(db, role="supervisor")
    shift = make_shift(db, name="A")                               # 06:00-14:00, the only shift
    ravi = make_worker(db, role="operator", daily_wage=800)
    suresh = make_worker(db, role="operator", daily_wage=900)
    lakshmi = make_worker(db, role="operator", daily_wage=800)     # runs the dye machine; no attendance is marked
    kiran = make_worker(db, role="storekeeper", daily_wage=800)
    created = at(1, 0)
    spinner = make_machine(db, stage="spinning", running_cost_per_hour=55, rated_output_per_hour=20, created_at=created)
    loom = make_machine(db, stage="weaving", running_cost_per_hour=60, rated_output_per_hour=28, created_at=created)
    dyer = make_machine(db, stage="dyeing", running_cost_per_hour=90, rated_output_per_hour=45, created_at=created)
    buyer = make_buyer(db, name="Sharma Fabrics")
    order = make_order(db, buyer=buyer, qty_metres=500, price_per_metre=100)
    lot = make_lot(db, qty_kg=400, cost_per_kg=250)
    bill = db.scalar(select(SupplierBill).where(SupplierBill.yarn_lot_id == lot.id))
    bill.bill_date, bill.due_date = dt.date(2026, 9, 1), dt.date(2026, 9, 30)

    spin = make_run(db, order, spinner, ravi, started_at=at(3, 6), ended_at=at(3, 10), output_kg=95)
    weave = make_run(db, order, loom, suresh, input_run_id=spin.id, started_at=at(3, 10), ended_at=at(3, 14))
    dyeing = make_run(db, order, dyer, lakshmi, started_at=at(3, 14), ended_at=at(3, 16))
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="issue", qty_kg=-100, production_run_id=spin.id, moved_by=marker.id,
                        created_at=at(3, 8)))
    db.add(YarnMovement(yarn_lot_id=lot.id, kind="adjustment", qty_kg=-2, note="count", moved_by=marker.id,
                        created_at=at(12, 10)))
    r1, r2 = make_roll(db, order, weave, 500), make_roll(db, order, weave, 500)
    r1.created_at = r2.created_at = at(3, 13)
    dye(db, r1, dyeing)
    dye(db, r2, dyeing)
    make_inspection(db, r1, "pass", inspected_at=at(4, 9))
    make_inspection(db, r2, "reject", inspected_at=at(4, 9))
    for person in (ravi, suresh, kiran):
        db.add(Attendance(worker_id=person.id, work_date=dt.date(2026, 9, 3), shift_id=shift.id, status="present",
                          marked_by=marker.id))

    dispatch = make_dispatch(db, buyer, state="dispatched", dispatched_at=at(20, 11))
    put_on_dispatch(db, r1, dispatch)
    invoice = Invoice(invoice_no="INV-0001", dispatch_id=dispatch.id, buyer_id=buyer.id, issued_at=at(20, 11),
                      total_amount=50000)
    invoice.lines.append(InvoiceLine(order_id=order.id, metres=500, rate=100, amount=50000))
    db.add(invoice)
    db.flush()
    db.add(BuyerPayment(invoice_id=invoice.id, amount=20000, received_at=dt.date(2026, 9, 22)))
    db.add(SupplierPayment(bill_id=bill.id, amount=40000, paid_at=dt.date(2026, 9, 5)))
    db.add(WagePayment(worker_id=ravi.id, period_start=dt.date(2026, 9, 1), period_end=dt.date(2026, 9, 30),
                       amount=1000, paid_at=dt.date(2026, 9, 25)))
    db.flush()
    return World(order, buyer, r1, r2, {"spin": spin, "weave": weave, "dye": dyeing},
                 {"spin": spinner, "loom": loom, "dye": dyer}, {"ravi": ravi, "suresh": suresh, "lakshmi": lakshmi}, invoice, bill)
