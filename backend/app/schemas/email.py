from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    message_index: int = Field(ge=0)

    from_name: str | None = None
    from_email: str = Field(min_length=1)

    to: str | list[str]
    cc: list[str] = Field(default_factory=list)

    subject: str = ""

    body: str = ""

    received_at: datetime

    attachments: list[str] = Field(default_factory=list)

    is_reply: bool = False