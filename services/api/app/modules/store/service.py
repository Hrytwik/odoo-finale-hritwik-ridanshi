"""Yarn store rules: receiving a lot (R1) and reading lots. Quantities are Decimal; only the JSON edge uses float."""
import datetime as dt
import re
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.clock import today_ist
from app.core.codes import next_code
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import dec, q_kg, q_money, to_float
from app.db.models import (
    Machine, Order, ProductionRun, Supplier, SupplierBill, User, YarnLot, YarnMovement, YarnType,
)
from app.core.schemas import Ref
from app.modules.store import schemas as s

PHOTO_RE = re.compile(r"uploads/[0-9a-f]{32}\.(jpg|png|webp)")
BILL_TERMS_DAYS = 30


def _not_found(what: str, field: str | None = None) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", field=field, status=404)


def _invalid(message: str, field: str) -> AppError:
    return AppError("VALIDATION_ERROR", message, field=field, status=422)


def _exact(value, field: str, rounder) -> Decimal:
    try:
        d = rounder(dec(value))
    except ValueError:
        raise _invalid("Enter a valid number", field) from None
    if d <= 0:
        raise _invalid("This rounds to zero; enter a larger number", field)
    return d


def get_lot_or_404(db: Session, lot_code: str, for_update: bool = False) -> YarnLot:
    query = select(YarnLot).where(YarnLot.lot_code == lot_code)
    if for_update:
        query = query.with_for_update()
    lot = db.scalar(query)
    if lot is None:
        raise _not_found("Lot", "lot_code")
    return lot


def receive_lot(db: Session, user: User, body: s.LotReceiveIn) -> YarnLot:
    yarn_type = db.get(YarnType, body.yarn_type_id)
    if yarn_type is None:
        raise _not_found("Yarn type", "yarn_type_id")
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None:
        raise _not_found("Supplier", "supplier_id")
    order_id = None
    if body.intended_order_code is not None:
        order_id = db.scalar(select(Order.id).where(Order.code == body.intended_order_code))
        if order_id is None:
            raise _not_found("Order", "intended_order_code")
    photo = body.challan_photo_path
    if photo is not None and PHOTO_RE.fullmatch(photo) is None:
        raise _invalid("Use a photo uploaded through the app", "challan_photo_path")
    qty = _exact(body.qty_kg, "qty_kg", q_kg)
    cost = _exact(body.cost_per_kg, "cost_per_kg", q_money)

    today = today_ist()
    lot = YarnLot(
        lot_code=next_code(db, "lot"), yarn_type_id=yarn_type.id, supplier_id=supplier.id, cost_per_kg=cost,
        challan_no=body.challan_no, challan_photo_path=photo, intended_order_id=order_id, received_by=user.id,
    )
    lot.movements.append(YarnMovement(kind="receipt", qty_kg=qty, moved_by=user.id))
    lot.bill = SupplierBill(
        supplier_id=supplier.id, bill_no=body.challan_no, amount=q_money(qty * cost),
        bill_date=today, due_date=today + dt.timedelta(days=BILL_TERMS_DAYS),
    )
    db.add(lot)
    commit(db)  # a repeated (supplier, challan, yarn type) fails here as DUPLICATE_CHALLAN and rolls everything back
    db.refresh(lot)
    broadcaster.publish("lot.changed", lot.id)
    broadcaster.publish("stock.changed", lot.yarn_type_id)
    return lot


def _totals(db: Session, lot_ids: list[int]) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """(received kg, on hand kg) per lot, from the ledger."""
    if not lot_ids:
        return {}, {}
    received = dict(db.execute(
        select(YarnMovement.yarn_lot_id, func.sum(YarnMovement.qty_kg))
        .where(YarnMovement.yarn_lot_id.in_(lot_ids), YarnMovement.kind == "receipt")
        .group_by(YarnMovement.yarn_lot_id)).all())
    on_hand = dict(db.execute(
        text("SELECT yarn_lot_id, on_hand_kg FROM v_lot_stock WHERE yarn_lot_id = ANY(:ids)"),
        {"ids": lot_ids}).all())
    return received, on_hand


def _lot_out(lot: YarnLot, received: Decimal, on_hand: Decimal, intended_code: str | None) -> s.LotOut:
    photo = lot.challan_photo_path
    return s.LotOut(
        id=lot.id, lot_code=lot.lot_code, yarn_type=s.YarnTypeRef.model_validate(lot.yarn_type),
        supplier=Ref.model_validate(lot.supplier), qty_received_kg=to_float(received),
        on_hand_kg=to_float(on_hand), cost_per_kg=to_float(lot.cost_per_kg), challan_no=lot.challan_no,
        challan_photo_url=f"/api/{photo}" if photo else None, intended_order_code=intended_code,
        received_at=lot.received_at, is_blocked=lot.is_blocked, blocked_reason=lot.blocked_reason,
    )


def _outs(db: Session, lots: list[YarnLot]) -> list[s.LotOut]:
    received, on_hand = _totals(db, [lot.id for lot in lots])
    order_ids = {lot.intended_order_id for lot in lots if lot.intended_order_id}
    codes = dict(db.execute(select(Order.id, Order.code).where(Order.id.in_(order_ids))).all()) if order_ids else {}
    zero = Decimal("0.000")
    return [_lot_out(lot, received.get(lot.id, zero), on_hand.get(lot.id, zero), codes.get(lot.intended_order_id))
            for lot in lots]


def lot_out(db: Session, lot: YarnLot) -> s.LotOut:
    return _outs(db, [lot])[0]


def list_lots(db: Session, yarn_type_id: int | None = None, blocked: bool | None = None) -> list[s.LotOut]:
    query = select(YarnLot).options(selectinload(YarnLot.yarn_type), selectinload(YarnLot.supplier))
    if yarn_type_id is not None:
        query = query.where(YarnLot.yarn_type_id == yarn_type_id)
    if blocked is not None:
        query = query.where(YarnLot.is_blocked == blocked)
    return _outs(db, list(db.scalars(query.order_by(YarnLot.id.desc()))))


def movements_out(db: Session, lot: YarnLot) -> list[s.MovementOut]:
    rows = db.execute(
        select(YarnMovement, ProductionRun.id, Order.code, Machine.code, User.username)
        .outerjoin(ProductionRun, ProductionRun.id == YarnMovement.production_run_id)
        .outerjoin(Order, Order.id == ProductionRun.order_id)
        .outerjoin(Machine, Machine.id == ProductionRun.machine_id)
        .join(User, User.id == YarnMovement.moved_by)
        .where(YarnMovement.yarn_lot_id == lot.id).order_by(YarnMovement.id)).all()
    return [
        s.MovementOut(id=m.id, lot_code=lot.lot_code, kind=m.kind, qty_kg=to_float(m.qty_kg), run_id=run_id,
                      order_code=order_code, machine_code=machine_code, at=m.created_at, by=username, note=m.note)
        for m, run_id, order_code, machine_code, username in rows
    ]


def lot_detail(db: Session, lot: YarnLot) -> s.LotDetail:
    return s.LotDetail(**lot_out(db, lot).model_dump(), movements=movements_out(db, lot))


def stock_rows(db: Session) -> list[s.StockRow]:
    """One row per yarn type from v_yarn_type_stock (on hand of unblocked lots, minus what confirmed orders still need)."""
    numbers = {row["yarn_type_id"]: row for row in db.execute(text("SELECT * FROM v_yarn_type_stock")).mappings()}
    return [
        s.StockRow(
            yarn_type=s.YarnTypeRef.model_validate(yt), on_hand_kg=to_float(n["on_hand_kg"]),
            outstanding_kg=to_float(n["outstanding_kg"]), free_kg=to_float(n["free_kg"]),
            reorder_level_kg=to_float(n["reorder_level_kg"]), below_reorder=n["below_reorder"],
        )
        for yt in db.scalars(select(YarnType).order_by(YarnType.code))
        for n in [numbers[yt.id]]
    ]
