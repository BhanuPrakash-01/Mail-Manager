from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Thread(Base):
    __tablename__ = "threads"

    thread_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    candidate_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    current_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_email_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )