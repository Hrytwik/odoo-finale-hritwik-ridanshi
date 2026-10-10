"""Yarn store rules: receiving a lot (R1) and reading lots. Quantities are Decimal; only the JSON edge uses float."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.clock import today_ist
from app.core.codes import next_code
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import dec, q_kg, q_money, to_float
from app.core.validate import check_upload_path, exact_positive, invalid, not_found
from app.db.models import (
    FabricRecipeLine, Machine, Order, ProductionRun, Supplier, SupplierBill, User, YarnLot, YarnMovement, YarnType,
)
from app.core.schemas import Ref
from app.modules.store import schemas as s

BILL_TERMS_DAYS = 30


def get_lot_or_404(db: Session, lot_code: str, for_update: bool = False) -> YarnLot:
    query = select(YarnLot).where(YarnLot.lot_code == lot_code)
    if for_update:  # take the row lock and re-read the row, so is_blocked and the ledger are what is committed NOW
        query = query.with_for_update().execution_options(populate_existing=True)
    lot = db.scalar(query)
    if lot is None:
        raise not_found("Lot", "lot_code")
    return lot


def receive_lot(db: Session, user: User, body: s.LotReceiveIn) -> YarnLot:
    yarn_type = db.get(YarnType, body.yarn_type_id)
    if yarn_type is None:
        raise not_found("Yarn type", "yarn_type_id")
    supplier = db.get(Supplier, body.supplier_id)
    if supplier is None:
        raise not_found("Supplier", "supplier_id")
    order_id = None
    if body.intended_order_code is not None:
        order_id = db.scalar(select(Order.id).where(Order.code == body.intended_order_code))
        if order_id is None:
            raise not_found("Order", "intended_order_code")
    photo = body.challan_photo_path
    if photo is not None:
        check_upload_path(photo, "challan_photo_path")
    qty = exact_positive(body.qty_kg, "qty_kg", q_kg)
    cost = exact_positive(body.cost_per_kg, "cost_per_kg", q_money)

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


def _movements(db: Session, *conditions) -> list[s.MovementOut]:
    rows = db.execute(
        select(YarnMovement, YarnLot.lot_code, ProductionRun.id, Order.code, Machine.code, User.username)
        .join(YarnLot, YarnLot.id == YarnMovement.yarn_lot_id)
        .outerjoin(ProductionRun, ProductionRun.id == YarnMovement.production_run_id)
        .outerjoin(Order, Order.id == ProductionRun.order_id)
        .outerjoin(Machine, Machine.id == ProductionRun.machine_id)
        .join(User, User.id == YarnMovement.moved_by)
        .where(*conditions).order_by(YarnMovement.id)).all()
    return [
        s.MovementOut(id=m.id, lot_code=lot_code, kind=m.kind, qty_kg=to_float(m.qty_kg), run_id=run_id,
                      order_code=order_code, machine_code=machine_code, at=m.created_at, by=username, note=m.note)
        for m, lot_code, run_id, order_code, machine_code, username in rows
    ]


def movements_out(db: Session, lot: YarnLot) -> list[s.MovementOut]:
    return _movements(db, YarnMovement.yarn_lot_id == lot.id)


def movement_out(db: Session, movement: YarnMovement) -> s.MovementOut:
    return _movements(db, YarnMovement.id == movement.id)[0]


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


# ---- issue, return, adjust, block (R2, R2b, R14) -----------------------------------------------------------------
# Every one of these locks the lot's row first (SELECT ... FOR UPDATE), so two requests for the same lot run one after
# the other and the second one sees what the first one committed. That is what keeps stock from going negative.

def _on_hand(db: Session, lot: YarnLot) -> Decimal:
    return db.execute(text("SELECT COALESCE((SELECT on_hand_kg FROM v_lot_stock WHERE yarn_lot_id = :i), 0)"),
                      {"i": lot.id}).scalar_one()


def _announce(lot: YarnLot) -> None:
    broadcaster.publish("lot.changed", lot.id)
    broadcaster.publish("stock.changed", lot.yarn_type_id)


def _run_or_404(db: Session, run_id: int) -> ProductionRun:
    run = db.get(ProductionRun, run_id)
    if run is None:
        raise not_found("Production run", "run_id")
    return run


def _record(db: Session, user: User, lot: YarnLot, kind: str, qty: Decimal, run_id: int | None = None,
            note: str | None = None) -> YarnMovement:
    movement = YarnMovement(yarn_lot_id=lot.id, kind=kind, qty_kg=qty, production_run_id=run_id, note=note,
                            moved_by=user.id)
    db.add(movement)
    commit(db)
    db.refresh(movement)
    _announce(lot)
    return movement


def issue_yarn(db: Session, user: User, body: s.IssueIn) -> YarnMovement:
    lot = get_lot_or_404(db, body.lot_code, for_update=True)
    qty = exact_positive(body.qty_kg, "qty_kg", q_kg)
    if lot.is_blocked:
        raise AppError("LOT_BLOCKED", "This lot is blocked and cannot be issued", field="lot_code")
    run = _run_or_404(db, body.run_id)
    order = db.get(Order, run.order_id)
    if run.stage != "spinning" or run.ended_at is not None or order.state != "confirmed":
        raise AppError("RUN_NOT_OPEN", "Yarn can only be issued to a running spinning job of a confirmed order",
                       field="run_id")
    in_recipe = db.scalar(select(FabricRecipeLine.id).where(
        FabricRecipeLine.fabric_type_id == order.fabric_type_id, FabricRecipeLine.yarn_type_id == lot.yarn_type_id))
    if in_recipe is None:
        raise AppError("YARN_NOT_IN_RECIPE", "This order's fabric does not use this yarn type", field="lot_code")
    available = _on_hand(db, lot)
    if qty > available:
        raise AppError("INSUFFICIENT_STOCK", f"Only {available:f} kg of this lot is in stock", field="qty_kg")
    return _record(db, user, lot, "issue", -qty, run.id)


def return_yarn(db: Session, user: User, body: s.ReturnIn) -> YarnMovement:
    lot = get_lot_or_404(db, body.lot_code, for_update=True)
    qty = exact_positive(body.qty_kg, "qty_kg", q_kg)
    run = _run_or_404(db, body.run_id)
    net_issued = -db.scalar(select(func.coalesce(func.sum(YarnMovement.qty_kg), 0)).where(
        YarnMovement.yarn_lot_id == lot.id, YarnMovement.production_run_id == run.id,
        YarnMovement.kind.in_(("issue", "return"))))
    if qty > net_issued:
        raise AppError("RETURN_EXCEEDS_ISSUED",
                       f"Only {net_issued:f} kg of this lot is out with that run", field="qty_kg")
    return _record(db, user, lot, "return", qty, run.id)


def adjust_stock(db: Session, user: User, body: s.AdjustIn) -> YarnMovement:
    lot = get_lot_or_404(db, body.lot_code, for_update=True)
    try:
        qty = q_kg(dec(body.qty_kg))
    except ValueError:
        raise invalid("Enter a valid number", "qty_kg") from None
    if qty == 0:
        raise invalid("This rounds to zero; enter a larger number", "qty_kg")
    available = _on_hand(db, lot)
    if qty < 0 and -qty > available:
        raise AppError("INSUFFICIENT_STOCK", f"Only {available:f} kg of this lot is in stock", field="qty_kg")
    return _record(db, user, lot, "adjustment", qty, note=body.note)


def block_lot(db: Session, user: User, lot_code: str, body: s.BlockIn) -> YarnLot:
    lot = get_lot_or_404(db, lot_code, for_update=True)
    if lot.is_blocked:
        raise AppError("LOT_ALREADY_BLOCKED", "This lot is already blocked", field="lot_code")
    lot.is_blocked, lot.blocked_reason, lot.blocked_at = True, body.reason, dt.datetime.now(dt.UTC)
    commit(db)
    db.refresh(lot)
    _announce(lot)
    return lot
