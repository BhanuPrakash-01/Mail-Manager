import uuid
import concurrent.futures
from typing import Optional

from fastapi import Depends, FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.db.session import engine, get_db, SessionLocal
from app.models.base import Base

from app.models.email import Email
from app.models.email_processing import EmailProcessing
from app.models.processing_run import ProcessingRun
from app.models.thread import Thread

from app.schemas.ingest import IngestRequest, IngestResponse
from app.schemas.processing import ProcessingResult, ProcessingStatus

from app.services.email_processor import EmailProcessor
from app.services.gemini_service import GeminiService
from app.services.preprocessor import EmailPreprocessor
from app.services.processing_run import ProcessingRunService
from app.services.rule_engine import RuleEngine
from app.services.task_api import get_task_api_client


app = FastAPI(
    title="Sales Inbox Task Router",
)

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


def process_emails_background(run_id: str, candidate_id: str, emails: list):
    # Create a single Task API client shared by all workers in this run.
    # For mock: shares in-memory state. For real: each call is stateless HTTP.
    task_api = get_task_api_client()

    def process_single_email(email):
        with SessionLocal() as db:
            processor = EmailProcessor(
                db=db,
                preprocessor=EmailPreprocessor(),
                gemini_service=GeminiService(),
                rule_engine=RuleEngine(),
                task_api=task_api,
            )
            try:
                result = processor.process(
                    email=email,
                    candidate_id=candidate_id,
                    run_id=run_id,
                )
                db.commit()
                return result
            except Exception as exc:
                db.rollback()
                print(f"Unhandled error for {email.email_id}: {exc}")
                
                try:
                    import datetime
                    processing = EmailProcessing(
                        email_id=email.email_id,
                        run_id=run_id,
                        decision="processing_error",
                        processing_status="processing_error",
                        error_stage="unhandled",
                        error_message=str(exc),
                        processed_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                    db.merge(processing)
                    db.commit()
                except Exception:
                    db.rollback()

                return ProcessingResult(
                    email_id=email.email_id,
                    decision="processing_error",
                    status=ProcessingStatus.PROCESSING_ERROR,
                    error_stage="unhandled",
                    error_message=str(exc)
                )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(process_single_email, email) for email in emails]
        
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            with SessionLocal() as db:
                run_service = ProcessingRunService(db)
                run = run_service.get(run_id)
                if run:
                    if run.status == "queued":
                        run.status = "processing"
                    run_service.record_result(
                        run=run,
                        decision=result.decision,
                        status=result.status.value,
                    )
                    db.commit()
                    
    with SessionLocal() as db:
        run_service = ProcessingRunService(db)
        run = run_service.get(run_id)
        if run:
            run_service.complete(run)
            db.commit()


@app.post(
    "/ingest",
    response_model=IngestResponse,
)
def ingest(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    candidate_id = request.candidate_id.strip().lower()
    run_id = str(uuid.uuid4())

    run_service = ProcessingRunService(db)
    run = run_service.start(
        run_id=run_id,
        candidate_id=candidate_id,
    )
    db.commit()

    background_tasks.add_task(
        process_emails_background,
        run_id,
        candidate_id,
        request.emails
    )

    return IngestResponse(
        run_id=run.run_id,
        status=run.status,
        processed_count=run.processed_count,
        created_count=run.created_count,
        updated_count=run.updated_count,
        skipped_count=run.skipped_count,
        error_count=run.error_count,
    )


@app.get(
    "/ingest/{run_id}",
    response_model=IngestResponse,
)
def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
):
    run_service = ProcessingRunService(db)
    run = run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return IngestResponse(
        run_id=run.run_id,
        status=run.status,
        processed_count=run.processed_count,
        created_count=run.created_count,
        updated_count=run.updated_count,
        skipped_count=run.skipped_count,
        error_count=run.error_count,
    )


# =============================================================
# Dashboard API Endpoints
# =============================================================

@app.get("/api/tasks")
def get_tasks(
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return all processed emails with their routing decisions."""
    query = (
        db.query(
            EmailProcessing.email_id,
            EmailProcessing.run_id,
            EmailProcessing.decision,
            EmailProcessing.category,
            EmailProcessing.assignee_id,
            EmailProcessing.priority,
            EmailProcessing.due_date,
            EmailProcessing.deal_value_inr,
            EmailProcessing.company_name,
            EmailProcessing.confidence,
            EmailProcessing.reasoning,
            EmailProcessing.task_id,
            EmailProcessing.processing_status,
            EmailProcessing.error_stage,
            EmailProcessing.error_message,
            EmailProcessing.processed_at,
            Email.subject,
            Email.body,
            Email.from_name,
            Email.from_email,
            Email.received_at,
        )
        .outerjoin(Email, Email.email_id == EmailProcessing.email_id)
    )

    if run_id:
        query = query.filter(EmailProcessing.run_id == run_id)

    query = query.order_by(EmailProcessing.processed_at.desc().nullslast())
    rows = query.all()

    tasks = []
    for row in rows:
        tasks.append({
            "email_id": row.email_id,
            "run_id": row.run_id,
            "decision": row.decision,
            "category": row.category,
            "assignee_id": row.assignee_id,
            "priority": row.priority,
            "due_date": str(row.due_date) if row.due_date else None,
            "deal_value_inr": row.deal_value_inr,
            "company_name": row.company_name,
            "confidence": row.confidence,
            "reasoning": row.reasoning,
            "task_id": row.task_id,
            "processing_status": row.processing_status,
            "error_stage": row.error_stage,
            "error_message": row.error_message,
            "processed_at": str(row.processed_at) if row.processed_at else None,
            "subject": row.subject,
            "body": row.body,
            "from_name": row.from_name,
            "from_email": row.from_email,
            "received_at": str(row.received_at) if row.received_at else None,
        })

    return {"tasks": tasks, "total": len(tasks)}


@app.get("/api/stats")
def get_stats(
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return aggregate statistics for the dashboard summary cards."""
    query = db.query(
        func.count(EmailProcessing.email_id).label("total"),
        func.count(case(
            (EmailProcessing.decision == "create_task", 1),
        )).label("created"),
        func.count(case(
            (EmailProcessing.decision == "update_task", 1),
        )).label("updated"),
        func.count(case(
            (EmailProcessing.decision == "skip", 1),
        )).label("skipped"),
        func.count(case(
            (EmailProcessing.decision == "processing_error", 1),
        )).label("errors"),
    )

    if run_id:
        query = query.filter(EmailProcessing.run_id == run_id)

    row = query.one()

    # Category breakdown
    cat_query = (
        db.query(
            EmailProcessing.category,
            func.count(EmailProcessing.email_id),
        )
        .filter(EmailProcessing.decision.in_(["create_task", "update_task"]))
    )
    if run_id:
        cat_query = cat_query.filter(EmailProcessing.run_id == run_id)
    cat_query = cat_query.group_by(EmailProcessing.category)
    categories = {cat: count for cat, count in cat_query.all() if cat}

    # Priority breakdown
    pri_query = (
        db.query(
            EmailProcessing.priority,
            func.count(EmailProcessing.email_id),
        )
        .filter(EmailProcessing.decision.in_(["create_task", "update_task"]))
    )
    if run_id:
        pri_query = pri_query.filter(EmailProcessing.run_id == run_id)
    pri_query = pri_query.group_by(EmailProcessing.priority)
    priorities = {pri: count for pri, count in pri_query.all() if pri}

    # Assignee breakdown
    asg_query = (
        db.query(
            EmailProcessing.assignee_id,
            func.count(EmailProcessing.email_id),
        )
        .filter(EmailProcessing.decision.in_(["create_task", "update_task"]))
    )
    if run_id:
        asg_query = asg_query.filter(EmailProcessing.run_id == run_id)
    asg_query = asg_query.group_by(EmailProcessing.assignee_id)
    assignees = {asg: count for asg, count in asg_query.all() if asg}

    return {
        "total_processed": row.total,
        "created": row.created,
        "updated": row.updated,
        "skipped": row.skipped,
        "errors": row.errors,
        "categories": categories,
        "priorities": priorities,
        "assignees": assignees,
    }


class ChatRequest(BaseModel):
    question: str
    scope: str = "db"
    batch_emails: list[dict] | None = None


@app.post("/api/chat")
def chat(request: ChatRequest):
    """Conversational interface — ask questions about processed emails."""
    from app.services.chat_service import ChatService
    service = ChatService()
    return service.ask(
        question=request.question,
        scope=request.scope,
        batch_emails=request.batch_emails,
    )