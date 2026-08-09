from enum import Enum

from pydantic import BaseModel


class ProcessingStatus(str, Enum):
    COMPLETED = "completed"
    PROCESSING_ERROR = "processing_error"
    TASK_API_ERROR = "task_api_error"


class ProcessingResult(BaseModel):
    email_id: str
    decision: str
    status: ProcessingStatus
    task_id: str | None = None
    error_stage: str | None = None
    error_message: str | None = None