import datetime as dt
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import KG, MONEY, Base, IdMixin, nonblank


class Supplier(IdMixin, Base):
    __tablename__ = "suppliers"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    __table_args__ = (nonblank("name"), CheckConstraint("lead_time_days >= 0", name="lead_time_nonneg"))


class Buyer(IdMixin, Base):
    __tablename__ = "buyers"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    __table_args__ = (nonblank("name"),)


class YarnType(IdMixin, Base):
    __tablename__ = "yarn_types"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    colour: Mapped[str] = mapped_column(String(60))
    reorder_level_kg: Mapped[Decimal] = mapped_column(KG, default=0)
    __table_args__ = (
        nonblank("code"), nonblank("name"), nonblank("colour"),
        CheckConstraint("reorder_level_kg >= 0", name="reorder_nonneg"),
    )


class FabricType(IdMixin, Base):
    __tablename__ = "fabric_types"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    width_in: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    wastage_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=5)
    recipe_lines: Mapped[list["FabricRecipeLine"]] = relationship(
        back_populates="fabric_type", cascade="all, delete-orphan", order_by="FabricRecipeLine.id"
    )
    __table_args__ = (
        nonblank("name"),
        CheckConstraint("width_in > 0", name="width_pos"),
        CheckConstraint("wastage_pct >= 0 AND wastage_pct <= 50", name="wastage_range"),
    )


class FabricRecipeLine(IdMixin, Base):
    __tablename__ = "fabric_recipe_lines"
    fabric_type_id: Mapped[int] = mapped_column(ForeignKey("fabric_types.id", ondelete="CASCADE"))
    yarn_type_id: Mapped[int] = mapped_column(ForeignKey("yarn_types.id"))
    kg_per_metre: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    fabric_type: Mapped[FabricType] = relationship(back_populates="recipe_lines")
    yarn_type: Mapped[YarnType] = relationship()
    __table_args__ = (
        UniqueConstraint("fabric_type_id", "yarn_type_id"),
        CheckConstraint("kg_per_metre > 0", name="kg_per_metre_pos"),
    )


class Machine(IdMixin, Base):
    __tablename__ = "machines"
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(20))
    rated_output_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    running_cost_per_hour: Mapped[Decimal] = mapped_column(MONEY, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        nonblank("code"), nonblank("name"),
        CheckConstraint("stage IN ('spinning','weaving','dyeing')", name="stage_valid"),
        CheckConstraint("rated_output_per_hour > 0", name="rated_pos"),
        CheckConstraint("running_cost_per_hour >= 0", name="cost_nonneg"),
    )


class Shift(IdMixin, Base):
    __tablename__ = "shifts"
    name: Mapped[str] = mapped_column(String(10), unique=True)
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time] = mapped_column(Time)
    __table_args__ = (nonblank("name"), CheckConstraint("start_time <> end_time", name="times_differ"))
