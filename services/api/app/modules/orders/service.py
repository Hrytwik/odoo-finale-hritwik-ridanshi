"""Order lifecycle (R3) and the numbers derived for an order: yarn check, progress and the buyer-facing stage (spec §5).
Nothing derived is stored: progress and stage are recomputed from runs, rolls, inspections and dispatches on every read."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.clock import today_ist
from app.core.codes import next_code
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import dec, q_kg, q_money, to_float
from app.core.schemas import Ref
from app.core.validate import exact_positive, not_found
from app.db.models import Buyer, FabricType, Order, ProductionRun, YarnType
from app.modules.orders import schemas as s
from app.modules.store.schemas import YarnTypeRef

STATES = ("draft", "confirmed", "cancelled")
ZERO = Decimal("0")


def get_order_or_404(db: Session, code: str, for_update: bool = False) -> Order:
    query = select(Order).where(Order.code == code)
    if for_update:  # lock the row and re-read it, so two requests on one order run one after the other
        query = query.with_for_update().execution_options(populate_existing=True)
    order = db.scalar(query)
    if order is None:
        raise not_found("Order", "order_code")
    return order


def _announce(order: Order, stock: bool = False) -> None:
    broadcaster.publish("order.changed", order.id)
    if stock:
        broadcaster.publish("stock.changed")


def _check_deadline(deadline: dt.date) -> None:
    if deadline < today_ist():
        raise AppError("DEADLINE_IN_PAST", "The deadline cannot be before today", field="deadline", status=422)


def create_order(db: Session, body: s.OrderIn) -> Order:
    if db.get(Buyer, body.buyer_id) is None:
        raise not_found("Buyer", "buyer_id")
    if db.get(FabricType, body.fabric_type_id) is None:
        raise not_found("Fabric type", "fabric_type_id")
    qty = exact_positive(body.qty_metres, "qty_metres", q_kg)
    price = exact_positive(body.price_per_metre, "price_per_metre", q_money)
    _check_deadline(body.deadline)
    order = Order(code=next_code(db, "order"), buyer_id=body.buyer_id, fabric_type_id=body.fabric_type_id,
                  colour=body.colour, qty_metres=qty, price_per_metre=price, deadline=body.deadline, state="draft")
    db.add(order)
    commit(db)
    db.refresh(order)
    _announce(order)
    return order


def confirm_order(db: Session, code: str) -> Order:
    order = get_order_or_404(db, code, for_update=True)
    if order.state != "draft":
        raise AppError("ORDER_NOT_DRAFT", "Only a draft order can be confirmed", field="order_code")
    order.state, order.confirmed_at = "confirmed", dt.datetime.now(dt.UTC)
    commit(db)
    db.refresh(order)
    _announce(order, stock=True)         # a confirmed order reserves yarn
    return order


def cancel_order(db: Session, code: str) -> Order:
    order = get_order_or_404(db, code, for_update=True)
    if order.state == "cancelled":
        raise AppError("ORDER_ALREADY_CANCELLED", "This order is already cancelled", field="order_code")
    if db.scalar(select(ProductionRun.id).where(ProductionRun.order_id == order.id).limit(1)) is not None:
        raise AppError("ORDER_HAS_RUNS", "This order has production runs and can no longer be cancelled",
                       field="order_code")
    order.state = "cancelled"
    commit(db)
    db.refresh(order)
    _announce(order, stock=True)         # its reservation is released
    return order


def change_deadline(db: Session, code: str, body: s.DeadlineIn) -> Order:
    order = get_order_or_404(db, code, for_update=True)
    if order.state == "cancelled":
        raise AppError("ORDER_CANCELLED", "A cancelled order's deadline cannot be changed", field="order_code")
    _check_deadline(body.deadline)
    order.deadline = body.deadline
    commit(db)
    db.refresh(order)
    _announce(order)
    return order


# ---- derived numbers ------------------------------------------------------------------------------------------

_PROGRESS_SQL = text("""
WITH latest AS (
  SELECT DISTINCT ON (i.roll_id) i.roll_id, i.verdict
  FROM qc_inspections i JOIN rolls r ON r.id = i.roll_id
  WHERE r.order_id = :oid
  ORDER BY i.roll_id, i.inspected_at DESC, i.id DESC
)
SELECT
  (SELECT COALESCE(SUM(need_kg), 0) FROM v_order_yarn_need WHERE order_id = :oid) AS need_kg,
  (SELECT COALESCE(SUM(output_kg), 0) FROM production_runs
     WHERE order_id = :oid AND stage = 'spinning' AND ended_at IS NOT NULL) AS spun_kg,
  (SELECT COALESCE(SUM(metres), 0) FROM rolls WHERE order_id = :oid) AS woven_m,
  (SELECT COALESCE(SUM(r.metres), 0) FROM rolls r
     WHERE r.order_id = :oid AND EXISTS (
       SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
       WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NOT NULL)) AS dyed_m,
  (SELECT COALESCE(SUM(r.metres), 0) FROM rolls r JOIN latest l ON l.roll_id = r.id WHERE l.verdict = 'pass') AS passed_m,
  (SELECT COALESCE(SUM(r.metres), 0) FROM rolls r JOIN latest l ON l.roll_id = r.id WHERE l.verdict = 'reject') AS rejected_m,
  (SELECT COALESCE(SUM(r.metres), 0) FROM rolls r
     JOIN dispatch_items di ON di.roll_id = r.id JOIN dispatches d ON d.id = di.dispatch_id
     WHERE r.order_id = :oid AND d.state = 'dispatched') AS dispatched_m
""")

_STAGE_SQL = text("""
SELECT
  EXISTS (SELECT 1 FROM production_runs WHERE order_id = :oid AND stage = 'dyeing') AS has_dyeing,
  EXISTS (SELECT 1 FROM production_runs WHERE order_id = :oid AND stage = 'weaving') AS has_weaving,
  EXISTS (SELECT 1 FROM production_runs WHERE order_id = :oid AND stage = 'spinning') AS has_spinning,
  EXISTS (
    SELECT 1 FROM rolls r
    WHERE r.order_id = :oid
      AND NOT EXISTS (SELECT 1 FROM dispatch_items di JOIN dispatches d ON d.id = di.dispatch_id
                      WHERE di.roll_id = r.id AND d.state = 'dispatched')
      AND (
        (EXISTS (SELECT 1 FROM roll_runs rr JOIN production_runs pr ON pr.id = rr.run_id
                 WHERE rr.roll_id = r.id AND rr.purpose = 'dye' AND pr.ended_at IS NOT NULL)
         AND NOT EXISTS (SELECT 1 FROM qc_inspections q WHERE q.roll_id = r.id))
        OR (SELECT q.verdict FROM qc_inspections q WHERE q.roll_id = r.id
            ORDER BY q.inspected_at DESC, q.id DESC LIMIT 1) = 'rework'
      )
  ) AS needs_quality_check
""")

_YARN_CHECK_SQL = text("""
SELECT n.yarn_type_id, n.need_kg, n.issued_kg, n.outstanding_kg,
       COALESCE(s.on_hand_kg, 0) AS on_hand_kg,
       COALESCE((SELECT SUM(o.outstanding_kg) FROM v_order_yarn_need o
                 WHERE o.yarn_type_id = n.yarn_type_id AND o.state = 'confirmed' AND o.order_id <> n.order_id), 0)
         AS others_outstanding_kg
FROM v_order_yarn_need n
JOIN yarn_types yt ON yt.id = n.yarn_type_id
LEFT JOIN v_yarn_type_stock s ON s.yarn_type_id = n.yarn_type_id
WHERE n.order_id = :oid
ORDER BY yt.code
""")


def _progress_row(db: Session, order: Order) -> dict[str, Decimal]:
    return dict(db.execute(_PROGRESS_SQL, {"oid": order.id}).mappings().one())


def progress(db: Session, order: Order) -> s.Progress:
    return _progress_out(_progress_row(db, order))


def _progress_out(row: dict[str, Decimal]) -> s.Progress:
    return s.Progress(**{key: to_float(value) for key, value in row.items()})


def stage(db: Session, order: Order, row: dict[str, Decimal]) -> str:
    """Spec §5: the furthest stage reached. Draft and cancelled come first, then dispatch, then the shop floor.
    `row` is the exact (Decimal) progress from _progress_row, so metres are compared without float rounding."""
    if order.state in ("draft", "cancelled"):
        return order.state
    if row["dispatched_m"] >= order.qty_metres:
        return "dispatched"
    if row["dispatched_m"] > 0:
        return "partly_dispatched"
    if row["passed_m"] >= order.qty_metres:
        return "ready_to_ship"
    flags = db.execute(_STAGE_SQL, {"oid": order.id}).mappings().one()
    if flags["needs_quality_check"]:
        return "quality_check"
    for name in ("dyeing", "weaving", "spinning"):
        if flags[f"has_{name}"]:
            return name
    return "waiting_to_start"


def _yarn_lines(db: Session, order: Order) -> list[dict]:
    """Per yarn type of the recipe, exact: need, issued, outstanding, free after the OTHER confirmed orders, and short."""
    lines = []
    for row in db.execute(_YARN_CHECK_SQL, {"oid": order.id}).mappings():
        available = max(ZERO, row["on_hand_kg"] - row["others_outstanding_kg"])
        lines.append({**row, "available_kg": available, "short_kg": max(ZERO, row["outstanding_kg"] - available)})
    return lines


def _check_out(db: Session, order: Order, lines: list[dict]) -> s.YarnCheckOut:
    return s.YarnCheckOut(order_code=order.code, can_start=all(line["short_kg"] == 0 for line in lines), lines=[
        s.YarnCheckLine(
            yarn_type=YarnTypeRef.model_validate(db.get(YarnType, line["yarn_type_id"])),
            need_kg=to_float(line["need_kg"]), issued_kg=to_float(line["issued_kg"]),
            outstanding_kg=to_float(line["outstanding_kg"]), available_kg=to_float(line["available_kg"]),
            short_kg=to_float(line["short_kg"]))
        for line in lines])


def yarn_check(db: Session, order: Order) -> s.YarnCheckOut:
    return _check_out(db, order, _yarn_lines(db, order))


def order_out(db: Session, order: Order) -> s.OrderOut:
    row = _progress_row(db, order)
    lines = _yarn_lines(db, order)
    short = sum((line["short_kg"] for line in lines), ZERO)
    if order.state == "cancelled" or all(line["outstanding_kg"] == 0 for line in lines):
        yarn_status = "not_needed"
    else:
        yarn_status = "short" if short > 0 else "can_start"
    return s.OrderOut(
        id=order.id, code=order.code, buyer=Ref.model_validate(order.buyer),
        fabric_type=Ref.model_validate(order.fabric_type), colour=order.colour,
        qty_metres=to_float(order.qty_metres), price_per_metre=to_float(order.price_per_metre),
        deadline=order.deadline, state=order.state, stage=stage(db, order, row), created_at=order.created_at,
        confirmed_at=order.confirmed_at, progress=_progress_out(row), yarn_status=yarn_status,
        short_kg=to_float(short), delivery_date=None, days_late=None)


def list_orders(db: Session, state: str | None = None, buyer_id: int | None = None) -> list[s.OrderOut]:
    if state is not None and state not in STATES:
        raise AppError("VALIDATION_ERROR", "state must be draft, confirmed or cancelled", field="state", status=422)
    query = select(Order).order_by(Order.id.desc())
    if state is not None:
        query = query.where(Order.state == state)
    if buyer_id is not None:
        query = query.where(Order.buyer_id == buyer_id)
    return [order_out(db, order) for order in db.scalars(query)]
