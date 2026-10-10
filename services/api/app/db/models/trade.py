import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import KG, MONEY, Base, IdMixin, nonblank


class Dispatch(IdMixin, Base):
    __tablename__ = "dispatches"
    code: Mapped[str] = mapped_column(String(20), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    vehicle_no: Mapped[str] = mapped_column(String(30))
    driver_name: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(12), default="loading")
    dispatched_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    items: Mapped[list["DispatchItem"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (
        nonblank("code"), nonblank("vehicle_no"),
        CheckConstraint("state IN ('loading','dispatched')", name="state_valid"),
        CheckConstraint("(state = 'dispatched') = (dispatched_at IS NOT NULL)", name="dispatched_has_time"),
    )


class DispatchItem(IdMixin, Base):
    __tablename__ = "dispatch_items"
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatches.id", ondelete="CASCADE"))
    roll_id: Mapped[int] = mapped_column(ForeignKey("rolls.id"), unique=True)


class Invoice(IdMixin, Base):
    __tablename__ = "invoices"
    invoice_no: Mapped[str] = mapped_column(String(20), unique=True)
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatches.id"), unique=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("buyers.id"))
    issued_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    total_amount: Mapped[Decimal] = mapped_column(MONEY)
    lines: Mapped[list["InvoiceLine"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("total_amount >= 0", name="total_nonneg"),)


class InvoiceLine(IdMixin, Base):
    __tablename__ = "invoice_lines"
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    metres: Mapped[Decimal] = mapped_column(KG)
    rate: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    __table_args__ = (
        CheckConstraint("metres > 0", name="metres_pos"),
        CheckConstraint("rate > 0", name="rate_pos"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
    )


class BuyerPayment(IdMixin, Base):
    __tablename__ = "buyer_payments"
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    received_at: Mapped[dt.date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (CheckConstraint("amount > 0", name="amount_pos"),)


class SupplierBill(IdMixin, Base):
    __tablename__ = "supplier_bills"
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    yarn_lot_id: Mapped[int] = mapped_column(ForeignKey("yarn_lots.id"), unique=True)
    bill_no: Mapped[str] = mapped_column(String(60))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    bill_date: Mapped[dt.date] = mapped_column(Date)
    due_date: Mapped[dt.date] = mapped_column(Date)
    lot: Mapped["YarnLot"] = relationship(back_populates="bill")
    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        CheckConstraint("due_date >= bill_date", name="due_after_bill"),
    )


class SupplierPayment(IdMixin, Base):
    __tablename__ = "supplier_payments"
    bill_id: Mapped[int] = mapped_column(ForeignKey("supplier_bills.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    paid_at: Mapped[dt.date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (CheckConstraint("amount > 0", name="amount_pos"),)
