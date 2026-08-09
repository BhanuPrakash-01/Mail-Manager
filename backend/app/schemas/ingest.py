from pydantic import BaseModel

from app.schemas.email import EmailInput


class IngestRequest(BaseModel):
    candidate_id: str
    emails: list[EmailInput]


class IngestResponse(BaseModel):
    run_id: str
    status: str
    processed_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    error_count: int