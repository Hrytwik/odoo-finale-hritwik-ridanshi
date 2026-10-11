"""The audit: reads the finished month through the real endpoint functions and checks each story and each invariant.

Every check prints PASS or FAIL with the figures it saw. Where a figure matters, an independent SQL recalculation straight
from the tables is compared with what the endpoint says. The audit is never loosened to make a build pass: a failing
story means the data (the scheduler's numbers) is tuned.
"""
import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.costing import router as costing
from app.modules.dispatch import service as dispatch
from app.modules.floor import board
from app.modules.insights import router as insights
from app.modules.money import service as money
from app.modules.portal import router as portal
from app.modules.qc import service as qc
from app.modules.store import router as store_router
from app.modules.store import service as store
from scripts.month.clock import SimClock
from scripts.month.plan import IST

COTTON = "30S-COT-RAW"
UNLUCKY_NAMES = ("W-009", "Farah Sheikh")
BUYERS = {"Sharma Fabrics", "Kavya Garments"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def report(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = [f"{'PASS' if c.ok else 'FAIL'}  {c.name.ljust(width)}  {c.detail}" for c in checks]
    failed = sum(1 for c in checks if not c.ok)
    lines.append(f"\n{len(checks) - failed} of {len(checks)} checks passed" + ("" if not failed else f", {failed} FAILED"))
    return "\n".join(lines)


def _month_bounds(month: str) -> tuple[dt.datetime, dt.datetime]:
    year, mon = (int(x) for x in month.split("-"))
    start = dt.datetime(year, mon, 1, tzinfo=IST)
    return start, dt.datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=IST)


def _run_id(warning: str) -> int | None:
    """The run a month-report warning is about ('Run 348 (LOOM-02, ...) has ...')."""
    try:
        return int(warning.split()[1])
    except (IndexError, ValueError):
        return None


def _months(end: dt.datetime) -> list[str]:
    first = end.replace(day=1) - dt.timedelta(days=1)
    return [f"{first:%Y-%m}", f"{end:%Y-%m}"]


# ---- structure: true for any month, big or small

def leaks(db: Session, clock: SimClock, **_) -> Check:
    found = clock.leaks()
    return Check("no real-clock timestamp left", not found, "none later than the simulated end" if not found else "; ".join(found))


def ledger(db: Session, **_) -> Check:
    sql = {r.lot_code: float(r.kg) for r in db.execute(text(
        "SELECT l.lot_code, COALESCE(sum(m.qty_kg), 0) AS kg FROM yarn_lots l LEFT JOIN yarn_movements m ON m.yarn_lot_id = l.id GROUP BY l.lot_code"))}
    api = {lot.lot_code: lot.on_hand_kg for lot in store.list_lots(db)}
    bad = {c: (api.get(c), kg) for c, kg in sql.items() if abs((api.get(c) or 0) - kg) > 0.001}
    return Check("yarn on hand = ledger sum, every lot", not bad and len(sql) == len(api), f"{len(sql)} lots" if not bad else str(bad))


def attendance_covers_runs(db: Session, **_) -> Check:
    rows = db.execute(text("""
        SELECT p.id FROM production_runs p
        WHERE p.machine_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.worker_id = p.operator_worker_id AND a.status = 'present'
              AND a.shift_id = (SELECT id FROM shifts WHERE name = CASE
                  WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time >= '06:00' AND (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '14:00' THEN 'A'
                  WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time >= '14:00' AND (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '22:00' THEN 'B'
                  ELSE 'C' END)
              AND a.date = CASE WHEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::time < '06:00'
                                THEN (p.started_at AT TIME ZONE 'Asia/Kolkata')::date - 1
                                ELSE (p.started_at AT TIME ZONE 'Asia/Kolkata')::date END)""")).all()
    return Check("every run's operator was present that shift", not rows, "all machine runs covered" if not rows else f"{len(rows)} runs not covered")


def month_reports(db: Session, clock: SimClock, **_) -> list[Check]:
    out = []
    for month in _months(clock.end):
        rep = costing.month_report(month=month, db=db)
        start, nxt = _month_bounds(month)
        invoiced = float(db.scalar(text("SELECT COALESCE(sum(total_amount), 0) FROM invoices WHERE issued_at >= :s AND issued_at < :e"),
                                   {"s": start, "e": nxt}))
        out.append(Check(f"month report {month}: invoiced = invoices in SQL", abs(rep.profit.invoiced - invoiced) < 0.005,
                         f"endpoint {rep.profit.invoiced:,.2f} | SQL {invoiced:,.2f}"))
        open_runs = {r[0] for r in db.execute(text("SELECT id FROM production_runs WHERE ended_at IS NULL"))}
        warn = [w for w in rep.warnings if "not covered" in w and _run_id(w) not in open_runs]
        tail = sum(1 for w in rep.warnings if "not covered" in w and _run_id(w) in open_runs)
        out.append(Check(f"month report {month}: no finished run lacks attendance", not warn,
                         ("no such warning" if not warn else warn[0]) + (f" ({tail} open run(s) are costed up to now)" if tail else "")))
    return out


def order_yarn_cost(db: Session, runner=None, **_) -> Check:
    code = runner.order["O1"] if runner else db.scalar(text("SELECT code FROM orders ORDER BY id LIMIT 1"))
    cost = costing.order_cost(order_code=code, db=db)
    sql = float(db.scalar(text("""
        SELECT COALESCE(-sum(m.qty_kg * l.cost_per_kg), 0) FROM yarn_movements m
        JOIN yarn_lots l ON l.id = m.yarn_lot_id JOIN production_runs r ON r.id = m.production_run_id
        JOIN orders o ON o.id = r.order_id WHERE o.code = :c AND m.kind IN ('issue', 'return')"""), {"c": code}))
    return Check(f"order {code}: yarn cost = ledger x lot price in SQL", abs(cost.parts.yarn - sql) < 0.01 and sql > 0,
                 f"endpoint {cost.parts.yarn:,.2f} | SQL {sql:,.2f}")


def portal_scope(db: Session, **_) -> Check:
    from app.db.models import User
    user = db.query(User).filter(User.username == "buyer").one()
    seen = {o.code for o in portal.my_orders(db=db, user=user)}
    own = {r[0] for r in db.execute(text("SELECT code FROM orders WHERE buyer_id = :b"), {"b": user.buyer_id})}
    return Check("buyer portal shows only the buyer's own orders", seen <= own and bool(seen), f"{len(seen)} of {len(own)} own orders")


# ---- the stories: only for the full month

def bad_lot(db: Session, runner, **_) -> list[Check]:
    code = runner.lot["lot:bad"]
    rows = insights.root_causes(db=db)
    flagged = [r for r in rows if r.factor == "yarn_lot" and r.flagged and r.value == code]
    lucky = [r for r in rows if r.factor == "weaving_operator" and r.flagged and r.value in UNLUCKY_NAMES]
    recall = store_router.lot_recall(lot_code=code, db=db)
    buyers = {b.buyer_name for b in recall.buyers}
    trucks = sum(b.dispatched_roll_count for b in recall.buyers)
    return [
        Check(f"bad lot {code} is flagged by root cause", bool(flagged),
              f"rate {flagged[0].rate:.0%} vs {flagged[0].rest_rate:.0%}, p={flagged[0].p_value:.2g}" if flagged
              else "flagged rows: " + str([(r.factor, r.value) for r in rows if r.flagged])),
        Check("the unlucky operator is not flagged (Bonferroni)", not lucky, "not flagged" if not lucky else str(lucky)),
        Check(f"recall of {code} reaches both buyers and dispatched rolls", buyers == BUYERS and trucks > 0,
              f"buyers {sorted(buyers)}, {trucks} dispatched rolls"),
    ]


def loss_order(db: Session, runner, **_) -> Check:
    code = runner.order["O6"]
    c = costing.order_cost(order_code=code, db=db)
    return Check(f"rework-loss order {code}: negative profit, rework cost", c.profit < 0 and c.parts.rework > 0,
                 f"profit {c.profit:,.0f}, rework {c.parts.rework:,.0f} of cost {c.total:,.0f}, rejected {c.rejected_metres:.0f} m")


def late_order(db: Session, runner, **_) -> Check:
    code = runner.order["O11"]
    rows = [r for r in insights.late_orders(db=db) if r.order_code == code]
    ok = bool(rows) and rows[0].days_late > 0 and rows[0].bottleneck_stage is not None
    return Check(f"late order {code} is late with a bottleneck", ok,
                 f"{rows[0].days_late} days late, bottleneck {rows[0].bottleneck_stage}" if rows else "not in the late list")


def low_yarn(db: Session, **_) -> Check:
    rows = [r for r in insights.shortages(db=db) if COTTON in str(r.yarn_type)]
    ok = bool(rows) and rows[0].suggested_kg > 0 and rows[0].supplier is not None
    return Check("cotton shortage with a supplier and a reorder quantity", ok,
                 f"free {rows[0].free_kg:,.0f} kg < level {rows[0].reorder_level_kg:,.0f}, order {rows[0].suggested_kg:,.0f} kg" if rows else "no cotton shortage listed")


def machines(db: Session, clock: SimClock, **_) -> list[Check]:
    state = board.floor_board(db) if hasattr(board, "floor_board") else None
    statuses = {m.status for m in state.machines} if state else set()
    rep = costing.month_report(month=f"{clock.end:%Y-%m}", db=db)
    prev = costing.month_report(month=_months(clock.end)[0], db=db)
    loom6 = [m for r in (rep, prev) for m in r.machines if m.code == "LOOM-06"]
    down_h, run_h = sum(m.down_h for m in loom6), sum(m.running_h for m in loom6)
    queue = qc.queue(db)
    return [
        Check("floor board shows running, idle and down machines", {"running", "idle", "down"} <= statuses, f"{sorted(statuses)}"),
        Check("the idle loom (LOOM-06) was down and never ran", down_h > 0 and run_h == 0, f"down {down_h:.0f} h, running {run_h:.0f} h"),
        Check("the QC queue has rolls waiting", queue.counts.awaiting_qc > 0 or queue.counts.awaiting_rework + queue.counts.in_rework > 0,
              str(queue.counts.model_dump())),
    ]


def money_stories(db: Session, **_) -> list[Check]:
    pay = money.payables(db)
    rec = money.receivables(db)
    partial = [r for r in rec if 0 < r.paid < r.total]
    unpaid = [r for r in rec if r.paid == 0]
    loading = dispatch.list_dispatches(db, "loading")
    return [
        Check("a supplier bill is overdue", any(p.overdue for p in pay), f"{sum(p.overdue for p in pay)} overdue of {len(pay)} bills"),
        Check("invoices: some paid, one part-paid, some unpaid", bool(partial) and len(unpaid) >= 2 and any(r.balance == 0 for r in rec),
              f"{len(rec)} invoices, {len(partial)} part-paid, {len(unpaid)} unpaid"),
        Check("a truck is still loading", bool(loading), f"{len(loading)} loading"),
    ]


def mix(db: Session, **_) -> Check:
    row = db.execute(text("""
        WITH latest AS (SELECT DISTINCT ON (roll_id) roll_id, verdict FROM qc_inspections ORDER BY roll_id, inspected_at DESC, id DESC)
        SELECT (SELECT count(*) FROM orders) AS orders, (SELECT count(*) FROM yarn_lots) AS lots, (SELECT count(*) FROM rolls) AS rolls,
               (SELECT count(*) FROM production_runs) AS runs, (SELECT count(*) FROM qc_inspections) AS inspections,
               (SELECT count(*) FROM latest WHERE verdict = 'pass') AS passed, (SELECT count(*) FROM latest WHERE verdict = 'rework') AS rework,
               (SELECT count(*) FROM latest WHERE verdict = 'reject') AS rejected, (SELECT count(*) FROM invoices) AS invoices""")).one()
    return Check("what the month contains (reported, not asserted)", True, ", ".join(f"{k} {v}" for k, v in row._mapping.items()))


def audit(db: Session, clock: SimClock, runner=None, full: bool = True) -> list[Check]:
    checks = [leaks(db, clock), ledger(db), attendance_covers_runs(db), *month_reports(db, clock), order_yarn_cost(db, runner),
              portal_scope(db)]
    if full:
        checks += [*bad_lot(db, runner), loss_order(db, runner), late_order(db, runner), low_yarn(db), *machines(db, clock),
                   *money_stories(db)]
    checks.append(mix(db))
    return checks
