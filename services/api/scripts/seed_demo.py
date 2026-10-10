"""A mill in the middle of a working day, built through the same service functions the API uses, so every number is
one the rules produced. Needs an empty database (no lots or orders yet). `npm run db:demo` runs build_demo().

The story (numbers are worked out in docs/plans/B9a-seed-and-demo-mill.md):
  Order A  Poplin 5,000 m for Sharma: spun (587.5 kg issued, 590 kg out), woven on LOOM-04 (3 rolls, 2,310 m), two
           rolls loaded into the running dye machine DYE-01.
  Order B  Twill 3,000 m for Kavya: spinning on SPIN-02, 300 kg issued.
  Order C  Poplin 3,174.603 m for Kavya, a draft: confirming it shows 'short 230 kg'.
  LOOM-06 is down ('belt snapped'); the other six machines are idle."""
import datetime as dt
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_ist
from app.db.models import Buyer, FabricType, Order, Supplier, User, Worker, YarnLot, YarnType
from app.db.session import SessionLocal
from app.modules.floor import rolls as floor_rolls
from app.modules.floor import schemas as fs
from app.modules.floor import service as floor
from app.modules.orders import schemas as os_
from app.modules.orders import service as orders
from app.modules.store import schemas as ss
from app.modules.store import service as store
from scripts import seed_dev


class DemoRefused(RuntimeError):
    pass


def _one(db: Session, model, column, value):
    return db.scalar(select(model).where(column == value))


def build_demo(db: Session) -> dict[str, str]:
    seed_dev.seed_all(db)                      # the starter facts (machines, workers, master data) must exist first
    if db.scalar(select(func.count()).select_from(YarnLot)) or db.scalar(select(func.count()).select_from(Order)):
        raise DemoRefused("The database already has lots or orders. The demo mill needs an empty database "
                          "(drop and recreate it, or point DATABASE_URL at a new one, then run db:migrate and db:demo).")
    today = today_ist()
    store_user = _one(db, User, User.username, "store")
    supervisor = _one(db, User, User.username, "supervisor")
    worker = lambda code: _one(db, Worker, Worker.code, code).id  # noqa: E731
    cotton, blend = (_one(db, YarnType, YarnType.code, c) for c in ("30S-COT-RAW", "40S-PC-RAW"))
    vardhman, coastal = (_one(db, Supplier, Supplier.name, n) for n in ("Vardhman Yarns", "Coastal Spinners"))
    sharma, kavya = (_one(db, Buyer, Buyer.name, n) for n in ("Sharma Fabrics", "Kavya Garments"))
    poplin, twill = (_one(db, FabricType, FabricType.name, n) for n in ("Poplin 58in", "Twill 58in"))

    lot_cotton = store.receive_lot(db, store_user, ss.LotReceiveIn(
        yarn_type_id=cotton.id, supplier_id=vardhman.id, qty_kg=800, cost_per_kg=250, challan_no="CH-5521"))
    lot_blend = store.receive_lot(db, store_user, ss.LotReceiveIn(
        yarn_type_id=blend.id, supplier_id=coastal.id, qty_kg=1450, cost_per_kg=280, challan_no="CH-5530"))

    def new_order(buyer, fabric, colour, metres, price, days, confirm=True) -> str:
        order = orders.create_order(db, os_.OrderIn(
            buyer_id=buyer.id, fabric_type_id=fabric.id, colour=colour, qty_metres=metres, price_per_metre=price,
            deadline=today + dt.timedelta(days=days)))
        if confirm:
            orders.confirm_order(db, order.code)
        return order.code

    order_a = new_order(sharma, poplin, "navy", 5000, 120, 10)
    order_b = new_order(kavya, twill, "charcoal", 3000, 150, 14)
    order_c = new_order(kavya, poplin, "maroon", 3174.603, 110, 21, confirm=False)

    # order A: spin, weave, start dyeing
    spin = floor.start_run(db, fs.RunStartIn(order_code=order_a, machine_code="SPIN-01", operator_worker_id=worker("W-001")))
    store.issue_yarn(db, supervisor, ss.IssueIn(lot_code=lot_cotton.lot_code, run_id=spin.id, qty_kg=587.5))
    floor.end_run(db, spin.id, fs.RunEndIn(output_kg=590))
    weave = floor.start_run(db, fs.RunStartIn(order_code=order_a, machine_code="LOOM-04",
                                              operator_worker_id=worker("W-006"), input_run_id=spin.id))
    made = [floor_rolls.roll_off(db, weave.id, fs.RollOffIn(metres=m)) for m in (1000, 800, 510)]
    dyeing = floor.start_run(db, fs.RunStartIn(order_code=order_a, machine_code="DYE-01", operator_worker_id=worker("W-007")))
    floor_rolls.load_rolls(db, dyeing.id, fs.LoadRollsIn(roll_codes=[made[0].code, made[1].code]))

    # order B: spinning on the second ring frame
    spin_b = floor.start_run(db, fs.RunStartIn(order_code=order_b, machine_code="SPIN-02", operator_worker_id=worker("W-008")))
    store.issue_yarn(db, supervisor, ss.IssueIn(lot_code=lot_blend.lot_code, run_id=spin_b.id, qty_kg=300))

    floor.breakdown(db, "LOOM-06", fs.BreakdownIn(reason="belt snapped"))
    db.commit()
    return {"order_a": order_a, "order_b": order_b, "order_c": order_c,
            "lot_cotton": lot_cotton.lot_code, "lot_blend": lot_blend.lot_code, "rolls": ", ".join(r.code for r in made)}


def main() -> None:
    with SessionLocal() as db:
        try:
            summary = build_demo(db)
        except DemoRefused as exc:
            print(f"Not done: {exc}")
            sys.exit(1)
    print("demo mill ready:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
