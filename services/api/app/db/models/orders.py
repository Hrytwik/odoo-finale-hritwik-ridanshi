import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import KG, MONEY, Base, IdMixin, nonblank
from app.db.models.master import Buyer, FabricType


class Order(IdMixin, Base):
    __tablename__ = "orders"
    code: Mapped[str] = mapped_column(String(20), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    fabric_type_id: Mapped[int] = mapped_column(ForeignKey("fabric_types.id"))
    colour: Mapped[str] = mapped_column(String(60))
    qty_metres: Mapped[Decimal] = mapped_column(KG)
    price_per_metre: Mapped[Decimal] = mapped_column(MONEY)
    deadline: Mapped[dt.date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(String(12), default="draft")
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_short_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    closed_short_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_short_reason: Mapped[str | None] = mapped_column(String(200))
    buyer: Mapped[Buyer] = relationship()
    fabric_type: Mapped[FabricType] = relationship()
    __table_args__ = (
        nonblank("code"), nonblank("colour"),
        CheckConstraint("qty_metres > 0", name="qty_pos"),
        CheckConstraint("price_per_metre > 0", name="price_pos"),
        CheckConstraint("state IN ('draft','confirmed','cancelled')", name="state_valid"),
        CheckConstraint("state <> 'confirmed' OR confirmed_at IS NOT NULL", name="confirmed_has_time"),
        CheckConstraint("(closed_short_at IS NULL) = (closed_short_by IS NULL) "
                        "AND (closed_short_at IS NULL) = (closed_short_reason IS NULL)", name="closed_short_all_or_none"),
        CheckConstraint("closed_short_at IS NULL OR state = 'confirmed'", name="closed_short_is_confirmed"),
    )
