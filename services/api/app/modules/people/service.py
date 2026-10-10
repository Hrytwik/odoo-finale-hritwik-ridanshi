"""Wages: what each worker earned from attendance, what has been paid, and what is still owed."""
import calendar
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Attendance, WagePayment, Worker
from app.modules.people.schemas import WageRow

# a present shift pays the full daily wage, a half day pays half, an absence pays nothing
FULL, HALF = Decimal(1), Decimal("0.5")
CENT = Decimal("0.01")


def month_bounds(month: str) -> tuple[dt.date, dt.date]:
    year, mon = (int(p) for p in month.split("-"))
    return dt.date(year, mon, 1), dt.date(year, mon, calendar.monthrange(year, mon)[1])


def attendance_counts(db: Session, start: dt.date, end: dt.date) -> dict[int, dict[str, int]]:
    """worker id -> how many present, half_day and absent records fall between the dates."""
    rows = db.execute(
        select(Attendance.worker_id, Attendance.status, func.count())
        .where(Attendance.work_date.between(start, end))
        .group_by(Attendance.worker_id, Attendance.status)
    )
    counts: dict[int, dict[str, int]] = {}
    for worker_id, status, n in rows:
        counts.setdefault(worker_id, {})[status] = n
    return counts


def paid_within(db: Session, start: dt.date, end: dt.date) -> dict[int, Decimal]:
    """worker id -> total of the wage payments whose whole period lies inside the dates."""
    rows = db.execute(
        select(WagePayment.worker_id, func.sum(WagePayment.amount))
        .where(WagePayment.period_start >= start, WagePayment.period_end <= end)
        .group_by(WagePayment.worker_id)
    )
    return {worker_id: Decimal(total) for worker_id, total in rows}


def wage_row(worker: Worker, counts: dict[str, int], paid: Decimal | int) -> WageRow:
    present, half, absent = counts.get("present", 0), counts.get("half_day", 0), counts.get("absent", 0)
    earned = (Decimal(worker.daily_wage) * (present * FULL + half * HALF)).quantize(CENT, ROUND_HALF_UP)
    paid = Decimal(paid)
    return WageRow(
        worker_id=worker.id, worker_code=worker.code, worker_name=worker.name, daily_wage=float(worker.daily_wage),
        present=present, half_days=half, absent=absent, earned=float(earned), paid=float(paid),
        owed=float(earned - paid),
    )


def wage_rows(db: Session, start: dt.date, end: dt.date) -> list[WageRow]:
    """One row per worker who is on the payroll or has attendance or payments in the period."""
    counts = attendance_counts(db, start, end)
    paid = paid_within(db, start, end)
    rows: list[WageRow] = []
    for worker in db.scalars(select(Worker).order_by(Worker.code)):
        if worker.active or worker.id in counts or worker.id in paid:
            rows.append(wage_row(worker, counts.get(worker.id, {}), paid.get(worker.id, Decimal(0))))
    return rows
