import datetime as dt

from app.core.schemas import Ref
from app.modules.insights.schemas import EtaOut, RootCauseRow, ShortageOut, StageFinish, WhatIf
from app.modules.store.examples import COTTON

ETA = EtaOut(
    order_code="ORD-0012", buyer_name="Sharma Fabrics", deadline=dt.date(2026, 10, 20),
    delivery_date=dt.date(2026, 10, 22), days_late=2, bottleneck_stage="weaving",
    stages=[StageFinish(stage="spinning", finish_date=dt.date(2026, 10, 12)),
            StageFinish(stage="weaving", finish_date=dt.date(2026, 10, 19)),
            StageFinish(stage="dyeing", finish_date=dt.date(2026, 10, 20))],
    what_ifs=[WhatIf(kind="add_shift", label="Add a third shift on weaving", delivery_date=dt.date(2026, 10, 20),
                     days_late=0),
              WhatIf(kind="move_to_front", label="Move ORD-0012 to the front of every queue",
                     delivery_date=dt.date(2026, 10, 21), days_late=1)],
)
SHORTAGE = ShortageOut(yarn_type=COTTON, free_kg=-417.5, reorder_level_kg=300, falls_below_on=dt.date(2026, 10, 10),
                       supplier=Ref(id=1, name="Vardhman Yarns"), order_by=dt.date(2026, 10, 5), suggested_kg=750,
                       overdue_days=5)
ROOT_CAUSES = [
    RootCauseRow(factor="yarn_lot", value="L-0017", defective=9, inspected=20, rate=0.45, rest_rate=0.04,
                 p_value=0.00002, flagged=True),
    RootCauseRow(factor="weaving_machine", value="LOOM-05", defective=3, inspected=14, rate=0.21, rest_rate=0.09,
                 p_value=0.19, flagged=False),
]
