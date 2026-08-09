from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.processing_run import ProcessingRun


class ProcessingRunService:

    def __init__(self, db: Session):
        self.db = db

    def start(
        self,
        run_id: str,
        candidate_id: str,
    ) -> ProcessingRun:

        run = ProcessingRun(
            run_id=run_id,
            candidate_id=candidate_id,
            started_at=datetime.now(timezone.utc),
            status="processing",
        )

        self.db.add(run)
        self.db.flush()

        return run

    def complete(
        self,
        run: ProcessingRun,
    ) -> None:

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)

        self.db.flush()

    def record_result(
        self,
        run: ProcessingRun,
        decision: str,
        status: str,
    ) -> None:

        run.processed_count += 1

        if status == "completed":
            if decision == "skip":
                run.skipped_count += 1

            elif decision == "create_task":
                run.created_count += 1

            elif decision == "update_task":
                run.updated_count += 1

        else:
            run.error_count += 1

        self.db.flush()