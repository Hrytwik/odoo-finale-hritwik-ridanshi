import datetime as dt

from app.core.schemas import Ref
from app.modules.store.schemas import (
    LotDetail, LotOut, MovementOut, RecallBuyer, RecallOut, RecallRoll, StockRow, YarnTypeRef,
)

T0 = dt.datetime(2026, 10, 10, 9, 30, tzinfo=dt.UTC)
COTTON = YarnTypeRef(id=1, code="30S-COT-RAW", name="30s cotton", colour="raw white")
POLY = YarnTypeRef(id=2, code="40S-PC-RAW", name="40s poly-cotton", colour="raw white")

LOT = LotOut(
    id=17, lot_code="L-0017", yarn_type=COTTON, supplier=Ref(id=1, name="Vardhman Yarns"),
    qty_received_kg=800, on_hand_kg=212.5, cost_per_kg=250, challan_no="CH-5521", challan_photo_url=None,
    intended_order_code="ORD-0012", received_at=T0, is_blocked=False, blocked_reason=None,
)
MOVEMENTS = [
    MovementOut(id=101, lot_code="L-0017", kind="receipt", qty_kg=800, run_id=None, order_code=None,
                machine_code=None, at=T0, by="store", note=None),
    MovementOut(id=102, lot_code="L-0017", kind="issue", qty_kg=-587.5, run_id=41, order_code="ORD-0012",
                machine_code="SPIN-01", at=T0 + dt.timedelta(hours=2), by="supervisor", note=None),
]
LOT_DETAIL = LotDetail(**LOT.model_dump(), movements=MOVEMENTS)
STOCK = [
    StockRow(yarn_type=COTTON, on_hand_kg=212.5, outstanding_kg=630, free_kg=-417.5, reorder_level_kg=300,
             below_reorder=True),
    StockRow(yarn_type=POLY, on_hand_kg=1450, outstanding_kg=400, free_kg=1050, reorder_level_kg=250,
             below_reorder=False),
]
_r = dict(order_code="ORD-0012", buyer_name="Sharma Fabrics", metres=110)
RECALL = RecallOut(
    lot_code="L-0017", is_blocked=True,
    on_floor=[RecallRoll(roll_code="R-0150", status="dyeing", dispatch_code=None, **_r)],
    in_store=[RecallRoll(roll_code=f"R-014{i}", status="in_store", dispatch_code=None, **_r) for i in range(2, 8)],
    loading=[],
    dispatched=[RecallRoll(roll_code=f"R-013{i}", status="dispatched", dispatch_code="DSP-0007", **_r)
                for i in range(1, 4)],
    buyers=[RecallBuyer(buyer_id=1, buyer_name="Sharma Fabrics", roll_count=10, dispatched_roll_count=3,
                        dispatch_codes=["DSP-0007"])],
)
