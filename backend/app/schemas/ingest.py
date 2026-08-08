from pydantic import BaseModel, Field

from app.schemas.email import EmailInput


class IngestRequest(BaseModel):
    candidate_id: str = Field(min_length=1)
    emails: list[EmailInput] = Field(min_length=1, max_length=100)