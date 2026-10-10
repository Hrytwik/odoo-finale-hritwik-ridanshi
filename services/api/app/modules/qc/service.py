"""Quality control: record an inspection (R9) and start a rework run (R10), the QC queue.
Lock order (see floor/service.py): machine row, then roll rows. Timestamps come from db_now() after the locks."""
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import AppError, commit, flush
from app.core.events import broadcaster
from app.core.schemas import Ref
from app.core.validate import check_upload_path, invalid, not_found
from app.db.models import MachineDowntime, ProductionRun, QcDefect, QcInspection, Roll, RollRun, User, Worker
from app.modules.floor.service import db_now, get_machine_or_404, lock_machine
from app.modules.qc import schemas as s
from app.modules.rolls.service import get_roll_or_404, roll_outs, roll_status, v_roll_status


def record_inspection(db: Session, user: User, body: s.InspectionIn) -> QcInspection:
    roll = get_roll_or_404(db, body.roll_code)
    worker = user.worker
    if worker is None or not worker.active:
        raise AppError("INSPECTOR_REQUIRED", "This login is not linked to an active inspector", status=409)
    photo = check_upload_path(body.photo_path, "photo_path") if body.photo_path is not None else None
    if body.verdict != "pass" and not body.defects:
        raise AppError("DEFECTS_REQUIRED", "Record at least one defect when the roll is not passed", field="defects",
                       status=422)
    types = [d.defect_type for d in body.defects]
    if len(set(types)) != len(types):
        raise invalid("List each defect type once, with its total count", "defects")

    roll = get_roll_or_404(db, body.roll_code, for_update=True)
    status = roll_status(db, roll.id)
    if status != "awaiting_qc":
        raise AppError("ROLL_WRONG_STATUS", f"Roll {roll.code} is {status}, not awaiting QC", field="roll_code")

    suggestion = body.ai_suggestion
    inspection = QcInspection(
        roll_id=roll.id, inspector_worker_id=worker.id, inspected_at=db_now(db), photo_path=photo,
        ai_suggestion=suggestion.model_dump() if suggestion is not None else None, verdict=body.verdict,
        overrode_ai=suggestion is not None and suggestion.verdict != body.verdict, notes=body.notes,
    )
    inspection.defects = [QcDefect(defect_type=d.defect_type, count=d.count, ai_detected=d.ai_detected)
                          for d in body.defects]
    db.add(inspection)
    commit(db)
    db.refresh(inspection)
    broadcaster.publish("roll.changed", roll.id)
    broadcaster.publish("order.changed", roll.order_id)
    return inspection


def inspection_out(db: Session, inspection: QcInspection) -> s.InspectionOut:
    roll = db.get(Roll, inspection.roll_id)
    worker = db.get(Worker, inspection.inspector_worker_id)
    return s.InspectionOut(
        id=inspection.id, roll_code=roll.code, inspector=Ref(id=worker.id, name=worker.name),
        inspected_at=inspection.inspected_at, verdict=inspection.verdict, overrode_ai=inspection.overrode_ai,
        defects=[s.DefectOut(defect_type=d.defect_type, count=d.count, ai_detected=d.ai_detected)
                 for d in inspection.defects],
        photo_url=f"/api/{inspection.photo_path}" if inspection.photo_path else None,
        ai_suggestion=s.AiSuggestion.model_validate(inspection.ai_suggestion) if inspection.ai_suggestion else None,
        notes=inspection.notes,
    )


def start_rework(db: Session, body: s.ReworkIn) -> ProductionRun:
    """A rework run for one roll that the inspector sent back: manual mending (no machine) or a re-dye on a dyeing machine."""
    roll = get_roll_or_404(db, body.roll_code)
    machine = None
    if body.machine_code is not None:
        machine = lock_machine(db, get_machine_or_404(db, body.machine_code).id)
        if not machine.active:
            raise AppError("MACHINE_INACTIVE", "This machine is not active", field="machine_code")
        if machine.stage != "dyeing":
            raise AppError("WRONG_STAGE", "Rework uses a dyeing machine (re-dye) or no machine (mending)",
                           field="machine_code")
        if db.scalar(select(MachineDowntime.id).where(MachineDowntime.machine_id == machine.id,
                                                      MachineDowntime.ended_at.is_(None))) is not None:
            raise AppError("MACHINE_DOWN", "This machine is down", field="machine_code")
    operator = db.get(Worker, body.operator_worker_id)
    if operator is None:
        raise not_found("Worker", "operator_worker_id")
    if not operator.active:
        raise AppError("OPERATOR_INACTIVE", "This worker is not active", field="operator_worker_id")

    roll = get_roll_or_404(db, body.roll_code, for_update=True)
    status = roll_status(db, roll.id)
    if status != "awaiting_rework":
        raise AppError("ROLL_WRONG_STATUS", f"Roll {roll.code} is {status}, not awaiting rework", field="roll_code")

    run = ProductionRun(order_id=roll.order_id, machine_id=machine.id if machine else None, stage="rework",
                        operator_worker_id=operator.id, started_at=db_now(db))
    db.add(run)
    flush(db)    # a second open run on the machine fails here as MACHINE_BUSY (unique index) and rolls back
    db.add(RollRun(roll_id=roll.id, run_id=run.id, purpose="rework"))
    commit(db)
    db.refresh(run)
    broadcaster.publish("roll.changed", roll.id)
    broadcaster.publish("run.changed", run.id)
    if machine is not None:
        broadcaster.publish("machine.changed", machine.id)
    return run


_COUNTS_SQL = text("""
WITH latest AS (
  SELECT DISTINCT ON (roll_id) roll_id, verdict FROM qc_inspections ORDER BY roll_id, inspected_at DESC, id DESC
)
SELECT
  (SELECT count(*) FROM v_roll_status WHERE status = 'awaiting_qc') AS awaiting_qc,
  (SELECT count(*) FROM v_roll_status WHERE status = 'awaiting_rework') AS awaiting_rework,
  (SELECT count(*) FROM v_roll_status WHERE status = 'in_rework') AS in_rework,
  (SELECT count(*) FROM latest WHERE verdict = 'pass') AS passed,
  (SELECT count(*) FROM v_roll_status WHERE status = 'rejected') AS rejected
""")
NEEDS_ATTENTION = ("awaiting_qc", "awaiting_rework", "in_rework")


def queue(db: Session) -> s.QcQueue:
    """The inspector's view: how many rolls are in each state, and the rolls that need someone, oldest first.
    'passed' is every roll whose latest verdict is pass, wherever it is now (in store, loading, dispatched)."""
    counts = dict(db.execute(_COUNTS_SQL).mappings().one())
    waiting = list(db.scalars(select(Roll).join(v_roll_status, v_roll_status.c.roll_id == Roll.id)
                              .where(v_roll_status.c.status.in_(NEEDS_ATTENTION)).order_by(Roll.id)))
    return s.QcQueue(counts=s.QcCounts(**counts), rolls=roll_outs(db, waiting))
