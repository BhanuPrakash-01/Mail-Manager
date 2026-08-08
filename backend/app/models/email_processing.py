from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmailProcessing(Base):
    __tablename__ = "email_processing"

    email_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("emails.email_id"),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    assignee_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    priority: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    deal_value_inr: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    company_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    error_stage: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )