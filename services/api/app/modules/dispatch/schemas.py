import datetime as dt

from pydantic import BaseModel

from app.core.enums import DispatchState
from app.core.schemas import NonBlank, Out, Ref
from app.modules.rolls.schemas import RollOut


class DispatchIn(BaseModel):
    buyer_id: int
    vehicle_no: NonBlank
    driver_name: NonBlank | None = None


class ScanIn(BaseModel):
    roll_code: NonBlank


class OrderLoadSummary(Out):
    order_code: str
    ordered_m: float
    previously_dispatched_m: float
    loaded_m: float
    remaining_m: float
    over_shipped: bool


class DispatchOut(Out):
    id: int
    code: str
    buyer: Ref
    vehicle_no: str
    driver_name: str | None
    state: DispatchState
    created_at: dt.datetime
    dispatched_at: dt.datetime | None
    rolls: list[RollOut]
    orders: list[OrderLoadSummary]
    total_metres: float
    invoice_no: str | None
    warnings: list[str]


class InvoiceLineOut(Out):
    order_code: str
    fabric: str
    colour: str
    metres: float
    rate: float
    amount: float
    roll_codes: list[str]


class InvoiceOut(Out):
    invoice_no: str
    issued_at: dt.datetime
    buyer: Ref
    dispatch_code: str
    vehicle_no: str
    lines: list[InvoiceLineOut]
    total_amount: float
    paid_amount: float
    balance: float
