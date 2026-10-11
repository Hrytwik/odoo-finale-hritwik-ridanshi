"""Plays a month plan through the real service functions, one event at a time, inside the simulated clock."""
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Buyer, Dispatch, FabricType, Invoice, Shift, Supplier, SupplierBill, User, Worker, YarnLot, YarnType
from app.modules.floor import rolls as floor_rolls
from app.modules.floor import schemas as fs
from app.modules.floor import service as floor
from app.modules.orders import schemas as os_
from app.modules.orders import service as orders
from app.modules.store import schemas as ss
from app.modules.store import service as store
from scripts.month.clock import SimClock
from scripts.month.plan import Event


class RunnerError(RuntimeError):
    pass


class Runner:
    def __init__(self, db: Session, clock: SimClock):
        self.db, self.clock = db, clock
        self.users = {u.username: u for u in db.scalars(select(User))}
        self.worker = {w.code: w.id for w in db.scalars(select(Worker))}
        self.buyer = {b.name: b.id for b in db.scalars(select(Buyer))}
        self.fabric = {f.name: f.id for f in db.scalars(select(FabricType))}
        self.yarn = {y.code: y.id for y in db.scalars(select(YarnType))}
        self.supplier = {s.name: s.id for s in db.scalars(select(Supplier))}
        self.shift = {s.name: s.id for s in db.scalars(select(Shift))}
        self.order: dict[str, str] = {}          # plan key -> order code
        self.lot: dict[str, str] = {}            # plan key -> lot code
        self.roll: dict[str, str] = {}           # plan key -> roll code
        self.run: dict[str, int] = {}            # run key -> the first run's id (a weaving run's input)
        self.open: dict[str, int] = {}           # machine code -> its open run id
        self.truck: dict[str, str] = {}          # plan key -> dispatch code
        self.hand_run: dict[str, int] = {}       # roll key -> its hand-mending run id
        self.count = 0

    def play(self, events: list[Event], only: set[str] | None = None) -> None:
        for e in events:
            if only is not None and e.action not in only:
                continue
            handler = getattr(self, f"do_{e.action}")
            try:
                with self.clock.at(e.t):
                    handler(**e.args)
            except Exception as exc:
                self.db.rollback()
                raise RunnerError(f"{e.t:%d %b %H:%M} {e.action} {e.args}: {exc}") from exc
            self.count += 1

    # ---- orders and yarn
    def do_create_order(self, order, buyer, fabric, colour, metres, price, deadline_days):
        created = orders.create_order(self.db, os_.OrderIn(
            buyer_id=self.buyer[buyer], fabric_type_id=self.fabric[fabric], colour=colour, qty_metres=metres,
            price_per_metre=price, deadline=self.clock.now.date() + dt.timedelta(days=deadline_days)))
        self.order[order] = created.code

    def do_confirm_order(self, order):
        orders.confirm_order(self.db, self.order[order])

    def do_cancel_order(self, order):
        orders.cancel_order(self.db, self.order[order])

    def do_receive_lot(self, lot, yarn, supplier, qty_kg, cost_per_kg, order, challan):
        body = ss.LotReceiveIn(yarn_type_id=self.yarn[yarn], supplier_id=self.supplier[supplier], qty_kg=qty_kg,
                               cost_per_kg=cost_per_kg, challan_no=challan,
                               intended_order_code=self.order[order] if order else None)
        self.lot[lot] = store.receive_lot(self.db, self.users["store"], body).lot_code

    def do_issue_yarn(self, machine, lot, qty_kg):
        store.issue_yarn(self.db, self.users["supervisor"], ss.IssueIn(lot_code=self.lot[lot], run_id=self.open[machine], qty_kg=qty_kg))

    # ---- runs
    def do_start_run(self, order, machine, operator, input_key, run_key):
        run = floor.start_run(self.db, fs.RunStartIn(order_code=self.order[order], machine_code=machine,
                                                    operator_worker_id=self.worker[operator],
                                                    input_run_id=self.run[input_key] if input_key else None))
        self.open[machine] = run.id
        if run_key:
            self.run[run_key] = run.id

    def do_handover(self, machine, operator):
        self.open[machine] = floor.handover(self.db, self.open[machine], fs.HandoverIn(operator_worker_id=self.worker[operator])).id

    def do_end_run(self, machine, run_key, output_kg):
        run_id = self.open.pop(machine) if machine else self.hand_run.pop(run_key.removeprefix("rework:"))
        floor.end_run(self.db, run_id, fs.RunEndIn(output_kg=output_kg))

    def do_roll_off(self, machine, roll, metres):
        self.roll[roll] = floor_rolls.roll_off(self.db, self.open[machine], fs.RollOffIn(metres=metres)).code

    def do_load_rolls(self, machine, rolls):
        floor_rolls.load_rolls(self.db, self.open[machine], fs.LoadRollsIn(roll_codes=[self.roll[r] for r in rolls]))
