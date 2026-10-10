"""Floor writes: start a run (R4), end and hand over (R6), breakdown and repair (R5).

Locking, always in this order: order row -> machine row -> roll rows (ascending id). A write takes only the ones it needs,
never in another order, so two writes cannot wait on each other. Timestamps written here come from db_now() (the real
clock, read AFTER the locks): the transaction-start now() could be earlier than a run that another transaction committed
while this one waited, which would break the end_after_start constraint."""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, commit
from app.core.events import broadcaster
from app.core.money import dec, q_kg
from app.core.validate import invalid, not_found
from app.db.models import Machine, MachineDowntime, ProductionRun, Worker
from app.modules.floor import schemas as s
from app.modules.orders.service import get_order_or_404


def db_now(db: Session) -> dt.datetime:
    return db.scalar(select(func.clock_timestamp()))


def get_machine_or_404(db: Session, machine_code: str) -> Machine:
    machine = db.scalar(select(Machine).where(Machine.code == machine_code))
    if machine is None:
        raise not_found("Machine", "machine_code")
    return machine


def lock_machine(db: Session, machine_id: int) -> Machine:
    """Take the machine's row lock and re-read the row, so what we check is what is committed now."""
    return db.scalar(select(Machine).where(Machine.id == machine_id).with_for_update()
                     .execution_options(populate_existing=True))


def locked_open_run(db: Session, run_id: int, stage: str | None = None) -> ProductionRun:
    """The run, with its machine locked (a rework run has no machine) and re-read, refused if it has ended or is of
    another stage than `stage`."""
    run = db.get(ProductionRun, run_id)
    if run is None:
        raise not_found("Production run", "run_id")
    if run.machine_id is not None:
        lock_machine(db, run.machine_id)
    run = db.scalar(select(ProductionRun).where(ProductionRun.id == run_id).with_for_update()
                    .execution_options(populate_existing=True))
    if run.ended_at is not None:
        raise AppError("RUN_NOT_OPEN", "This run has already ended", field="run_id")
    if stage is not None and run.stage != stage:
        raise AppError("WRONG_STAGE", f"This needs a {stage} run", field="run_id")
    return run


def _announce(run: ProductionRun) -> None:
    broadcaster.publish("run.changed", run.id)
    if run.machine_id is not None:
        broadcaster.publish("machine.changed", run.machine_id)


def start_run(db: Session, body: s.RunStartIn) -> ProductionRun:
    order = get_order_or_404(db, body.order_code, for_update=True)
    if order.state != "confirmed":
        raise AppError("ORDER_NOT_CONFIRMED", "A run can only start on a confirmed order", field="order_code")
    machine = get_machine_or_404(db, body.machine_code)
    machine = lock_machine(db, machine.id)
    if not machine.active:
        raise AppError("MACHINE_INACTIVE", "This machine is not active", field="machine_code")
    operator = db.get(Worker, body.operator_worker_id)
    if operator is None:
        raise not_found("Worker", "operator_worker_id")
    if not operator.active:
        raise AppError("OPERATOR_INACTIVE", "This worker is not active", field="operator_worker_id")
    if machine.stage == "weaving":
        if body.input_run_id is None:
            raise AppError("INPUT_RUN_REQUIRED", "A weaving run needs the spinning run whose yarn it uses",
                           field="input_run_id", status=422)
        source = db.get(ProductionRun, body.input_run_id)
        if source is None:
            raise not_found("Production run", "input_run_id")
        if source.order_id != order.id or source.stage != "spinning":
            raise AppError("INPUT_RUN_REQUIRED", "The input run must be a spinning run of the same order",
                           field="input_run_id")
    elif body.input_run_id is not None:
        raise invalid("Only a weaving run takes an input run", "input_run_id")
    if db.scalar(select(MachineDowntime.id).where(MachineDowntime.machine_id == machine.id,
                                                  MachineDowntime.ended_at.is_(None))) is not None:
        raise AppError("MACHINE_DOWN", "This machine is down", field="machine_code")
    run = ProductionRun(order_id=order.id, machine_id=machine.id, stage=machine.stage,
                        operator_worker_id=operator.id, input_run_id=body.input_run_id, started_at=db_now(db))
    db.add(run)
    commit(db)   # a second open run on the machine fails here as MACHINE_BUSY (unique index) and rolls back
    db.refresh(run)
    _announce(run)
    return run


def end_run(db: Session, run_id: int, body: s.RunEndIn) -> ProductionRun:
    run = locked_open_run(db, run_id)
    output = None
    if run.stage == "spinning":
        if body.output_kg is None:
            raise AppError("OUTPUT_REQUIRED", "Enter the kg spun when ending a spinning run", field="output_kg",
                           status=422)
        output = q_kg(dec(body.output_kg))
    elif body.output_kg is not None:
        raise AppError("OUTPUT_NOT_ALLOWED", "Only a spinning run has an output in kg", field="output_kg", status=422)
    run.ended_at, run.output_kg = db_now(db), output
    commit(db)
    db.refresh(run)
    _announce(run)
    return run


def handover(db: Session, run_id: int, body: s.HandoverIn) -> ProductionRun:
    """Shift change: end this run and start the next one on the same machine and order with the new operator, both at
    the same instant. Returns the NEW run."""
    old = locked_open_run(db, run_id)
    if old.machine_id is None:
        raise AppError("WRONG_STAGE", "A run without a machine cannot be handed over", field="run_id")
    operator = db.get(Worker, body.operator_worker_id)
    if operator is None:
        raise not_found("Worker", "operator_worker_id")
    if not operator.active:
        raise AppError("OPERATOR_INACTIVE", "This worker is not active", field="operator_worker_id")
    if operator.id == old.operator_worker_id:
        raise invalid("The new operator must be someone else", "operator_worker_id")
    now = db_now(db)
    old.ended_at = now
    db.flush()      # the old run must be closed before the new one is inserted: one open run per machine
    new = ProductionRun(order_id=old.order_id, machine_id=old.machine_id, stage=old.stage,
                        operator_worker_id=operator.id, input_run_id=old.input_run_id, started_at=now)
    db.add(new)
    commit(db)
    db.refresh(new)
    broadcaster.publish("run.changed", old.id)
    broadcaster.publish("run.changed", new.id)
    broadcaster.publish("machine.changed", new.machine_id)
    return new
