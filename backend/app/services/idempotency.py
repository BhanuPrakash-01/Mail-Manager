from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email import Email
from app.models.email_processing import EmailProcessing


class IdempotencyService:

    def __init__(self, db: Session):
        self.db = db

    def email_already_processed(
        self,
        email_id: str,
        candidate_id: str,
    ) -> bool:

        statement = (
            select(EmailProcessing)
            .join(
                Email,
                Email.email_id == EmailProcessing.email_id,
            )
            .where(
                EmailProcessing.email_id == email_id,
                Email.candidate_id == candidate_id,
                EmailProcessing.status == "completed",
            )
        )

        result = self.db.execute(statement)

        return result.scalar_one_or_none() is not None