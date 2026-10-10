"""Costing on request (spec §7): load the rows, run the engine, round to the paisa, shape the response.
Nothing here writes, locks or publishes. Money is rounded half up to the paisa and a total is the sum of its
rounded parts; the engine's own figures stay exact."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from sqlalchemy.orm import Session

from app.core.money import q_kg, q_money, to_float
from app.db.models import Order, Roll
from app.modules.costing import loader
from app.modules.costing.engine.allocation import PARTS, OrderResult, allocate_order, is_final
from app.modules.costing.engine.labour import Labour, split_labour
from app.modules.costing.engine.runs import run_costs
from app.modules.costing.schemas import CostParts, OrderCost, RollCost
from app.modules.floor.service import db_now
from app.modules.orders.service import get_order_or_404
from app.modules.rolls.service import get_roll_or_404

FINANCE = ("owner", "accountant")        # R18: the only roles that see cost
ZERO = Decimal(0)


def exact(value: Fraction) -> Decimal:
    return Decimal(value.numerator) / Decimal(value.denominator)


def money(value: Fraction) -> Decimal:
    return q_money(exact(value))


def two_places(value: Fraction) -> float:
    return float(exact(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _parts(parts: dict[str, Fraction]) -> dict[str, Decimal]:
    return {name: money(parts[name]) for name in PARTS}


def _warnings(bundle: loader.Bundle, labour: Labour, run_ids: set[int], now: dt.datetime) -> list[str]:
    out = []
    for run in bundle.runs:
        if run.id not in run_ids:
            continue
        gap = labour.uncovered.get(run.id)
        if gap:
            out.append(f"{bundle.labels[run.id]} has {two_places(gap)} hours not covered by its operator's attendance")
        if run.end is None:
            out.append(f"{bundle.labels[run.id]} is still open, so its cost is provisional")
    return out


class _OrderNumbers:
    """One order, costed: the bundle it was built from, the engine's result and whether it is final."""

    def __init__(self, db: Session, order: Order, now: dt.datetime):
        self.order = order
        self.bundle = loader.load_order(db, order, now)
        b = self.bundle
        self.labour = split_labour(b.attendance, b.workers, b.shifts, b.runs, now)
        costs = run_costs(b.runs, b.machines, b.moves, self.labour.per_run, now)
        self.runs = [r for r in b.runs if r.order_id == order.id]
        self.result: OrderResult = allocate_order(self.runs, b.rolls, b.roll_runs, costs)
        self.final = is_final(self.runs, b.rolls, self.result.good_metres, Fraction(order.qty_metres),
                              order.state == "cancelled")
        self.now = now


def order_cost(db: Session, order_code: str) -> OrderCost:
    order = get_order_or_404(db, order_code)
    n = _OrderNumbers(db, order, db_now(db))
    res = n.result
    parts = _parts(res.parts)
    total = sum(parts.values(), ZERO)
    good = exact(res.good_metres)
    revenue = q_money(good * order.price_per_metre)
    return OrderCost(
        order_code=order.code, parts=CostParts(**{k: to_float(v) for k, v in parts.items()}),
        reject_cost=to_float(money(res.reject_cost)), total=to_float(total),
        good_metres=to_float(q_kg(good)), rejected_metres=to_float(q_kg(exact(res.rejected_metres))),
        cost_per_good_metre=to_float(q_money(total / good)) if good > 0 else None,
        revenue=to_float(revenue), profit=to_float(revenue - total),
        unabsorbed=to_float(total if good == 0 else ZERO), provisional=not n.final,
        warnings=_warnings(n.bundle, n.labour, {r.id for r in n.runs}, n.now),
    )


def roll_cost_for(db: Session, roll: Roll, now: dt.datetime | None = None) -> RollCost:
    n = _OrderNumbers(db, roll.order, now or db_now(db))
    rr = n.result.rolls[roll.id]
    parts = _parts(rr.parts)
    share = money(rr.reject_share)
    total = sum(parts.values(), ZERO) + share
    return RollCost(
        roll_code=roll.code, parts=CostParts(**{k: to_float(v) for k, v in parts.items()}),
        reject_share=to_float(share), total=to_float(total),
        per_metre=to_float(q_money(total / exact(rr.metres))), provisional=not n.final,
    )


def roll_cost(db: Session, roll_code: str) -> RollCost:
    return roll_cost_for(db, get_roll_or_404(db, roll_code))


