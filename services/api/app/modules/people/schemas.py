import datetime as dt
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.core.schemas import Money, Out, Ref

AttendanceStatus = Literal["present", "half_day", "absent"]


class AttendanceRow(Out):
    worker_id: int
    worker_code: str
    worker_name: str
    # None means nobody has marked this worker for this shift yet
    status: AttendanceStatus | None


class AttendanceSheet(Out):
    date: dt.date
    shift: Ref
    rows: list[AttendanceRow]


class AttendanceEntry(BaseModel):
    worker_id: int
    status: AttendanceStatus


class AttendanceIn(BaseModel):
    date: dt.date
    shift_id: int
    entries: Annotated[list[AttendanceEntry], Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def one_entry_per_worker(self) -> Self:
        ids = [e.worker_id for e in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("Each worker can appear only once")
        return self


class WageRow(Out):
    worker_id: int
    worker_code: str
    worker_name: str
    daily_wage: float
    present: int
    half_days: int
    absent: int
    earned: float
    paid: float
    owed: float


class WageSheet(Out):
    month: str
    rows: list[WageRow]
    total_earned: float
    total_paid: float
    total_owed: float


class WagePaymentIn(BaseModel):
    worker_id: int
    period_start: dt.date
    period_end: dt.date
    amount: Money
    paid_at: dt.date

    @model_validator(mode="after")
    def period_in_order(self) -> Self:
        if self.period_end < self.period_start:
            raise ValueError("The period must end on or after the day it starts")
        return self
