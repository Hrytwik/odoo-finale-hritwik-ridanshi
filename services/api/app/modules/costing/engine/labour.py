"""Spec §7.2: split each attendance record's pay across the runs its worker operated during that shift."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction
from zoneinfo import ZoneInfo

from .intervals import Interval, hours, intersect, measure, merge, overlap_hours
from .records import Attendance, Run, Shift, Worker

IST = ZoneInfo("Asia/Kolkata")
FACTOR = {"present": Fraction(1), "half_day": Fraction(1, 2)}   # absent is skipped


def shift_window(day: dt.date, shift: Shift) -> Interval:
    """The shift on the day it starts; a shift whose end is not after its start runs into the next day."""
    start = dt.datetime.combine(day, shift.start, tzinfo=IST)
    end = dt.datetime.combine(day, shift.end, tzinfo=IST)
    if end <= start:
        end += dt.timedelta(days=1)
    return start, end


def run_interval(run: Run, now: dt.datetime) -> Interval:
    """A run still open is costed up to now (never beyond)."""
    end = run.end if run.end is not None else now
    return run.start, max(end, run.start)


@dataclass
class RecordSplit:
    day: dt.date
    worker_id: int
    pay: Fraction
    allocated: dict[int, Fraction]      # run id -> share of this record's pay
    idle: Fraction                      # leftover of an operator
    support: Fraction                   # leftover of any other role


@dataclass
class Labour:
    records: list[RecordSplit] = field(default_factory=list)
    uncovered: dict[int, Fraction] = field(default_factory=dict)   # run id -> hours no attendance covers

    @property
    def per_run(self) -> dict[int, Fraction]:
        out: dict[int, Fraction] = {}
        for rec in self.records:
            for run_id, share in rec.allocated.items():
                out[run_id] = out.get(run_id, Fraction(0)) + share
        return out

    @property
    def idle(self) -> Fraction:
        return sum((r.idle for r in self.records), Fraction(0))

    @property
    def support(self) -> Fraction:
        return sum((r.support for r in self.records), Fraction(0))

    @property
    def pay(self) -> Fraction:
        return sum((r.pay for r in self.records), Fraction(0))


def split_labour(attendance: list[Attendance], workers: dict[int, Worker], shifts: dict[int, Shift],
                 runs: list[Run], now: dt.datetime) -> Labour:
    by_operator: dict[int, list[Run]] = {}
    for run in runs:
        by_operator.setdefault(run.operator_id, []).append(run)
    labour = Labour()
    windows: dict[int, list[Interval]] = {}          # worker id -> the windows that were paid
    for rec in attendance:
        factor = FACTOR.get(rec.status)
        if factor is None:
            continue
        worker, window = workers[rec.worker_id], shift_window(rec.day, shifts[rec.shift_id])
        windows.setdefault(rec.worker_id, []).append(window)
        pay = worker.daily_wage * factor
        paid_hours = hours(window[1] - window[0]) * factor
        spent = {run.id: overlap_hours(window, run_interval(run, now)) for run in by_operator.get(worker.id, [])}
        spent = {run_id: h for run_id, h in spent.items() if h > 0}
        divisor = max(sum(spent.values(), Fraction(0)), paid_hours)
        allocated = {run_id: pay * h / divisor for run_id, h in spent.items()}
        leftover = pay - sum(allocated.values(), Fraction(0))
        is_operator = worker.role == "operator"
        labour.records.append(RecordSplit(
            day=rec.day, worker_id=worker.id, pay=pay, allocated=allocated,
            idle=leftover if is_operator else Fraction(0), support=Fraction(0) if is_operator else leftover))
    for run in runs:
        span = run_interval(run, now)
        covered = measure(intersect([span], merge(windows.get(run.operator_id, []))))
        gap = hours(span[1] - span[0]) - covered
        if gap > 0:
            labour.uncovered[run.id] = gap
    return labour
