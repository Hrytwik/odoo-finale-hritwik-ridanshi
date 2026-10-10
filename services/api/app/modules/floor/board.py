"""Floor reads: the board, the machine page, the run list and 'output today' (an India-time day).
Everything here is derived on every read from runs, downtimes, rolls and the v_machine_status view."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.core.clock import today_ist
from app.core.money import to_float
from app.core.schemas import Ref
from app.core.validate import not_found
from app.db.models import Machine, MachineDowntime, Order, ProductionRun, Roll, RollRun
from app.modules.floor import schemas as s
from app.modules.orders.service import progress_row

STAGE_ORDER = {"spinning": 0, "weaving": 1, "dyeing": 2}
RECENT_RUNS = 10

# one statement per stage, each for ALL machines; :today is the India-time date
_OUTPUT_SQL = {
    "spinning": text("""
        SELECT pr.machine_id, COALESCE(SUM(pr.output_kg), 0) AS qty FROM production_runs pr
         WHERE pr.stage = 'spinning' AND pr.ended_at IS NOT NULL
           AND (pr.ended_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id"""),
    "weaving": text("""
        SELECT pr.machine_id, SUM(r.metres) AS qty FROM rolls r
          JOIN roll_runs rr ON rr.roll_id = r.id AND rr.purpose = 'produce'
          JOIN production_runs pr ON pr.id = rr.run_id
         WHERE (r.created_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id"""),
    "dyeing": text("""
        SELECT pr.machine_id, SUM(r.metres) AS qty FROM roll_runs rr
          JOIN rolls r ON r.id = rr.roll_id JOIN production_runs pr ON pr.id = rr.run_id
         WHERE rr.purpose = 'dye' AND pr.ended_at IS NOT NULL
           AND (pr.ended_at AT TIME ZONE 'Asia/Kolkata')::date = :today GROUP BY pr.machine_id"""),
}


def output_today(db: Session) -> dict[int, Decimal]:
    """kg (spinning) or metres (weaving, dyeing) per machine for today in India time."""
    today, result = today_ist(), {}
    for sql in _OUTPUT_SQL.values():
        for machine_id, qty in db.execute(sql, {"today": today}):
            result[machine_id] = result.get(machine_id, Decimal(0)) + qty
    return result


# ---- runs ----------------------------------------------------------------------------------------------------

_RUN_LOAD = (selectinload(ProductionRun.order), selectinload(ProductionRun.machine),
             selectinload(ProductionRun.operator))


def _run_outs(db: Session, runs: list[ProductionRun]) -> list[s.RunOut]:
    rolls: dict[int, list[tuple[str, Decimal]]] = {}
    if runs:
        rows = db.execute(select(RollRun.run_id, Roll.code, Roll.metres).join(Roll, Roll.id == RollRun.roll_id)
                          .where(RollRun.run_id.in_([r.id for r in runs])).order_by(Roll.id))
        for run_id, code, metres in rows:
            rolls.setdefault(run_id, []).append((code, metres))
    outs = []
    for r in runs:
        linked = rolls.get(r.id, [])
        outs.append(s.RunOut(
            id=r.id, order_code=r.order.code, machine_code=r.machine.code if r.machine else None, stage=r.stage,
            operator=Ref(id=r.operator.id, name=r.operator.name), started_at=r.started_at, ended_at=r.ended_at,
            output_kg=to_float(r.output_kg) if r.output_kg is not None else None, input_run_id=r.input_run_id,
            roll_codes=[code for code, _ in linked], metres=to_float(sum((m for _, m in linked), Decimal(0)))))
    return outs


def run_out(db: Session, run: ProductionRun) -> s.RunOut:
    return _run_outs(db, [run])[0]


def list_runs(db: Session, stage: str | None = None, order_code: str | None = None) -> list[s.RunOut]:
    query = select(ProductionRun).options(*_RUN_LOAD).order_by(ProductionRun.started_at.desc(),
                                                               ProductionRun.id.desc())
    if stage is not None:
        query = query.where(ProductionRun.stage == stage)
    if order_code is not None:
        query = query.join(Order, Order.id == ProductionRun.order_id).where(Order.code == order_code)
    return _run_outs(db, list(db.scalars(query)))


# ---- machines ------------------------------------------------------------------------------------------------

def _progress_pct(row: dict[str, Decimal], order: Order, stage: str) -> float:
    """Progress of the run's own stage for its order: spun over need, woven or dyed over ordered metres."""
    if stage == "spinning":
        done, total = row["spun_kg"], row["need_kg"]
    elif stage == "weaving":
        done, total = row["woven_m"], order.qty_metres
    elif stage == "dyeing":
        done, total = row["dyed_m"], order.qty_metres
    else:
        return 0.0
    if total <= 0:
        return 0.0
    return float(min(Decimal(100), done / total * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _cards(db: Session, machines: list[Machine]) -> list[s.MachineCard]:
    """Cards for ACTIVE machines (v_machine_status lists active machines only), read for all of them at once."""
    ids = [m.id for m in machines]
    if not ids:
        return []
    status = dict(db.execute(text("SELECT machine_id, status FROM v_machine_status WHERE machine_id = ANY(:ids)"),
                             {"ids": ids}).all())
    runs = {r.machine_id: r for r in db.scalars(
        select(ProductionRun).options(selectinload(ProductionRun.order), selectinload(ProductionRun.operator))
        .where(ProductionRun.machine_id.in_(ids), ProductionRun.ended_at.is_(None)))}
    downtimes = {d.machine_id: d for d in db.scalars(
        select(MachineDowntime).where(MachineDowntime.machine_id.in_(ids), MachineDowntime.ended_at.is_(None)))}
    produced = output_today(db)
    progress: dict[int, dict[str, Decimal]] = {}
    cards = []
    for m in machines:
        run, down = runs.get(m.id), downtimes.get(m.id)
        brief = None
        if run is not None:
            row = progress.setdefault(run.order_id, progress_row(db, run.order))
            brief = s.RunBrief(id=run.id, order_code=run.order.code, stage=run.stage,
                               operator=Ref(id=run.operator.id, name=run.operator.name), started_at=run.started_at,
                               order_progress_pct=_progress_pct(row, run.order, run.stage))
        cards.append(s.MachineCard(
            code=m.code, name=m.name, stage=m.stage, status=status[m.id], current_run=brief,
            downtime=s.DowntimeOut(reason=down.reason, started_at=down.started_at) if down else None,
            output_today=to_float(produced.get(m.id, Decimal(0))), output_unit="kg" if m.stage == "spinning" else "m"))
    return cards


def machine_card(db: Session, machine: Machine) -> s.MachineCard:
    return _cards(db, [machine])[0]


def floor_board(db: Session) -> s.FloorBoard:
    machines = sorted(db.scalars(select(Machine).where(Machine.active)),
                      key=lambda m: (STAGE_ORDER[m.stage], m.code))
    cards = _cards(db, machines)
    counts = {name: sum(c.status == name for c in cards) for name in ("running", "idle", "down")}
    return s.FloorBoard(machines=cards, generated_at=db.scalar(select(func.clock_timestamp())), **counts)


def machine_detail(db: Session, machine_code: str) -> s.MachineDetail:
    machine = db.scalar(select(Machine).where(Machine.code == machine_code))
    if machine is None or not machine.active:
        raise not_found("Machine", "machine_code")
    recent = db.scalars(select(ProductionRun).options(*_RUN_LOAD).where(ProductionRun.machine_id == machine.id)
                        .order_by(ProductionRun.started_at.desc(), ProductionRun.id.desc()).limit(RECENT_RUNS))
    return s.MachineDetail(**machine_card(db, machine).model_dump(), recent_runs=_run_outs(db, list(recent)))
