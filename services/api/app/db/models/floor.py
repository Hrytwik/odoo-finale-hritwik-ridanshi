import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import KG, Base, IdMixin, nonblank
from app.db.models.master import Machine
from app.db.models.orders import Order
from app.db.models.people import Worker


class MachineDowntime(IdMixin, Base):
    __tablename__ = "machine_downtimes"
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(200))
    __table_args__ = (
        nonblank("reason"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end_after_start"),
        Index("uq_open_downtime_per_machine", "machine_id", unique=True, postgresql_where=text("ended_at IS NULL")),
    )


class ProductionRun(IdMixin, Base):
    __tablename__ = "production_runs"
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    machine_id: Mapped[int | None] = mapped_column(ForeignKey("machines.id"))
    stage: Mapped[str] = mapped_column(String(20))
    operator_worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"))
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    output_kg: Mapped[Decimal | None] = mapped_column(KG)
    input_run_id: Mapped[int | None] = mapped_column(ForeignKey("production_runs.id"))
    order: Mapped[Order] = relationship()
    machine: Mapped[Machine | None] = relationship()
    operator: Mapped[Worker] = relationship()
    __table_args__ = (
        CheckConstraint("stage IN ('spinning','weaving','dyeing','rework')", name="stage_valid"),
        CheckConstraint("machine_id IS NOT NULL OR stage = 'rework'", name="machine_required"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="end_after_start"),
        CheckConstraint("output_kg IS NULL OR (stage = 'spinning' AND output_kg >= 0)", name="output_spinning_only"),
        CheckConstraint("(stage = 'weaving') = (input_run_id IS NOT NULL)", name="weaving_input"),
        Index("uq_open_run_per_machine", "machine_id", unique=True,
              postgresql_where=text("ended_at IS NULL AND machine_id IS NOT NULL")),
    )


class Roll(IdMixin, Base):
    __tablename__ = "rolls"
    code: Mapped[str] = mapped_column(String(20), unique=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    metres: Mapped[Decimal] = mapped_column(KG)
    order: Mapped[Order] = relationship()
    __table_args__ = (nonblank("code"), CheckConstraint("metres > 0", name="metres_pos"))


class RollRun(Base):
    __tablename__ = "roll_runs"
    roll_id: Mapped[int] = mapped_column(ForeignKey("rolls.id", ondelete="CASCADE"), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("production_runs.id"), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(10))
    __table_args__ = (CheckConstraint("purpose IN ('produce','dye','rework')", name="purpose_valid"),)
