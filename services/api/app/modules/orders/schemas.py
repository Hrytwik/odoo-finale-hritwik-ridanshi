import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.core.enums import OrderStage, OrderState
from app.core.schemas import Money, NonBlank, Out, PositiveQty, Ref
from app.modules.store.schemas import YarnTypeRef


class OrderIn(BaseModel):
    buyer_id: int
    fabric_type_id: int
    colour: NonBlank
    qty_metres: PositiveQty
    price_per_metre: Money
    deadline: dt.date


class CloseShortIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


class DeadlineIn(BaseModel):
    deadline: dt.date


class Progress(Out):
    need_kg: float
    spun_kg: float
    woven_m: float
    dyed_m: float
    passed_m: float
    rejected_m: float
    dispatched_m: float


class OrderOut(Out):
    id: int
    code: str
    buyer: Ref
    fabric_type: Ref
    colour: str
    qty_metres: float
    price_per_metre: float
    deadline: dt.date
    state: OrderState
    stage: OrderStage
    created_at: dt.datetime
    confirmed_at: dt.datetime | None
    progress: Progress
    yarn_status: Literal["can_start", "short", "not_needed"]
    short_kg: float
    delivery_date: dt.date | None
    days_late: int | None
    closed_short_at: dt.datetime | None
    closed_short_reason: str | None


class YarnCheckLine(Out):
    yarn_type: YarnTypeRef
    need_kg: float
    issued_kg: float
    outstanding_kg: float
    available_kg: float
    short_kg: float


class YarnCheckOut(Out):
    order_code: str
    can_start: bool
    lines: list[YarnCheckLine]
