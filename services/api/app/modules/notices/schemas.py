import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

Reason = Literal[
    "yarn_shortage", "machine_breakdown", "power_cut", "staff_shortage", "quality_rework", "dye_delay", "transport", "buyer_change", "other",
]


class ReasonIn(BaseModel):
    reason: Reason


class NoticeIn(BaseModel):
    reason: Reason
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]


class DraftOut(BaseModel):
    message: str
    drafted_by_ai: bool


class NoticeOut(BaseModel):
    id: int
    order_code: str
    reason: Reason
    reason_label: str
    message: str
    created_at: dt.datetime
    read: bool


class NotificationsOut(BaseModel):
    unread: int
    items: list[NoticeOut]
