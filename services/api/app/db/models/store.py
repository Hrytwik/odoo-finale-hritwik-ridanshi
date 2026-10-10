import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import KG, MONEY, Base, IdMixin, nonblank
from app.db.models.master import Supplier, YarnType


class YarnLot(IdMixin, Base):
    __tablename__ = "yarn_lots"
    lot_code: Mapped[str] = mapped_column(String(20), unique=True)
    yarn_type_id: Mapped[int] = mapped_column(ForeignKey("yarn_types.id"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    cost_per_kg: Mapped[Decimal] = mapped_column(MONEY)
    challan_no: Mapped[str] = mapped_column(String(60))
    challan_photo_path: Mapped[str | None] = mapped_column(String(300))
    intended_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    received_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    received_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    blocked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    yarn_type: Mapped[YarnType] = relationship()
    supplier: Mapped[Supplier] = relationship()
    movements: Mapped[list["YarnMovement"]] = relationship(order_by="YarnMovement.id")
    bill: Mapped["SupplierBill"] = relationship(back_populates="lot", uselist=False)
    __table_args__ = (
        nonblank("lot_code"), nonblank("challan_no"),
        CheckConstraint("cost_per_kg > 0", name="cost_pos"),
        CheckConstraint("NOT is_blocked OR blocked_at IS NOT NULL", name="blocked_has_time"),
        UniqueConstraint("supplier_id", "challan_no", "yarn_type_id"),
    )


class YarnMovement(IdMixin, Base):
    __tablename__ = "yarn_movements"
    yarn_lot_id: Mapped[int] = mapped_column(ForeignKey("yarn_lots.id"))
    kind: Mapped[str] = mapped_column(String(12))
    qty_kg: Mapped[Decimal] = mapped_column(KG)
    production_run_id: Mapped[int | None] = mapped_column(ForeignKey("production_runs.id"))
    note: Mapped[str | None] = mapped_column(Text)
    moved_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        CheckConstraint("kind IN ('receipt','issue','return','adjustment')", name="kind_valid"),
        CheckConstraint("qty_kg <> 0", name="qty_nonzero"),
        CheckConstraint(
            "(kind = 'receipt' AND qty_kg > 0) OR (kind = 'issue' AND qty_kg < 0) "
            "OR (kind = 'return' AND qty_kg > 0) OR kind = 'adjustment'",
            name="sign_matches_kind",
        ),
        CheckConstraint("(kind IN ('issue','return')) = (production_run_id IS NOT NULL)", name="run_link"),
        CheckConstraint("kind <> 'adjustment' OR btrim(coalesce(note, '')) <> ''", name="adjust_note"),
    )
