import datetime as dt

from app.modules.costing.schemas import CostParts, RollCost
from app.modules.floor.examples import NOW, ROLL
from app.modules.passport.schemas import Passport, PassportLot, PassportRun
from app.modules.qc.examples import INSPECTION

PASSPORT = Passport(
    roll=ROLL.model_copy(update={"status": "in_store"}), order_code="ORD-0012", buyer_name="Sharma Fabrics",
    deadline=dt.date(2026, 10, 20),
    yarn_lots=[PassportLot(lot_code="L-0017", yarn_type="30s cotton", supplier="Vardhman Yarns", is_blocked=False)],
    runs=[
        PassportRun(id=41, stage="spinning", machine_code="SPIN-01", machine_name="Ring frame 1",
                    operator="Ravi Kumar", started_at=NOW - dt.timedelta(days=2), ended_at=NOW - dt.timedelta(days=1)),
        PassportRun(id=45, stage="weaving", machine_code="LOOM-04", machine_name="Loom 4", operator="Ravi Kumar",
                    started_at=NOW - dt.timedelta(hours=3), ended_at=None),
    ],
    inspections=[INSPECTION],
    cost=RollCost(roll_code="R-0142", parts=CostParts(yarn=3465, machine=1210, labour=640, rework=380),
                  reject_share=260, total=5955, per_metre=54.14, provisional=True),
    dispatch=None,
)
