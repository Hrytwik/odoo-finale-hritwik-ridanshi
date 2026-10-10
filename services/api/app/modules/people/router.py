import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import require_roles
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.schemas import Ref
from app.db.models import Attendance, Shift, User, WagePayment, Worker
from app.db.session import get_db
from app.modules.people import schemas as s
from app.modules.people import service

router = APIRouter(tags=["people"])
viewers = require_roles("supervisor", "accountant", "owner")
markers = require_roles("supervisor", "owner")
accounts = require_roles("accountant", "owner")
Month = Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


def _shift_or_404(db: Session, shift_id: int) -> Shift:
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise AppError("NOT_FOUND", "That shift does not exist", field="shift_id", status=404)
    return shift


def _sheet(db: Session, date: dt.date, shift: Shift) -> s.AttendanceSheet:
    marked = {a.worker_id: a.status for a in db.scalars(
        select(Attendance).where(Attendance.work_date == date, Attendance.shift_id == shift.id))}
    workers = db.scalars(select(Worker).where(Worker.active | Worker.id.in_(marked)).order_by(Worker.name))
    return s.AttendanceSheet(
        date=date, shift=Ref(id=shift.id, name=shift.name),
        rows=[s.AttendanceRow(worker_id=w.id, worker_code=w.code, worker_name=w.name, status=marked.get(w.id))
              for w in workers],
    )


@router.get("/attendance", response_model=s.AttendanceSheet, dependencies=[Depends(viewers)])
def get_attendance(date: dt.date, shift_id: int, db: Session = Depends(get_db)) -> s.AttendanceSheet:
    """Every worker on the payroll for one shift on one day, with the status already marked (or none)."""
    return _sheet(db, date, _shift_or_404(db, shift_id))


@router.post("/attendance", response_model=s.AttendanceSheet)
def mark_attendance(body: s.AttendanceIn, db: Session = Depends(get_db), user: User = Depends(markers)) -> s.AttendanceSheet:
    """Marks (or corrects) attendance for a shift. Saving again for the same worker and shift changes the earlier mark."""
    if body.date > dt.date.today():
        raise AppError("FUTURE_DATE", "Attendance cannot be marked for a future date", field="date", status=422)
    shift = _shift_or_404(db, body.shift_id)
    worker_ids = {e.worker_id for e in body.entries}
    known = set(db.scalars(select(Worker.id).where(Worker.id.in_(worker_ids))))
    if known != worker_ids:
        raise AppError("NOT_FOUND", "One of those workers does not exist", field="entries", status=404)
    existing = {a.worker_id: a for a in db.scalars(
        select(Attendance).where(Attendance.work_date == body.date, Attendance.shift_id == shift.id,
                                 Attendance.worker_id.in_(worker_ids)))}
    for entry in body.entries:
        row = existing.get(entry.worker_id)
        if row:
            row.status, row.marked_by = entry.status, user.id
        else:
            db.add(Attendance(worker_id=entry.worker_id, work_date=body.date, shift_id=shift.id,
                              status=entry.status, marked_by=user.id))
    commit(db)
    broadcaster.publish("attendance.changed", shift.id)
    return _sheet(db, body.date, shift)


@router.get("/wages", response_model=s.WageSheet, dependencies=[Depends(accounts)])
def wages(month: Month, db: Session = Depends(get_db)) -> s.WageSheet:
    """Wages earned from attendance, paid so far and still owed, for each worker, for one calendar month."""
    start, end = service.month_bounds(month)
    rows = service.wage_rows(db, start, end)
    return s.WageSheet(
        month=month, rows=rows, total_earned=round(sum(r.earned for r in rows), 2),
        total_paid=round(sum(r.paid for r in rows), 2), total_owed=round(sum(r.owed for r in rows), 2),
    )


@router.post("/payments/wages", response_model=s.WageRow, status_code=201, dependencies=[Depends(accounts)])
def pay_wages(body: s.WagePaymentIn, db: Session = Depends(get_db)) -> s.WageRow:
    """Records a wage payment. It cannot be more than the worker is owed for the period (earned minus paid inside it)."""
    if body.paid_at > dt.date.today():
        raise AppError("FUTURE_DATE", "A payment cannot be dated in the future", field="paid_at", status=422)
    worker = db.get(Worker, body.worker_id)
    if worker is None:
        raise AppError("NOT_FOUND", "That worker does not exist", field="worker_id", status=404)
    counts = service.attendance_counts(db, body.period_start, body.period_end).get(worker.id, {})
    paid = service.paid_within(db, body.period_start, body.period_end).get(worker.id, 0)
    before = service.wage_row(worker, counts, paid)
    if body.amount > before.owed + 0.005:
        raise AppError("OVERPAYMENT", f"{worker.name} is owed only ₹{before.owed:,.2f} for this period", field="amount")
    db.add(WagePayment(worker_id=worker.id, period_start=body.period_start, period_end=body.period_end,
                       amount=body.amount, paid_at=body.paid_at))
    commit(db)
    broadcaster.publish("payment.changed", worker.id)
    paid_after = service.paid_within(db, body.period_start, body.period_end).get(worker.id, 0)
    return service.wage_row(worker, counts, paid_after)
