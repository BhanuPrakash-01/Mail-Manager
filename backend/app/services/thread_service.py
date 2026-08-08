from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.thread import Thread


class ThreadService:

    def __init__(self, db: Session):
        self.db = db

    def find_existing_task(
        self,
        thread_id: str,
        candidate_id: str,
    ) -> str | None:

        statement = (
            select(Thread.task_id)
            .where(
                Thread.thread_id == thread_id,
                Thread.candidate_id == candidate_id,
                Thread.task_id.is_not(None),
            )
        )

        return self.db.execute(statement).scalar_one_or_none()