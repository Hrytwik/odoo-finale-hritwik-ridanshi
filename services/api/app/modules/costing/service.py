"""Costing on request (spec §7): load the rows, run the engine, round to the paisa, shape the response.
Nothing here writes, locks or publishes. Money is rounded half up to the paisa and a total is the sum of its
rounded parts; the engine's own figures stay exact."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_ist
from app.core.money import q_kg, q_money, to_float
from app.db.models import (
    BuyerPayment, Invoice, InvoiceLine, Order, Roll, SupplierBill, SupplierPayment, WagePayment,
)
from app.modules.costing import loader
from app.modules.costing.engine.allocation import PARTS, OrderResult, allocate_order, is_final
from app.modules.costing.engine.labour import Labour, run_interval, split_labour
from app.modules.costing.engine.month import machine_hours, month_costs, month_window
from app.modules.costing.engine.runs import run_costs
from app.modules.costing.schemas import (
    CashPanel, CostParts, MachineMonth, MonthReport, OrderCost, OrderMonth, ProfitPanel, RollCost,
)
from app.modules.floor.service import db_now
from app.modules.orders.service import get_order_or_404
from app.modules.people.service import month_bounds, wage_rows
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


def month_report(db: Session, month: str) -> MonthReport:
    year, mon = (int(p) for p in month.split("-"))
    first, after, span = month_window(year, mon)
    last = after - dt.timedelta(days=1)
    now = db_now(db)
    b = loader.load_month(db, first, after, span, now)
    labour = split_labour(b.attendance, b.workers, b.shifts, b.runs, now)
    costs = month_costs(first, after, span, b.runs, b.machines, b.moves, b.writeoffs, labour, now)

    # --- profit
    invoiced = db.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0))
                         .where(Invoice.issued_at >= span[0], Invoice.issued_at < span[1]))
    wages = sum((Decimal(str(row.earned)) for row in wage_rows(db, *month_bounds(month))), ZERO)   # = GET /wages total
    yarn, machine, writeoffs = money(costs.yarn), money(costs.machine), money(costs.writeoffs)
    profit = ProfitPanel(
        invoiced=to_float(invoiced), yarn_issued=to_float(yarn), wages_earned=to_float(wages),
        idle_labour=to_float(money(costs.idle)), support_staff=to_float(money(costs.support)),
        machine_running_cost=to_float(machine), stock_writeoffs=to_float(writeoffs),
        profit=to_float(Decimal(invoiced) - yarn - wages - machine - writeoffs),
    )

    # --- cash (outstanding amounts are as at the end of the month, or today for the current month)
    asof = min(last, today_ist())

    def total(column, *conditions) -> Decimal:
        return Decimal(db.scalar(select(func.coalesce(func.sum(column), 0)).where(*conditions)))

    received = total(BuyerPayment.amount, BuyerPayment.received_at.between(first, last))
    paid_suppliers = total(SupplierPayment.amount, SupplierPayment.paid_at.between(first, last))
    paid_wages = total(WagePayment.amount, WagePayment.paid_at.between(first, last))
    receivable = (total(Invoice.total_amount, Invoice.issued_at < span[1])
                  - total(BuyerPayment.amount, BuyerPayment.received_at <= asof))
    payable = (total(SupplierBill.amount, SupplierBill.bill_date <= asof)
               - total(SupplierPayment.amount, SupplierPayment.paid_at <= asof))
    cash = CashPanel(
        received_from_buyers=to_float(received), paid_to_suppliers=to_float(paid_suppliers),
        paid_wages=to_float(paid_wages), net_cash=to_float(received - paid_suppliers - paid_wages),
        receivables_outstanding=to_float(receivable), payables_outstanding=to_float(payable),
    )

    # --- machines
    machines = []
    for m in sorted(b.machines.values(), key=lambda x: x.code):
        if m.created_at >= span[1]:
            continue
        h = machine_hours(m, b.runs, b.downtimes, b.rolls, b.roll_runs, list(b.shifts.values()), span, now)
        unit = "kg" if m.stage == "spinning" else "m"
        machines.append(MachineMonth(
            code=m.code, name=m.name, stage=m.stage, running_h=two_places(h.running), idle_h=two_places(h.idle),
            down_h=two_places(h.down), output=two_places(h.output), output_unit=unit,
            lost_capacity=two_places((h.idle + h.down) * m.rated), lost_capacity_unit=unit,
        ))

    # --- orders: revenue is the month's invoice lines, cost is what the order incurred in the month
    revenue = {oid: Decimal(amount) for oid, amount in db.execute(
        select(InvoiceLine.order_id, func.sum(InvoiceLine.amount)).join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(Invoice.issued_at >= span[0], Invoice.issued_at < span[1]).group_by(InvoiceLine.order_id))}
    orders = []
    for order in db.scalars(select(Order).where(Order.id.in_(set(costs.per_order) | set(revenue) or {0})).order_by(Order.code)):
        cost = sum((money(v) for v in costs.per_order.get(order.id, {}).values()), ZERO)
        rev = revenue.get(order.id, ZERO)
        orders.append(OrderMonth(order_code=order.code, buyer_name=order.buyer.name, revenue=to_float(rev),
                                 cost=to_float(cost), profit=to_float(rev - cost)))
    in_month = {r.id for r in b.runs if run_interval(r, now)[0] < span[1] and run_interval(r, now)[1] > span[0]}
    return MonthReport(month=month, profit=profit, cash=cash, machines=machines, orders=orders,
                       warnings=_warnings(b, labour, in_month, now))
