import datetime as dt

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, nonblank


class LlmSettings(IdMixin, Base):
    __tablename__ = "llm_settings"
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str | None] = mapped_column(String(300))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        nonblank("model"),
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("provider IN ('anthropic','openai_compatible')", name="provider_valid"),
        CheckConstraint("provider <> 'openai_compatible' OR base_url IS NOT NULL", name="base_url_needed"),
    )


class LlmEvalRun(IdMixin, Base):
    __tablename__ = "llm_eval_runs"
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(120))
    run_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    score: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    details: Mapped[list] = mapped_column(JSONB)
    __table_args__ = (CheckConstraint("total > 0 AND score >= 0 AND score <= total", name="score_range"),)
