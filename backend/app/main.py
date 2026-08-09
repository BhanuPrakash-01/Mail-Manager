import uuid

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.models.base import Base

from app.models.email import Email
from app.models.email_processing import EmailProcessing
from app.models.processing_run import ProcessingRun
from app.models.thread import Thread

from app.schemas.ingest import IngestRequest, IngestResponse

from app.services.email_processor import EmailProcessor
from app.services.gemini_service import GeminiService
from app.services.preprocessor import EmailPreprocessor
from app.services.processing_run import ProcessingRunService
from app.services.rule_engine import RuleEngine
from app.services.task_api import TaskAPIClient


app = FastAPI(
    title="Sales Inbox Task Router",
)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.post(
    "/ingest",
    response_model=IngestResponse,
)
def ingest(
    request: IngestRequest,
    db: Session = Depends(get_db),
):
    candidate_id = request.candidate_id.strip().lower()

    run_id = str(uuid.uuid4())

    run_service = ProcessingRunService(db)

    run = run_service.start(
        run_id=run_id,
        candidate_id=candidate_id,
    )

    processor = EmailProcessor(
        db=db,
        preprocessor=EmailPreprocessor(),
        gemini_service=GeminiService(),
        rule_engine=RuleEngine(),
        task_api=TaskAPIClient(),
    )

    try:
        for email in request.emails:
            try:
                result = processor.process(
                    email=email,
                    candidate_id=candidate_id,
                    run_id=run_id,
                )

                run_service.record_result(
                    run=run,
                    decision=result.decision,
                    status=result.status.value,
                )

            except Exception as exc:
                run.processed_count += 1
                run.error_count += 1

                print(
                    f"Error processing email "
                    f"{email.email_id}: {type(exc).__name__}: {exc}"
                )

                db.flush()

        run_service.complete(run)

        db.commit()

        return IngestResponse(
            run_id=run.run_id,
            status=run.status,
            processed_count=run.processed_count,
            created_count=run.created_count,
            updated_count=run.updated_count,
            skipped_count=run.skipped_count,
            error_count=run.error_count,
        )

    except Exception:
        db.rollback()
        raise