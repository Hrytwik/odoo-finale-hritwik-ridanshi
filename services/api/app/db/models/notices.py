import datetime as dt

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, nonblank


class BuyerNotice(IdMixin, Base):
    """One message from the mill to a buyer about one of their orders, for example "your order is delayed because of ...".

    Written by the owner (the reason is chosen from a fixed list; the sentence is drafted and may be edited before it is
    sent). The buyer's bell reads these; `read_at` is when the buyer first opened it.
    """

    __tablename__ = "buyer_notices"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    kind: Mapped[str] = mapped_column(String(20), default="delay")
    reason: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    sent_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        nonblank("message"),
        CheckConstraint("kind IN ('delay')", name="kind_valid"),
        Index("ix_buyer_notices_buyer_id_created_at", "buyer_id", "created_at"),
    )
