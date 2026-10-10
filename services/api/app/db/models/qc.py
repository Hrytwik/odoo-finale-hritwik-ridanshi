import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin


class QcInspection(IdMixin, Base):
    __tablename__ = "qc_inspections"
    roll_id: Mapped[int] = mapped_column(ForeignKey("rolls.id"))
    inspector_worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"))
    inspected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    photo_path: Mapped[str | None] = mapped_column(String(300))
    ai_suggestion: Mapped[dict | None] = mapped_column(JSONB)
    verdict: Mapped[str] = mapped_column(String(10))
    overrode_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    defects: Mapped[list["QcDefect"]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("verdict IN ('pass','rework','reject')", name="verdict_valid"),)


class QcDefect(IdMixin, Base):
    __tablename__ = "qc_defects"
    inspection_id: Mapped[int] = mapped_column(ForeignKey("qc_inspections.id", ondelete="CASCADE"))
    defect_type: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer)
    ai_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        CheckConstraint(
            "defect_type IN ('hole','stain','thread_fault','colour_mismatch','other')", name="type_valid"
        ),
        CheckConstraint("count > 0", name="count_pos"),
    )
