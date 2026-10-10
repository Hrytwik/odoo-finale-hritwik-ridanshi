import datetime as dt
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.core.enums import MovementKind, RollStatus
from app.core.schemas import Money, NonBlank, Out, PositiveQty, Ref


class YarnTypeRef(Out):
    id: int
    code: str
    name: str
    colour: str


class LotReceiveIn(BaseModel):
    yarn_type_id: int
    supplier_id: int
    qty_kg: PositiveQty
    cost_per_kg: Money
    challan_no: NonBlank
    intended_order_code: NonBlank | None = None
    challan_photo_path: NonBlank | None = None


class LotOut(Out):
    id: int
    lot_code: str
    yarn_type: YarnTypeRef
    supplier: Ref
    qty_received_kg: float
    on_hand_kg: float
    cost_per_kg: float
    challan_no: str
    challan_photo_url: str | None
    intended_order_code: str | None
    received_at: dt.datetime
    is_blocked: bool
    blocked_reason: str | None


class MovementOut(Out):
    id: int
    lot_code: str
    kind: MovementKind
    qty_kg: float
    run_id: int | None
    order_code: str | None
    machine_code: str | None
    at: dt.datetime
    by: str
    note: str | None


class LotDetail(LotOut):
    movements: list[MovementOut]


class BlockIn(BaseModel):
    reason: NonBlank


class IssueIn(BaseModel):
    lot_code: NonBlank
    run_id: int
    qty_kg: PositiveQty


class ReturnIn(IssueIn):
    pass


class AdjustIn(BaseModel):
    lot_code: NonBlank
    qty_kg: Annotated[float, Field(ge=-1_000_000, le=1_000_000)]
    note: NonBlank

    @field_validator("qty_kg")
    @classmethod
    def not_zero(cls, v: float) -> float:
        if v == 0:
            raise ValueError("An adjustment cannot be zero")
        return v


class StockRow(Out):
    yarn_type: YarnTypeRef
    on_hand_kg: float
    outstanding_kg: float
    free_kg: float
    reorder_level_kg: float
    below_reorder: bool


class RecallRoll(Out):
    roll_code: str
    order_code: str
    buyer_name: str
    metres: float
    status: RollStatus
    dispatch_code: str | None


class RecallBuyer(Out):
    buyer_id: int
    buyer_name: str
    roll_count: int
    dispatched_roll_count: int
    dispatch_codes: list[str]


class RecallOut(Out):
    lot_code: str
    is_blocked: bool
    on_floor: list[RecallRoll]
    in_store: list[RecallRoll]
    loading: list[RecallRoll]
    dispatched: list[RecallRoll]
    buyers: list[RecallBuyer]
