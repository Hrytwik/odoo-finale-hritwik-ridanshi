"""Dispatch: load a truck with rolls that passed QC (R11), confirm it into an invoice (R12), read an invoice.
Lock order (see floor/service.py): the dispatch row, then roll rows. A truck is for one buyer; over-shipping is a warning."""
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.codes import next_code
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import q_money, to_float
from app.core.schemas import Ref
from app.core.validate import invalid, not_found
from app.db.models import Buyer, BuyerPayment, Dispatch, DispatchItem, Invoice, InvoiceLine, Order, Roll, User
from app.modules.floor.service import db_now
from app.modules.dispatch import schemas as s
from app.modules.rolls.service import get_roll_or_404, roll_outs, roll_status

STATES = ("loading", "dispatched")
VEHICLE_MAX, DRIVER_MAX = 30, 120      # the column sizes; checked here so the answer is a 422 on the field

_SUMMARY_SQL = text("""
SELECT o.id AS order_id, o.code AS order_code, o.qty_metres AS ordered_m,
  COALESCE((SELECT SUM(r2.metres) FROM rolls r2
              JOIN dispatch_items di2 ON di2.roll_id = r2.id JOIN dispatches d2 ON d2.id = di2.dispatch_id
            WHERE r2.order_id = o.id AND d2.state = 'dispatched' AND d2.id <> :did), 0) AS previously_dispatched_m,
  SUM(r.metres) AS loaded_m
FROM dispatch_items di JOIN rolls r ON r.id = di.roll_id JOIN orders o ON o.id = r.order_id
WHERE di.dispatch_id = :did GROUP BY o.id ORDER BY o.code
""")


def get_dispatch_or_404(db: Session, code: str, for_update: bool = False) -> Dispatch:
    query = select(Dispatch).where(Dispatch.code == code)
    if for_update:  # lock the row and re-read it: two clerks on one truck, or a scan against a confirm, run one after the other
        query = query.with_for_update().execution_options(populate_existing=True)
    dispatch = db.scalar(query)
    if dispatch is None:
        raise not_found("Dispatch", "dispatch_code")
    return dispatch


def _locked(code: str) -> AppError:
    return AppError("DISPATCH_LOCKED", f"Dispatch {code} is confirmed and cannot be changed", field="dispatch_code")


def _loading_dispatch(db: Session, code: str) -> Dispatch:
    dispatch = get_dispatch_or_404(db, code, for_update=True)
    if dispatch.state != "loading":
        raise _locked(code)
    return dispatch


def _announce(dispatch: Dispatch, *roll_ids: int) -> None:
    broadcaster.publish("dispatch.changed", dispatch.id)
    for roll_id in roll_ids:
        broadcaster.publish("roll.changed", roll_id)


def create_dispatch(db: Session, body: s.DispatchIn) -> Dispatch:
    buyer = db.get(Buyer, body.buyer_id)
    if buyer is None:
        raise not_found("Buyer", "buyer_id")
    if len(body.vehicle_no) > VEHICLE_MAX:
        raise invalid(f"The vehicle number is too long (at most {VEHICLE_MAX} characters)", "vehicle_no")
    if body.driver_name is not None and len(body.driver_name) > DRIVER_MAX:
        raise invalid(f"The driver's name is too long (at most {DRIVER_MAX} characters)", "driver_name")
    dispatch = Dispatch(code=next_code(db, "dispatch"), buyer_id=buyer.id, vehicle_no=body.vehicle_no,
                        driver_name=body.driver_name, state="loading")
    db.add(dispatch)
    commit(db)
    db.refresh(dispatch)
    _announce(dispatch)
    return dispatch


def scan_roll(db: Session, code: str, body: s.ScanIn) -> Dispatch:
    dispatch = _loading_dispatch(db, code)
    roll = get_roll_or_404(db, body.roll_code)
    roll = get_roll_or_404(db, body.roll_code, for_update=True)
    if roll.order.buyer_id != dispatch.buyer_id:
        raise AppError("WRONG_BUYER", f"Roll {roll.code} belongs to another buyer's order", field="roll_code")
    if roll.order.closed_short_at is not None:
        raise AppError("ORDER_CLOSED_SHORT", f"Order {roll.order.code} was closed short: its rolls are not sent", field="roll_code")
    on = db.scalar(select(DispatchItem.dispatch_id).where(DispatchItem.roll_id == roll.id))
    if on is not None:
        where = "this dispatch" if on == dispatch.id else "another dispatch"
        raise AppError("ALREADY_DISPATCHED", f"Roll {roll.code} is already on {where}", field="roll_code")
    status = roll_status(db, roll.id)
    if status != "in_store":
        raise AppError("ROLL_NOT_PASSED", f"Roll {roll.code} is {status}, not in store (it has not passed QC)",
                       field="roll_code")
    db.add(DispatchItem(dispatch_id=dispatch.id, roll_id=roll.id))
    commit(db)   # the unique index on a roll's dispatch item is the last defence (ALREADY_DISPATCHED)
    _announce(dispatch, roll.id)
    return dispatch


def unload_roll(db: Session, code: str, roll_code: str) -> Dispatch:
    dispatch = _loading_dispatch(db, code)
    roll = get_roll_or_404(db, roll_code, for_update=True)
    item = db.scalar(select(DispatchItem).where(DispatchItem.dispatch_id == dispatch.id,
                                                DispatchItem.roll_id == roll.id))
    if item is None:
        raise not_found(f"Roll {roll.code} on this dispatch", "roll_code")
    db.delete(item)
    commit(db)
    _announce(dispatch, roll.id)
    return dispatch


def _warning(order_code: str, ordered: Decimal, over: Decimal) -> str:
    return f"Order {order_code}: {format(over.normalize(), 'f')} m more than the {format(ordered.normalize(), 'f')} m ordered"


def dispatch_out(db: Session, dispatch: Dispatch) -> s.DispatchOut:
    rolls = list(db.scalars(select(Roll).join(DispatchItem, DispatchItem.roll_id == Roll.id)
                            .where(DispatchItem.dispatch_id == dispatch.id).order_by(Roll.id)))
    orders, warnings = [], []
    for row in db.execute(_SUMMARY_SQL, {"did": dispatch.id}).mappings():
        previous, loaded, ordered = row["previously_dispatched_m"], row["loaded_m"], row["ordered_m"]
        over = previous + loaded - ordered
        orders.append(s.OrderLoadSummary(
            order_code=row["order_code"], ordered_m=to_float(ordered), previously_dispatched_m=to_float(previous),
            loaded_m=to_float(loaded), remaining_m=to_float(max(Decimal(0), ordered - previous - loaded)),
            over_shipped=over > 0))
        if over > 0:
            warnings.append(_warning(row["order_code"], ordered, over))
    invoice_no = db.scalar(select(Invoice.invoice_no).where(Invoice.dispatch_id == dispatch.id))
    buyer = db.get(Buyer, dispatch.buyer_id)
    return s.DispatchOut(
        id=dispatch.id, code=dispatch.code, buyer=Ref(id=buyer.id, name=buyer.name),
        vehicle_no=dispatch.vehicle_no, driver_name=dispatch.driver_name, state=dispatch.state,
        created_at=dispatch.created_at, dispatched_at=dispatch.dispatched_at, rolls=roll_outs(db, rolls), orders=orders,
        total_metres=to_float(sum((r.metres for r in rolls), Decimal(0))), invoice_no=invoice_no, warnings=warnings)


def list_dispatches(db: Session, state: str | None = None) -> list[s.DispatchOut]:
    if state is not None and state not in STATES:
        raise AppError("VALIDATION_ERROR", "state must be loading or dispatched", field="state", status=422)
    query = select(Dispatch).order_by(Dispatch.id.desc())
    if state is not None:
        query = query.where(Dispatch.state == state)
    return [dispatch_out(db, d) for d in db.scalars(query)]


def confirm_dispatch(db: Session, code: str) -> Dispatch:
    """Close the truck and bill it, in one transaction. One invoice line per order; the invoice total is the sum of the
    rounded line amounts. After this nothing on the dispatch or its invoice changes."""
    dispatch = _loading_dispatch(db, code)
    rolls = list(db.scalars(select(Roll).join(DispatchItem, DispatchItem.roll_id == Roll.id)
                            .where(DispatchItem.dispatch_id == dispatch.id).order_by(Roll.id)
                            .with_for_update().execution_options(populate_existing=True)))
    if not rolls:
        raise AppError("EMPTY_DISPATCH", f"Dispatch {dispatch.code} has no rolls to confirm", field="dispatch_code")
    now = db_now(db)
    per_order: dict[int, Decimal] = {}
    for roll in rolls:
        per_order[roll.order_id] = per_order.get(roll.order_id, Decimal(0)) + roll.metres
    orders = {o.id: o for o in db.scalars(select(Order).where(Order.id.in_(per_order)))}
    lines = [InvoiceLine(order_id=oid, metres=metres, rate=orders[oid].price_per_metre,
                         amount=q_money(metres * orders[oid].price_per_metre))
             for oid, metres in sorted(per_order.items(), key=lambda kv: orders[kv[0]].code)]
    dispatch.state, dispatch.dispatched_at = "dispatched", now
    invoice = Invoice(invoice_no=next_code(db, "invoice"), dispatch_id=dispatch.id, buyer_id=dispatch.buyer_id,
                      issued_at=now, total_amount=sum((line.amount for line in lines), Decimal(0)))
    invoice.lines = lines
    db.add(invoice)
    commit(db)   # a line too big for its column is a clean 422 and the rollback leaves the truck `loading`
    db.refresh(dispatch)
    _announce(dispatch, *(r.id for r in rolls))
    return dispatch


def invoice_out(db: Session, user: User, invoice_no: str) -> s.InvoiceOut:
    invoice = db.scalar(select(Invoice).where(Invoice.invoice_no == invoice_no))
    # a buyer asking for another buyer's invoice gets exactly the answer for an invoice that does not exist (R15)
    if invoice is None or (user.role == "buyer" and invoice.buyer_id != user.buyer_id):
        raise not_found("Invoice", "invoice_no")
    dispatch = db.get(Dispatch, invoice.dispatch_id)
    buyer = db.get(Buyer, invoice.buyer_id)
    lines = []
    for line in sorted(invoice.lines, key=lambda ln: ln.order_id):
        order = db.get(Order, line.order_id)
        codes = list(db.scalars(select(Roll.code).join(DispatchItem, DispatchItem.roll_id == Roll.id)
                                .where(DispatchItem.dispatch_id == dispatch.id, Roll.order_id == order.id)
                                .order_by(Roll.id)))
        lines.append(s.InvoiceLineOut(order_code=order.code, fabric=order.fabric_type.name, colour=order.colour,
                                      metres=to_float(line.metres), rate=to_float(line.rate),
                                      amount=to_float(line.amount), roll_codes=codes))
    paid = db.scalar(select(func.coalesce(func.sum(BuyerPayment.amount), 0)).where(BuyerPayment.invoice_id == invoice.id))
    return s.InvoiceOut(invoice_no=invoice.invoice_no, issued_at=invoice.issued_at, buyer=Ref(id=buyer.id, name=buyer.name),
                        dispatch_code=dispatch.code, vehicle_no=dispatch.vehicle_no, lines=lines,
                        total_amount=to_float(invoice.total_amount), paid_amount=to_float(paid),
                        balance=to_float(invoice.total_amount - paid))
