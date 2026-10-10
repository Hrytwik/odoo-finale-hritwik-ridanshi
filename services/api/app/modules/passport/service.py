"""The Roll Passport: the whole life of one roll, assembled on request from runs, yarn issues, inspections and dispatch.
Cost is empty until costing (B6). A buyer gets the reduced buyer_view, and only for rolls of their own orders (R15)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.schemas import Ref
from app.core.validate import not_found
from app.db.models import (
    Dispatch, DispatchItem, Invoice, ProductionRun, QcInspection, Roll, RollRun, User, YarnLot, YarnMovement,
)
from app.modules.passport.schemas import Passport, PassportDispatch, PassportLot, PassportRun
from app.modules.qc.service import inspection_out
from app.modules.rolls.service import roll_out


def buyer_view(passport: Passport) -> Passport:
    """What a buyer may see: status, order, quality checks and dispatch. No cost, yarn lots, suppliers, machines,
    operators, inspector names, photos or AI output."""
    return passport.model_copy(update={
        "cost": None,
        "yarn_lots": [],
        "runs": [],
        "inspections": [
            i.model_copy(update={"inspector": Ref(id=0, name="Quality team"), "ai_suggestion": None, "photo_url": None})
            for i in passport.inspections
        ],
    })


def _runs(db: Session, roll: Roll) -> list[ProductionRun]:
    """Every run linked to the roll (made, dyed, reworked) plus the spinning run each of its weaving runs points at,
    each once, oldest first."""
    ids = set(db.scalars(select(RollRun.run_id).where(RollRun.roll_id == roll.id)))
    load = (selectinload(ProductionRun.machine), selectinload(ProductionRun.operator))
    runs = {r.id: r for r in db.scalars(select(ProductionRun).options(*load).where(ProductionRun.id.in_(ids)))}
    feeders = {r.input_run_id for r in runs.values() if r.stage == "weaving" and r.input_run_id is not None}
    if feeders - runs.keys():
        for r in db.scalars(select(ProductionRun).options(*load).where(ProductionRun.id.in_(feeders - runs.keys()))):
            runs[r.id] = r
    return sorted(runs.values(), key=lambda r: (r.started_at, r.id))


def _lots(db: Session, spinning_ids: set[int]) -> list[PassportLot]:
    """Lots with a net positive issue (issued minus returned) to the spinning run that fed the roll."""
    if not spinning_ids:
        return []
    net = func.sum(YarnMovement.qty_kg)
    rows = db.scalars(
        select(YarnLot).options(selectinload(YarnLot.yarn_type), selectinload(YarnLot.supplier))
        .join(YarnMovement, YarnMovement.yarn_lot_id == YarnLot.id)
        .where(YarnMovement.production_run_id.in_(spinning_ids), YarnMovement.kind.in_(("issue", "return")))
        .group_by(YarnLot.id).having(net < 0).order_by(YarnLot.id))
    return [PassportLot(lot_code=lot.lot_code, yarn_type=lot.yarn_type.name, supplier=lot.supplier.name,
                        is_blocked=lot.is_blocked) for lot in rows]


def _dispatch(db: Session, roll: Roll) -> PassportDispatch | None:
    dispatch = db.scalar(select(Dispatch).join(DispatchItem, DispatchItem.dispatch_id == Dispatch.id)
                         .where(DispatchItem.roll_id == roll.id))
    if dispatch is None:
        return None
    invoice_no = db.scalar(select(Invoice.invoice_no).where(Invoice.dispatch_id == dispatch.id))
    return PassportDispatch(code=dispatch.code, dispatched_at=dispatch.dispatched_at, vehicle_no=dispatch.vehicle_no,
                            invoice_no=invoice_no)


def get_passport(db: Session, user: User, roll_code: str) -> Passport:
    roll = db.scalar(select(Roll).where(Roll.code == roll_code))
    # a buyer asking for another buyer's roll gets exactly the answer for a roll that does not exist (R15)
    if roll is None or (user.role == "buyer" and roll.order.buyer_id != user.buyer_id):
        raise not_found("Roll", "roll_code")
    runs = _runs(db, roll)
    spinning = {r.id for r in runs if r.stage == "spinning"}
    inspections = db.scalars(select(QcInspection).where(QcInspection.roll_id == roll.id)
                             .order_by(QcInspection.inspected_at, QcInspection.id))
    order = roll.order
    passport = Passport(
        roll=roll_out(db, roll), order_code=order.code, buyer_name=order.buyer.name, deadline=order.deadline,
        yarn_lots=_lots(db, spinning),
        runs=[PassportRun(id=r.id, stage=r.stage, machine_code=r.machine.code if r.machine else None,
                          machine_name=r.machine.name if r.machine else None, operator=r.operator.name,
                          started_at=r.started_at, ended_at=r.ended_at) for r in runs],
        inspections=[inspection_out(db, i) for i in inspections],
        cost=None, dispatch=_dispatch(db, roll),
    )
    return buyer_view(passport) if user.role == "buyer" else passport
