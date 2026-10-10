"""Reads the rows the costing engine needs and turns them into its plain records (no arithmetic happens here)."""
import datetime as dt
from dataclasses import dataclass, field
from fractions import Fraction

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.clock import IST
from app.db.models import (
    Attendance, Machine, MachineDowntime, Order, ProductionRun, Roll, RollRun, Shift, Worker, YarnLot, YarnMovement,
)
from app.modules.costing.engine import records as rec
from app.modules.rolls.service import v_roll_status

# a roll is "settled" once it is not still moving through weaving, dyeing, QC or rework
SETTLED = ("in_store", "rejected", "loading", "dispatched")
PAD = dt.timedelta(days=1)       # a night shift is dated by the day it starts, so look a day either side


@dataclass
class Bundle:
    runs: list[rec.Run] = field(default_factory=list)
    machines: dict[int, rec.Machine] = field(default_factory=dict)
    workers: dict[int, rec.Worker] = field(default_factory=dict)
    shifts: dict[int, rec.Shift] = field(default_factory=dict)
    attendance: list[rec.Attendance] = field(default_factory=list)
    moves: list[rec.YarnMove] = field(default_factory=list)
    writeoffs: list[rec.WriteOff] = field(default_factory=list)
    downtimes: list[rec.Downtime] = field(default_factory=list)
    rolls: list[rec.Roll] = field(default_factory=list)
    roll_runs: list[rec.RollRun] = field(default_factory=list)
    labels: dict[int, str] = field(default_factory=dict)     # run id -> "Run 52 (LOOM-05, 2026-10-08)"


def _frac(value) -> Fraction:
    return Fraction(value)


def _reference_data(db: Session, bundle: Bundle, workers: bool = True) -> None:
    for m in db.scalars(select(Machine)):
        bundle.machines[m.id] = rec.Machine(m.id, m.code, m.name, m.stage, _frac(m.rated_output_per_hour),
                                            _frac(m.running_cost_per_hour), m.created_at)
    for s in db.scalars(select(Shift)):
        bundle.shifts[s.id] = rec.Shift(s.id, s.name, s.start_time, s.end_time)
    if workers:
        for w in db.scalars(select(Worker)):
            bundle.workers[w.id] = rec.Worker(w.id, w.role, _frac(w.daily_wage))


def _runs(db: Session, bundle: Bundle, rows: list[ProductionRun]) -> None:
    for r in rows:
        bundle.runs.append(rec.Run(r.id, r.order_id, r.machine_id, r.stage, r.operator_worker_id, r.started_at,
                                   r.ended_at, _frac(r.output_kg) if r.output_kg is not None else None))
        machine = bundle.machines[r.machine_id].code if r.machine_id else "by hand"
        bundle.labels[r.id] = f"Run {r.id} ({machine}, {r.started_at.astimezone(IST).date()})"


def _attendance(db: Session, bundle: Bundle, lo: dt.date, hi: dt.date, worker_ids: set[int] | None = None) -> None:
    query = select(Attendance).where(Attendance.work_date.between(lo, hi))
    if worker_ids is not None:
        query = query.where(Attendance.worker_id.in_(worker_ids))
    bundle.attendance = [rec.Attendance(a.worker_id, a.work_date, a.shift_id, a.status) for a in db.scalars(query)]


def _rolls(db: Session, bundle: Bundle, roll_rows: list[Roll], with_status: bool) -> None:
    status = {}
    if with_status and roll_rows:
        status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                                 .where(v_roll_status.c.roll_id.in_([r.id for r in roll_rows]))).all())
    bundle.rolls = [rec.Roll(r.id, r.order_id, _frac(r.metres), status.get(r.id) == "rejected",
                             status.get(r.id, "in_store") in SETTLED, r.created_at) for r in roll_rows]
    ids = [r.id for r in roll_rows]
    if ids:
        bundle.roll_runs = [rec.RollRun(link.roll_id, link.run_id, link.purpose)
                            for link in db.scalars(select(RollRun).where(RollRun.roll_id.in_(ids)))]


def _moves(db: Session, bundle: Bundle, where) -> None:
    rows = db.execute(select(YarnMovement, YarnLot.cost_per_kg).join(YarnLot, YarnLot.id == YarnMovement.yarn_lot_id)
                      .where(YarnMovement.kind.in_(("issue", "return")), where))
    bundle.moves = [rec.YarnMove(m.production_run_id, _frac(m.qty_kg), _frac(cost), m.created_at) for m, cost in rows]


def load_order(db: Session, order: Order, now: dt.datetime) -> Bundle:
    """One order, plus the other runs of the same operators in the same hours (a weaver's pay is shared across every
    loom they minded, whatever the order)."""
    bundle = Bundle()
    _reference_data(db, bundle)
    mine = list(db.scalars(select(ProductionRun).where(ProductionRun.order_id == order.id)))
    operators = {r.operator_worker_id for r in mine}
    clause = ProductionRun.order_id == order.id
    if mine:
        lo = min(r.started_at for r in mine) - PAD
        hi = max((r.ended_at or now) for r in mine) + PAD
        clause = or_(clause, (ProductionRun.operator_worker_id.in_(operators)) & (ProductionRun.started_at < hi)
                     & (func.coalesce(ProductionRun.ended_at, now) > lo))
        _attendance(db, bundle, lo.astimezone(IST).date(), hi.astimezone(IST).date(), operators)
    rows = list(db.scalars(select(ProductionRun).where(clause)))
    _runs(db, bundle, rows)
    _moves(db, bundle, YarnMovement.production_run_id.in_([r.id for r in mine] or [0]))
    _rolls(db, bundle, list(db.scalars(select(Roll).where(Roll.order_id == order.id))), with_status=True)
    return bundle


def load_month(db: Session, first: dt.date, after: dt.date, span: tuple[dt.datetime, dt.datetime],
               now: dt.datetime) -> Bundle:
    """Everything that touches the month: runs overlapping it, the month's yarn movements and downtimes, and the
    attendance around the runs."""
    bundle = Bundle()
    _reference_data(db, bundle)
    lo, hi = span[0] - PAD, span[1] + PAD
    in_month = (YarnMovement.created_at >= span[0]) & (YarnMovement.created_at < span[1])
    _moves(db, bundle, in_month)
    moved_runs = {m.run_id for m in bundle.moves}
    overlap = (ProductionRun.started_at < hi) & (func.coalesce(ProductionRun.ended_at, now) > lo)
    rows = list(db.scalars(select(ProductionRun).where(or_(overlap, ProductionRun.id.in_(moved_runs or {0})))))
    _runs(db, bundle, rows)
    starts = [r.started_at for r in rows] + [span[0]]
    ends = [(r.ended_at or now) for r in rows] + [span[1]]
    _attendance(db, bundle, (min(starts) - PAD).astimezone(IST).date(), (max(ends) + PAD).astimezone(IST).date())
    for off in db.scalars(select(YarnMovement).where(YarnMovement.kind == "adjustment", YarnMovement.qty_kg < 0, in_month)):
        cost = db.scalar(select(YarnLot.cost_per_kg).where(YarnLot.id == off.yarn_lot_id))
        bundle.writeoffs.append(rec.WriteOff(_frac(off.qty_kg), _frac(cost), off.created_at))
    for d in db.scalars(select(MachineDowntime).where(MachineDowntime.started_at < span[1],
                                                       func.coalesce(MachineDowntime.ended_at, now) > span[0])):
        bundle.downtimes.append(rec.Downtime(d.machine_id, d.started_at, d.ended_at))
    run_ids = [r.id for r in rows]
    roll_ids = set(db.scalars(select(RollRun.roll_id).where(RollRun.run_id.in_(run_ids or [0]))))
    _rolls(db, bundle, list(db.scalars(select(Roll).where(Roll.id.in_(roll_ids or {0})))), with_status=False)
    return bundle
