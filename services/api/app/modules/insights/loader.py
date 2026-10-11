"""Reads the rows the insights engines need and turns them into their plain records (no arithmetic happens here)."""
import datetime as dt
from dataclasses import dataclass
from fractions import Fraction

from sqlalchemy import column, func, select, table, text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.clock import IST
from app.db.models import (
    Machine, MachineDowntime, Order, ProductionRun, QcDefect, QcInspection, Roll, RollRun, Shift, Worker, YarnLot,
    YarnMovement, YarnType,
)
from app.modules.insights.engine.rootcause import RollFacts
from app.modules.insights.engine.schedule import STAGES, EffRun, OpenOrder, StageCapacity, observed_efficiency
from app.modules.orders.service import progress_row

v_roll_latest_dye = table("v_roll_latest_dye", column("roll_id"), column("machine_id"))


def _frac(value) -> Fraction:
    return Fraction(value)


def _hours(delta: dt.timedelta) -> Fraction:
    return Fraction(delta.days * 86400 + delta.seconds, 3600)


def shift_length(shift: Shift) -> Fraction:
    """Hours in the shift; one whose end is not after its start runs into the next day."""
    span = dt.datetime.combine(dt.date.min, shift.end_time) - dt.datetime.combine(dt.date.min, shift.start_time)
    return _hours(span if span > dt.timedelta(0) else span + dt.timedelta(days=1))


def stage_shift_counts() -> dict[str, int]:
    """STAGE_SHIFTS such as 'weaving=2,dyeing=2' as {'weaving': 2, 'dyeing': 2} (validated when the settings load)."""
    out = {}
    for part in filter(None, (p.strip() for p in settings.stage_shifts.split(","))):
        stage, _, count = part.partition("=")
        out[stage.strip()] = int(count)
    return out


# ---- the delivery-date schedule ---------------------------------------------------------------------------------

def load_open_orders(db: Session) -> list[tuple[Order, OpenOrder]]:
    """Confirmed orders with metres still to dispatch, and what is left to do for each (spec 8.1)."""
    out = []
    for order in db.scalars(select(Order).where(Order.state == "confirmed", Order.closed_short_at.is_(None)).order_by(Order.id)):
        row = progress_row(db, order)
        if row["dispatched_m"] >= order.qty_metres:
            continue
        qty, woven, dyed = _frac(order.qty_metres), _frac(row["woven_m"]), _frac(row["dyed_m"])
        work = {"spinning": max(Fraction(0), _frac(row["need_kg"]) - _frac(row["spun_kg"])),
                "weaving": max(Fraction(0), qty - (woven - _frac(row["rejected_m"]))),
                "dyeing": max(Fraction(0), woven - dyed)}
        out.append((order, OpenOrder(order.code, order.deadline, order.confirmed_at, work,
                                     fully_passed=row["passed_m"] >= order.qty_metres)))
    return out


def _efficiency_runs(db: Session, now: dt.datetime) -> list[EffRun]:
    since = now - dt.timedelta(days=settings.efficiency_window_days)
    metres = dict(db.execute(
        select(RollRun.run_id, func.sum(Roll.metres)).join(Roll, Roll.id == RollRun.roll_id)
        .where(RollRun.purpose.in_(("produce", "dye"))).group_by(RollRun.run_id)).all())
    runs = []
    for run, rated in db.execute(
            select(ProductionRun, Machine.rated_output_per_hour).join(Machine, Machine.id == ProductionRun.machine_id)
            .where(ProductionRun.ended_at.is_not(None), ProductionRun.ended_at >= since, ProductionRun.ended_at <= now,
                   ProductionRun.stage.in_(STAGES))):
        if run.stage == "spinning":
            if run.output_kg is None:               # a run ended by hand-over keeps no output: it says nothing
                continue
            output = _frac(run.output_kg)
        else:
            output = _frac(metres.get(run.id, 0))
        runs.append(EffRun(run.stage, _hours(run.ended_at - run.started_at), _frac(rated), output))
    return runs


def load_stages(db: Session, now: dt.datetime) -> dict[str, StageCapacity]:
    """Per stage: rated output of the active machines that are up, times observed efficiency, and the shifts it runs."""
    shifts = tuple(shift_length(s) for s in db.scalars(select(Shift).order_by(Shift.id)))
    counts = stage_shift_counts()
    down = select(MachineDowntime.machine_id).where(MachineDowntime.ended_at.is_(None))
    machines = list(db.scalars(select(Machine).where(Machine.active.is_(True), Machine.id.not_in(down))))
    efficiency = observed_efficiency(_efficiency_runs(db, now), Fraction(str(settings.default_efficiency)),
                                     Fraction(str(settings.efficiency_min_hours)))
    return {stage: StageCapacity(
        sum((_frac(m.rated_output_per_hour) for m in machines if m.stage == stage), Fraction(0)) * efficiency[stage],
        shifts, min(counts.get(stage, len(shifts)), len(shifts))) for stage in STAGES}


# ---- the yarn shortage forecast ---------------------------------------------------------------------------------

@dataclass
class YarnInput:
    yarn_type: YarnType
    on_hand_kg: Fraction
    reorder_level_kg: Fraction
    supplier_id: int | None
    supplier_name: str | None
    lead_time_days: int | None
    demands: list[tuple[str, Fraction]]        # (order code, outstanding kg)


def load_yarn(db: Session) -> list[YarnInput]:
    stock = {r.yarn_type_id: r for r in db.execute(text(
        "SELECT yarn_type_id, on_hand_kg, reorder_level_kg FROM v_yarn_type_stock"))}
    demands: dict[int, list[tuple[str, Fraction]]] = {}
    for row in db.execute(text(
            "SELECT o.code, n.yarn_type_id, n.outstanding_kg FROM v_order_yarn_need n JOIN orders o ON o.id = n.order_id "
            "WHERE n.state = 'confirmed' AND n.outstanding_kg > 0")):
        demands.setdefault(row.yarn_type_id, []).append((row.code, _frac(row.outstanding_kg)))
    suppliers = {r.yarn_type_id: r for r in db.execute(text(
        "SELECT DISTINCT ON (l.yarn_type_id) l.yarn_type_id, s.id, s.name, s.lead_time_days "
        "FROM yarn_lots l JOIN suppliers s ON s.id = l.supplier_id "
        "ORDER BY l.yarn_type_id, l.received_at DESC, l.id DESC"))}
    out = []
    for yarn_type in db.scalars(select(YarnType).order_by(YarnType.code)):
        row, supplier = stock.get(yarn_type.id), suppliers.get(yarn_type.id)
        if row is None:
            continue
        out.append(YarnInput(yarn_type, _frac(row.on_hand_kg), _frac(row.reorder_level_kg),
                             supplier.id if supplier else None, supplier.name if supplier else None,
                             supplier.lead_time_days if supplier else None, demands.get(yarn_type.id, [])))
    return out


# ---- the defect root causes -------------------------------------------------------------------------------------

def _shift_name(started_at: dt.datetime, shifts: list[Shift]) -> str | None:
    moment = started_at.astimezone(IST).time()
    for shift in shifts:
        start, end = shift.start_time, shift.end_time
        if (start <= moment < end) if start < end else (moment >= start or moment < end):
            return shift.name
    return None


def load_roll_facts(db: Session) -> list[RollFacts]:
    """Every inspected roll with whether an inspector ever confirmed a defect on it, and the groups it belongs to."""
    inspected = set(db.scalars(select(QcInspection.roll_id).distinct()))
    defective = set(db.scalars(select(QcInspection.roll_id).join(QcDefect, QcDefect.inspection_id == QcInspection.id).distinct()))
    shifts = list(db.scalars(select(Shift).order_by(Shift.id)))
    made = {r.roll_id: r for r in db.execute(
        select(RollRun.roll_id, ProductionRun.input_run_id, ProductionRun.started_at, Machine.code.label("machine"),
               Worker.id.label("worker_id"), Worker.name.label("worker"))
        .join(ProductionRun, ProductionRun.id == RollRun.run_id).join(Machine, Machine.id == ProductionRun.machine_id)
        .join(Worker, Worker.id == ProductionRun.operator_worker_id)
        .where(RollRun.purpose == "produce", ProductionRun.stage == "weaving", RollRun.roll_id.in_(inspected or {0})))}
    dyers = dict(db.execute(select(v_roll_latest_dye.c.roll_id, Machine.code)
                            .join(Machine, Machine.id == v_roll_latest_dye.c.machine_id)
                            .where(v_roll_latest_dye.c.roll_id.in_(inspected or {0}))).all())
    spinning = {m.input_run_id for m in made.values() if m.input_run_id is not None}
    net = func.sum(YarnMovement.qty_kg)
    lots: dict[int, list[str]] = {}
    for run_id, lot_code in db.execute(
            select(YarnMovement.production_run_id, YarnLot.lot_code).join(YarnLot, YarnLot.id == YarnMovement.yarn_lot_id)
            .where(YarnMovement.production_run_id.in_(spinning or {0}), YarnMovement.kind.in_(("issue", "return")))
            .group_by(YarnMovement.production_run_id, YarnLot.lot_code).having(net < 0)):
        lots.setdefault(run_id, []).append(lot_code)
    facts = []
    for roll_id in sorted(inspected):
        groups: dict[str, list[tuple[str, str]]] = {}
        run = made.get(roll_id)
        if run is not None:
            groups["weaving_machine"] = [(run.machine, run.machine)]
            groups["weaving_operator"] = [(str(run.worker_id), run.worker)]
            shift = _shift_name(run.started_at, shifts)
            if shift is not None:
                groups["weaving_shift"] = [(shift, shift)]
            if run.input_run_id in lots:
                groups["yarn_lot"] = [(code, code) for code in sorted(lots[run.input_run_id])]
        if roll_id in dyers:
            groups["dyeing_machine"] = [(dyers[roll_id], dyers[roll_id])]
        facts.append(RollFacts(roll_id, roll_id in defective, groups))
    return facts
