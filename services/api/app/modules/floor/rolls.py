"""Rolls on the shop floor: a weaving run rolls one off (R7); a dyeing run is loaded with woven rolls (R8).
Lock order (see service.py): machine row, then the run row, then roll rows in ascending id."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.codes import next_code
from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import q_kg
from app.core.validate import exact_positive, invalid
from app.db.models import ProductionRun, Roll, RollRun
from app.modules.floor import schemas as s
from app.modules.floor.service import locked_open_run
from app.modules.rolls.service import v_roll_status


def roll_off(db: Session, run_id: int, body: s.RollOffIn) -> Roll:
    run = locked_open_run(db, run_id, stage="weaving")
    metres = exact_positive(body.metres, "metres", q_kg)
    roll = Roll(code=next_code(db, "roll"), order_id=run.order_id, metres=metres)
    db.add(roll)
    db.flush()
    db.add(RollRun(roll_id=roll.id, run_id=run.id, purpose="produce"))
    commit(db)
    db.refresh(roll)
    broadcaster.publish("roll.changed", roll.id)
    broadcaster.publish("run.changed", run.id)
    return roll


def load_rolls(db: Session, run_id: int, body: s.LoadRollsIn) -> ProductionRun:
    """All or nothing: every roll must exist, belong to the run's order and still be `woven`."""
    run = locked_open_run(db, run_id, stage="dyeing")
    codes = body.roll_codes
    if len(set(codes)) != len(codes):
        raise invalid("The same roll is listed twice", "roll_codes")
    by_code = {r.code: r for r in db.scalars(select(Roll).where(Roll.code.in_(codes)))}
    for code in codes:
        if code not in by_code:
            raise AppError("NOT_FOUND", f"Roll {code} not found", field="roll_codes", status=404)
    # lock the rolls (ascending id, so two loads can never wait on each other), then read their status: after the lock
    # a roll another run has just taken shows as `dyeing`
    locked = list(db.scalars(select(Roll).where(Roll.id.in_([r.id for r in by_code.values()])).order_by(Roll.id)
                             .with_for_update().execution_options(populate_existing=True)))
    status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                             .where(v_roll_status.c.roll_id.in_([r.id for r in locked]))).all())
    for code in codes:
        roll = by_code[code]
        if roll.order_id != run.order_id:
            raise AppError("ROLL_WRONG_ORDER", f"Roll {code} belongs to another order", field="roll_codes")
        if status[roll.id] != "woven":
            raise AppError("ROLL_WRONG_STATUS", f"Roll {code} is {status[roll.id]}, not woven", field="roll_codes")
    for roll in locked:
        db.add(RollRun(roll_id=roll.id, run_id=run.id, purpose="dye"))
    commit(db)
    for roll in locked:
        broadcaster.publish("roll.changed", roll.id)
    broadcaster.publish("run.changed", run.id)
    return run
