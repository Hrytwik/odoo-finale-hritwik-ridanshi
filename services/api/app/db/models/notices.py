import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, nonblank


class BuyerNotice(IdMixin, Base):
    """One message from the mill to a buyer about one of their orders, for example "your order is delayed because of ...".

    Written by the owner (the reason is chosen from a fixed list; the sentence is drafted and may be edited before it is
    sent). The buyer's bell reads these; `read_at` is when the buyer first opened it. When WhatsApp is connected the same
    message is also sent there, and `whatsapp_status` says what happened to that part.
    """

    __tablename__ = "buyer_notices"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    kind: Mapped[str] = mapped_column(String(20), default="delay")
    reason: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    sent_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_status: Mapped[str] = mapped_column(String(12), default="not_sent")
    whatsapp_detail: Mapped[str | None] = mapped_column(String(300))
    whatsapp_sid: Mapped[str | None] = mapped_column(String(60))
    __table_args__ = (
        nonblank("message"),
        CheckConstraint("kind IN ('delay')", name="kind_valid"),
        CheckConstraint("whatsapp_status IN ('not_sent','sent','failed','skipped')", name="whatsapp_status_valid"),
        Index("ix_buyer_notices_buyer_id_created_at", "buyer_id", "created_at"),
    )


class MessagingSettings(IdMixin, Base):
    """How the mill sends WhatsApp messages (a Twilio account). One row. The token is stored encrypted and never sent back."""

    __tablename__ = "messaging_settings"
    provider: Mapped[str] = mapped_column(String(30), default="twilio_whatsapp")
    account_sid: Mapped[str | None] = mapped_column(String(60))
    auth_token_encrypted: Mapped[str | None] = mapped_column(Text)
    from_number: Mapped[str | None] = mapped_column(String(30))
    content_sid: Mapped[str | None] = mapped_column(String(60))  # the message template to send through, when the sender needs one
    public_url: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("provider IN ('twilio_whatsapp')", name="provider_valid"),
    )
