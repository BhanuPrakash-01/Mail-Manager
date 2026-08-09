from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Email(Base):
    __tablename__ = "emails"

    email_id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
    )

    thread_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    candidate_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    from_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    from_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    message_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_reply: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )