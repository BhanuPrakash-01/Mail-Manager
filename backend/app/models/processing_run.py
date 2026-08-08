from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    run_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    candidate_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    processed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    created_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    updated_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    skipped_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    error_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )