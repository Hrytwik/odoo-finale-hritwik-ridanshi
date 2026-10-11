import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MONEY, Base, IdMixin, nonblank
from app.db.models.master import Buyer


class Worker(IdMixin, Base):
    __tablename__ = "workers"
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    daily_wage: Mapped[Decimal] = mapped_column(MONEY)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        nonblank("code"), nonblank("name"),
        CheckConstraint(
            "role IN ('operator','inspector','storekeeper','supervisor','dispatch','helper')", name="role_valid"
        ),
        CheckConstraint("daily_wage > 0", name="wage_pos"),
    )


class User(IdMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(60), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.id"))
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("buyers.id"))
    # true while the password is one the owner chose for them: set when the owner creates a login or resets someone else's
    # password, cleared when its owner changes it
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    worker: Mapped[Worker | None] = relationship()
    buyer: Mapped[Buyer | None] = relationship()
    __table_args__ = (
        nonblank("username"),
        CheckConstraint(
            "role IN ('owner','accountant','store','supervisor','qc','dispatch','buyer')", name="role_valid"
        ),
        CheckConstraint("(role = 'buyer') = (buyer_id IS NOT NULL)", name="buyer_link"),
        CheckConstraint("role <> 'qc' OR worker_id IS NOT NULL", name="qc_needs_worker"),
    )


class Attendance(IdMixin, Base):
    __tablename__ = "attendance"
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"))
    work_date: Mapped[dt.date] = mapped_column("date", Date)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    status: Mapped[str] = mapped_column(String(10))
    marked_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        UniqueConstraint("worker_id", "date", "shift_id"),
        CheckConstraint("status IN ('present','half_day','absent')", name="status_valid"),
    )


class WagePayment(IdMixin, Base):
    __tablename__ = "wage_payments"
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"))
    period_start: Mapped[dt.date] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    paid_at: Mapped[dt.date] = mapped_column(Date)
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_pos"),
        CheckConstraint("period_end >= period_start", name="period_order"),
    )
