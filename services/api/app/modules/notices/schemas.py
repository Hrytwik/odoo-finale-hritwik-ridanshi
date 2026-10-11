import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

DelayReason = Literal[
    "yarn_shortage", "machine_breakdown", "power_cut", "staff_shortage", "quality_rework", "dye_delay", "transport", "buyer_change", "other",
]
Reason = DelayReason | Literal["dispatched"]  # what a notice can be about: a delay, or the order leaving the mill


class ReasonIn(BaseModel):
    reason: DelayReason


class NoticeIn(BaseModel):
    reason: DelayReason
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]


class ChannelOut(BaseModel):
    """How the message would also reach this buyer on WhatsApp, shown to the owner before sending."""
    whatsapp_ready: bool
    to: str | None  # the buyer's number with the middle hidden
    phone: str | None  # the buyer's number as digits with the country code (for a wa.me link); only the owner can ask for this
    problem: str | None  # why it would not be sent on WhatsApp, in words for the owner
    tracking_url: str | None


class DraftOut(BaseModel):
    message: str
    drafted_by_ai: bool
    channel: ChannelOut


class NoticeOut(BaseModel):
    id: int
    kind: Literal["delay", "dispatch"]
    order_code: str
    reason: Reason
    reason_label: str
    message: str
    created_at: dt.datetime
    read: bool
    whatsapp_status: Literal["not_sent", "sent", "failed", "skipped"]
    whatsapp_detail: str | None


class NotificationsOut(BaseModel):
    unread: int
    items: list[NoticeOut]


# ---- WhatsApp connection (owner) ----

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]


class MessagingSettingsIn(BaseModel):
    account_sid: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    # None keeps the saved token; an empty string removes it; anything else replaces it
    auth_token: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    from_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    content_sid: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None
    public_url: Short | None = None
    enabled: bool = False


class MessagingSettingsOut(BaseModel):
    account_sid: str | None
    token_set: bool
    from_number: str | None
    content_sid: str | None
    public_url: str | None
    enabled: bool
    ready: bool


class TestIn(BaseModel):
    to: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=40)]


class TestOut(BaseModel):
    status: Literal["sent", "failed", "skipped"]
    detail: str | None
    to: str | None
