"""What a buyer may see of their own orders. Real data, read through the orders module's own functions.

A buyer sees only their own confirmed or cancelled orders, with dates and metres: never costs, prices, machines or
people. An order that belongs to someone else gets exactly the same 404 as one that does not exist.
"""
import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Order, User
from app.modules.insights import service as insights
from app.modules.orders import service as orders
from app.modules.portal import schemas as s

_STAGE_STARTS = text("""
SELECT stage, MIN(started_at) AS at FROM production_runs
WHERE order_id = :oid AND stage IN ('spinning', 'weaving', 'dyeing') GROUP BY stage
""")
_FIRST_PASS = text("""
SELECT MIN(q.inspected_at) AS at FROM qc_inspections q JOIN rolls r ON r.id = q.roll_id
WHERE r.order_id = :oid AND q.verdict = 'pass'
""")
_DISPATCHES = text("""
SELECT d.code, d.dispatched_at, SUM(r.metres) AS metres, i.invoice_no
FROM dispatches d
JOIN dispatch_items di ON di.dispatch_id = d.id
JOIN rolls r ON r.id = di.roll_id
LEFT JOIN invoices i ON i.dispatch_id = d.id
WHERE r.order_id = :oid AND d.state = 'dispatched'
GROUP BY d.id, d.code, d.dispatched_at, i.invoice_no
ORDER BY d.dispatched_at
""")
_STAGE_LABEL = {"spinning": "Spinning started", "weaving": "Weaving started", "dyeing": "Dyeing started"}


def _share_done(order: Order, progress: orders.s.Progress) -> float:
    """A rough share of the work finished: half weaving, a quarter dyeing, a quarter passed quality check."""
    qty = float(order.qty_metres)
    part = lambda metres: min(max(metres, 0.0), qty) / qty  # noqa: E731
    ready = max(progress.passed_m, progress.dispatched_m)
    return round(100 * (0.5 * part(progress.woven_m) + 0.25 * part(progress.dyed_m) + 0.25 * part(ready)), 1)


def _summary(db: Session, order: Order, dates: dict[str, tuple[dt.date, int]]) -> s.PortalOrder:
    """`dates` is the whole mill's delivery schedule (insights); the order service alone cannot see it."""
    out = orders.order_out(db, order)
    return s.PortalOrder(
        code=order.code, fabric=out.fabric_type.name, colour=order.colour, qty_metres=out.qty_metres, stage=out.stage,
        progress_pct=100.0 if out.stage == "dispatched" else _share_done(order, out.progress),
        deadline=order.deadline, delivery_date=dates[order.code][0] if order.code in dates else None)


def my_orders(db: Session, user: User) -> list[s.PortalOrder]:
    dates = insights.delivery_dates(db)
    query = (select(Order).where(Order.buyer_id == user.buyer_id, Order.state.in_(("confirmed", "cancelled")))
             .order_by(Order.id.desc()))
    return [_summary(db, order, dates) for order in db.scalars(query)]


def my_order(db: Session, user: User, code: str) -> s.PortalOrderDetail:
    order = db.scalar(select(Order).where(Order.code == code, Order.buyer_id == user.buyer_id,
                                          Order.state.in_(("confirmed", "cancelled"))))
    if order is None:
        raise AppError("NOT_FOUND", "Order not found", status=404)
    dates = insights.delivery_dates(db)
    events: list[tuple[dt.datetime, str]] = []
    if order.confirmed_at:
        events.append((order.confirmed_at, "Order confirmed"))
    for row in db.execute(_STAGE_STARTS, {"oid": order.id}).mappings():
        events.append((row["at"], _STAGE_LABEL[row["stage"]]))
    first_pass = db.execute(_FIRST_PASS, {"oid": order.id}).scalar()
    if first_pass:
        events.append((first_pass, "First rolls passed quality check"))
    dispatches = [s.PortalDispatch(code=r["code"], dispatched_at=r["dispatched_at"], metres=float(r["metres"]), invoice_no=r["invoice_no"])
                  for r in db.execute(_DISPATCHES, {"oid": order.id}).mappings()]
    for d in dispatches:
        events.append((d.dispatched_at, f"{d.metres:g} m dispatched ({d.code})"))
    events.sort(key=lambda e: e[0])
    return s.PortalOrderDetail(**_summary(db, order, dates).model_dump(), timeline=[s.TimelineEvent(at=at, label=label) for at, label in events],
                               dispatches=dispatches)
