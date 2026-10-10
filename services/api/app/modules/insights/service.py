"""The insights on request (spec 8): load the rows, run the engines, shape the existing response models.
Nothing here writes, locks or publishes. Money-free: only dates, kilograms, metres and probabilities."""
import datetime as dt
from decimal import Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import today_ist
from app.core.errors import AppError
from app.core.money import to_float
from app.core.schemas import Ref
from app.db.models import Order
from app.modules.floor.service import db_now
from app.modules.insights import loader
from app.modules.insights.engine.rootcause import analyse
from app.modules.insights.engine.schedule import STAGES, Eta, OpenOrder, StageCapacity, all_etas
from app.modules.insights.engine.shortage import Demand, forecast, spinning_window
from app.modules.insights.schemas import EtaOut, RootCauseRow, ShortageOut, StageFinish, WhatIf
from app.modules.orders.service import get_order_or_404
from app.modules.store.schemas import YarnTypeRef


class Schedule:
    """The whole mill's schedule, built once: an order's date depends on the orders ahead of it in every queue."""

    def __init__(self, db: Session, only: str | None = None, with_what_ifs: bool = True):
        self.today, now = today_ist(), db_now(db)
        pairs = loader.load_open_orders(db)
        self.orders: dict[str, OpenOrder] = {open_order.code: open_order for _, open_order in pairs}
        self.rows: dict[str, Order] = {order.code: order for order, _ in pairs}
        self.stages: dict[str, StageCapacity] = loader.load_stages(db, now)
        self.etas: dict[str, Eta | None] = all_etas(list(self.orders.values()), self.stages, self.today,
                                                    settings.qc_days, settings.dispatch_days, only, with_what_ifs)

    def missing_stage(self, code: str) -> str | None:
        """The first stage where this order has work and no machine is working."""
        order = self.orders[code]
        return next((s for s in STAGES if order.work[s] > 0 and self.stages[s].per_day() == 0), None)


def _eta_out(eta: Eta, order: Order) -> EtaOut:
    return EtaOut(
        order_code=eta.code, buyer_name=order.buyer.name, deadline=eta.deadline, delivery_date=eta.delivery,
        days_late=eta.days_late, bottleneck_stage=eta.bottleneck,
        stages=[StageFinish(stage=s, finish_date=eta.stage_dates[s]) for s in STAGES],
        what_ifs=[WhatIf(kind=w.kind, label=w.label, delivery_date=w.delivery, days_late=w.days_late) for w in eta.what_ifs])


def delivery_dates(db: Session) -> dict[str, tuple[dt.date, int]]:
    """order code -> (delivery date, days late) for every order waiting for production whose date is known."""
    schedule = Schedule(db, with_what_ifs=False)
    return {code: (eta.delivery, eta.days_late) for code, eta in schedule.etas.items() if eta is not None}


def order_eta(db: Session, order_code: str) -> EtaOut:
    order = get_order_or_404(db, order_code)
    schedule = Schedule(db, only=order_code)
    if order_code not in schedule.orders:
        raise AppError("NOT_SCHEDULED", "This order is not waiting for production", field="order_code", status=409)
    eta = schedule.etas[order_code]
    if eta is None:
        raise AppError("NO_CAPACITY", f"No working machine at {schedule.missing_stage(order_code)}",
                       field="order_code", status=409)
    return _eta_out(eta, order)


def late_orders(db: Session) -> list[EtaOut]:
    """Late orders, the most days late first."""
    schedule = Schedule(db)
    late = [(eta, schedule.rows[code]) for code, eta in schedule.etas.items() if eta is not None and eta.days_late > 0]
    late.sort(key=lambda pair: (-pair[0].days_late, pair[0].code))
    return [_eta_out(eta, order) for eta, order in late]


def shortages(db: Session) -> list[ShortageOut]:
    """Yarn types that are or will be below their reorder level, the most urgent first."""
    schedule = Schedule(db, with_what_ifs=False)
    rows = []
    for item in loader.load_yarn(db):
        demands = []
        for code, outstanding in item.demands:
            eta = schedule.etas.get(code)
            finish = None if eta is None else Fraction((eta.stage_dates["spinning"] - schedule.today).days)
            demands.append(Demand(code, outstanding, spinning_window(finish)))
        result = forecast(item.on_hand_kg, item.reorder_level_kg, demands, item.lead_time_days, schedule.today,
                          settings.reorder_round_kg)
        if result is None:
            continue
        yt = item.yarn_type
        rows.append(ShortageOut(
            yarn_type=YarnTypeRef(id=yt.id, code=yt.code, name=yt.name, colour=yt.colour),
            free_kg=to_float(_dec(result.free_kg)), reorder_level_kg=to_float(_dec(item.reorder_level_kg)),
            falls_below_on=result.falls_below_on,
            supplier=Ref(id=item.supplier_id, name=item.supplier_name) if item.supplier_id else None,
            order_by=result.order_by, suggested_kg=to_float(_dec(result.suggested_kg)), overdue_days=result.overdue_days))
    rows.sort(key=lambda r: (r.order_by is None, r.order_by or dt.date.max, r.yarn_type.code))
    return rows


def _dec(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def root_causes(db: Session) -> list[RootCauseRow]:
    rows = analyse(loader.load_roll_facts(db), settings.root_cause_min_group, Fraction(str(settings.root_cause_alpha)))
    return [RootCauseRow(factor=r.factor, value=r.value, defective=r.defective, inspected=r.inspected,
                         rate=float(r.rate), rest_rate=float(r.rest_rate), p_value=float(r.p_value), flagged=r.flagged)
            for r in rows]
