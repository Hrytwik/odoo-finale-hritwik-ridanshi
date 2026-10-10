"""Spec 8.4: where did the yarn of one lot end up? The passport's trace (roll -> weaving run -> spinning run -> lots) run
the other way: lot -> spinning runs with a net positive issue -> weaving runs fed by them -> the rolls they made."""
from sqlalchemy import column, func, select, table
from sqlalchemy.orm import Session

from app.core.money import to_float
from app.db.models import Dispatch, DispatchItem, ProductionRun, Roll, RollRun, YarnMovement
from app.modules.store.schemas import RecallBuyer, RecallOut, RecallRoll
from app.modules.store.service import get_lot_or_404

v_roll_status = table("v_roll_status", column("roll_id"), column("status"))
ON_THE_FLOOR = ("woven", "dyeing", "awaiting_qc", "awaiting_rework", "in_rework", "rejected")


def lot_recall(db: Session, lot_code: str) -> RecallOut:
    lot = get_lot_or_404(db, lot_code)
    net = func.sum(YarnMovement.qty_kg)
    spinning = set(db.scalars(
        select(YarnMovement.production_run_id).where(YarnMovement.yarn_lot_id == lot.id,
                                                      YarnMovement.kind.in_(("issue", "return")))
        .group_by(YarnMovement.production_run_id).having(net < 0)))
    weaving = set(db.scalars(select(ProductionRun.id).where(ProductionRun.stage == "weaving",
                                                            ProductionRun.input_run_id.in_(spinning or {0}))))
    rolls = list(db.scalars(select(Roll).join(RollRun, RollRun.roll_id == Roll.id)
                            .where(RollRun.purpose == "produce", RollRun.run_id.in_(weaving or {0})).order_by(Roll.code)))
    status = dict(db.execute(select(v_roll_status.c.roll_id, v_roll_status.c.status)
                             .where(v_roll_status.c.roll_id.in_([r.id for r in rolls] or {0}))).all())
    truck = {roll_id: (code, state) for roll_id, code, state in db.execute(
        select(DispatchItem.roll_id, Dispatch.code, Dispatch.state).join(Dispatch, Dispatch.id == DispatchItem.dispatch_id)
        .where(DispatchItem.roll_id.in_([r.id for r in rolls] or {0})))}
    out = RecallOut(lot_code=lot.lot_code, is_blocked=lot.is_blocked, on_floor=[], in_store=[], loading=[],
                    dispatched=[], buyers=[])
    buyers: dict[int, dict] = {}
    for roll in rolls:
        state = status.get(roll.id, "woven")
        code = truck.get(roll.id, (None, None))[0]
        row = RecallRoll(roll_code=roll.code, order_code=roll.order.code, buyer_name=roll.order.buyer.name,
                         metres=to_float(roll.metres), status=state, dispatch_code=code)
        (out.on_floor if state in ON_THE_FLOOR else getattr(out, state)).append(row)
        entry = buyers.setdefault(roll.order.buyer_id, {"name": roll.order.buyer.name, "rolls": 0, "gone": 0, "codes": set()})
        entry["rolls"] += 1
        if state == "dispatched":
            entry["gone"] += 1
            entry["codes"].add(code)
    out.buyers = [RecallBuyer(buyer_id=buyer_id, buyer_name=e["name"], roll_count=e["rolls"],
                              dispatched_roll_count=e["gone"], dispatch_codes=sorted(e["codes"]))
                  for buyer_id, e in sorted(buyers.items(), key=lambda kv: kv[1]["name"])]
    return out
