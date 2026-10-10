import datetime as dt
from typing import Literal

from app.core.enums import Stage
from app.core.schemas import Out, Ref
from app.modules.store.schemas import YarnTypeRef


class StageFinish(Out):
    stage: Stage
    finish_date: dt.date


class WhatIf(Out):
    kind: Literal["add_shift", "move_to_front"]
    label: str
    delivery_date: dt.date
    days_late: int


class EtaOut(Out):
    order_code: str
    buyer_name: str
    deadline: dt.date
    delivery_date: dt.date
    days_late: int
    bottleneck_stage: Stage | None
    stages: list[StageFinish]
    what_ifs: list[WhatIf]


class ShortageOut(Out):
    yarn_type: YarnTypeRef
    free_kg: float
    reorder_level_kg: float
    falls_below_on: dt.date | None
    supplier: Ref | None
    order_by: dt.date | None
    suggested_kg: float
    overdue_days: int


class RootCauseRow(Out):
    factor: Literal["weaving_machine", "dyeing_machine", "weaving_operator", "weaving_shift", "yarn_lot"]
    value: str
    defective: int
    inspected: int
    rate: float
    rest_rate: float
    p_value: float
    flagged: bool
