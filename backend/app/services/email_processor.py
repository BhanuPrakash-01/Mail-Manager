from datetime import datetime, timezone
from sqlalchemy import select

from sqlalchemy.orm import Session

from app.models.email import Email
from app.models.email_processing import EmailProcessing
from app.models.thread import Thread
from app.schemas.email import EmailInput
from app.schemas.processing import ProcessingResult, ProcessingStatus
from app.services.gemini_service import GeminiService
from app.services.idempotency import IdempotencyService
from app.services.preprocessor import EmailPreprocessor
from app.services.rule_engine import RuleEngine
from app.services.task_api import TaskAPIClient, TaskAPIError
from app.services.thread_service import ThreadService


class EmailProcessor:

    def __init__(
        self,
        db: Session,
        preprocessor: EmailPreprocessor,
        gemini_service: GeminiService,
        rule_engine: RuleEngine,
        task_api: TaskAPIClient,
    ):
        self.db = db
        self.preprocessor = preprocessor
        self.gemini_service = gemini_service
        self.rule_engine = rule_engine
        self.task_api = task_api

        self.idempotency_service = IdempotencyService(db)
        self.thread_service = ThreadService(db)

    def process(
        self,
        email: EmailInput,
        candidate_id: str,
        run_id: str,
    ) -> ProcessingResult:

        candidate_id = candidate_id.strip().lower()

        # 1. Idempotency check
        if self.idempotency_service.email_already_processed(
            email.email_id,
            candidate_id,
        ):
            return ProcessingResult(
                email_id=email.email_id,
                decision="skip",
                status=ProcessingStatus.COMPLETED,
            )

        # 2. Persist incoming email
        self._save_email(
            email=email,
            candidate_id=candidate_id,
        )

        # Commit early so the DB connection is not held open
        # during the potentially long Gemini API call.
        self.db.commit()

        # 3. Preprocess
        try:
            cleaned_email = self.preprocessor.preprocess(email)

        except Exception as exc:
            self._save_processing_error(
                email=email,
                run_id=run_id,
                error_stage="preprocessor",
                exc=exc,
            )

            return ProcessingResult(
                email_id=email.email_id,
                decision="processing_error",
                status=ProcessingStatus.PROCESSING_ERROR,
                error_stage="preprocessor",
                error_message=str(exc),
            )

        # 4. Gemini extraction
        try:
            extraction = self.gemini_service.extract(
                cleaned_email=cleaned_email,
                received_at=email.received_at,
            )

        except Exception as exc:
            self._save_processing_error(
                email=email,
                run_id=run_id,
                error_stage="gemini",
                exc=exc,
            )

            return ProcessingResult(
                email_id=email.email_id,
                decision="processing_error",
                status=ProcessingStatus.PROCESSING_ERROR,
                error_stage="gemini",
                error_message=str(exc),
            )

        # 5. Deterministic routing
        try:
            routing = self.rule_engine.route(
                extraction=extraction,
                received_at=email.received_at,
            )

            # GUARDRAIL: Never populate deal_value_inr for marketing or alliances
            if getattr(routing, 'category', None) in {"marketing", "alliances"}:
                extraction.deal_value_inr = None

        except Exception as exc:
            self._save_processing_error(
                email=email,
                run_id=run_id,
                error_stage="rule_engine",
                exc=exc,
            )

            return ProcessingResult(
                email_id=email.email_id,
                decision="processing_error",
                status=ProcessingStatus.PROCESSING_ERROR,
                error_stage="rule_engine",
                error_message=str(exc),
            )

        # 6. SKIP decision
        if getattr(routing.decision, 'value', routing.decision) == "skip":
            processing = self._save_processing_result(
                email=email,
                extraction=extraction,
                routing=routing,
                run_id=run_id,
                decision="skip",
                processing_status="completed",
            )

            processing.processed_at = datetime.now(timezone.utc)

            self.db.flush()

            return ProcessingResult(
                email_id=email.email_id,
                decision="skip",
                status=ProcessingStatus.COMPLETED,
            )

        # 7. Find existing task for this thread
        thread_record = self.db.execute(
            select(Thread).where(
                Thread.thread_id == email.thread_id,
                Thread.candidate_id == candidate_id,
                Thread.current_task_id.is_not(None),
            )
        ).scalar_one_or_none()

        existing_task_id = thread_record.current_task_id if thread_record else None

        # Fix for Update-Path Category/Field carryover
        if existing_task_id and thread_record.last_email_id:
            last_processing = self.db.get(EmailProcessing, thread_record.last_email_id)
            if last_processing:
                # If new category is triage, carry over old category & assignee
                if getattr(routing, 'category', None) == "triage":
                    routing.category = last_processing.category
                    routing.assignee_id = last_processing.assignee_id
                
                # Carry over null fields
                if extraction.company_name is None:
                    extraction.company_name = last_processing.company_name
                
                if extraction.deal_value_inr is None:
                    extraction.deal_value_inr = last_processing.deal_value_inr

        # 8. Decide whether this is CREATE or UPDATE
        if existing_task_id:
            decision = "update_task"
        else:
            decision = "create_task"

        # 9. Persist processing decision before Task API
        processing = self._save_processing_result(
            email=email,
            extraction=extraction,
            routing=routing,
            run_id=run_id,
            decision=decision,
            processing_status="processing",
        )

        # 10. Build Task API payload
        payload = self._build_task_payload(
            email=email,
            extraction=extraction,
            routing=routing,
            candidate_id=candidate_id,
        )

        try:
            # 11. Existing thread → PATCH
            if existing_task_id:
                self.task_api.update_task(
                    existing_task_id,
                    payload,
                )

                task_id = existing_task_id

            # 12. New thread → POST
            else:
                task_response = self.task_api.create_task(
                    payload,
                )

                task_id = task_response.get("task_id") or task_response.get("id")

                if not task_id:
                    raise TaskAPIError(
                        "Task API create response did not contain task id"
                    )

            # 13. Mark processing completed
            processing.task_id = task_id
            processing.processing_status = "completed"
            processing.processed_at = datetime.now(timezone.utc)

            # 14. Create/update local thread record
            self._save_thread(
                thread_id=email.thread_id,
                candidate_id=candidate_id,
                task_id=task_id,
                email_id=email.email_id,
            )

            self.db.flush()

            return ProcessingResult(
                email_id=email.email_id,
                decision=decision,
                status=ProcessingStatus.COMPLETED,
                task_id=task_id,
            )

        except TaskAPIError as exc:
            processing.processing_status = "task_api_error"
            processing.error_stage = "task_api"
            processing.error_message = str(exc)
            processing.processed_at = datetime.now(timezone.utc)

            self.db.flush()

            return ProcessingResult(
                email_id=email.email_id,
                decision=decision,
                status=ProcessingStatus.TASK_API_ERROR,
                error_stage="task_api",
                error_message=str(exc),
            )

    def _save_email(
        self,
        email: EmailInput,
        candidate_id: str,
    ) -> None:

        existing_email = self.db.get(Email, email.email_id)
        if existing_email:
            return

        email_record = Email(
            email_id=email.email_id,
            thread_id=email.thread_id,
            candidate_id=candidate_id,
            received_at=email.received_at,
            from_name=email.from_name,
            from_email=email.from_email,
            subject=email.subject,
            body=email.body,
            message_index=email.message_index,
            is_reply=email.message_index > 0,
        )

        self.db.add(email_record)
        self.db.flush()

    def _save_processing_error(
        self,
        email: EmailInput,
        run_id: str,
        error_stage: str,
        exc: Exception,
        decision: str = "processing_error",
        retry_count: int = 0,
    ) -> None:

        processing = EmailProcessing(
            email_id=email.email_id,
            run_id=run_id,
            decision=decision,
            processing_status="processing_error",
            error_stage=error_stage,
            error_message=str(exc),
            retry_count=retry_count,
            processed_at=datetime.now(timezone.utc),
        )

        self.db.merge(processing)
        self.db.flush()

    def _save_processing_result(
        self,
        email: EmailInput,
        extraction,
        routing,
        run_id: str,
        decision: str,
        processing_status: str,
    ) -> EmailProcessing:

        processing = EmailProcessing(
            email_id=email.email_id,
            run_id=run_id,
            decision=decision,
            category=(
                routing.category
                if routing.category is not None
                else None
            ),
            assignee_id=routing.assignee_id,
            priority=(
                getattr(routing.priority, 'value', routing.priority)
                if routing.priority is not None
                else None
            ),
            due_date=extraction.due_date,
            deal_value_inr=extraction.deal_value_inr,
            company_name=extraction.company_name,
            confidence=extraction.confidence,
            reasoning=routing.reason,
            processing_status=processing_status,
        )

        processing = self.db.merge(processing)
        self.db.flush()

        return processing

    def _build_task_payload(
        self,
        email: EmailInput,
        extraction,
        routing,
        candidate_id: str,
    ) -> dict:
        # Build a concise title from subject
        title = email.subject or "Untitled Email"

        # Build description from routing reason + extraction context
        desc_parts = []
        if routing.reason:
            desc_parts.append(routing.reason)
        if extraction.company_name:
            desc_parts.append(f"Company: {extraction.company_name}")
        if extraction.due_date:
            desc_parts.append(f"Due: {extraction.due_date.isoformat()}")
        if extraction.deal_value_inr:
            desc_parts.append(f"Deal value: ₹{extraction.deal_value_inr:,}")
        description = ". ".join(desc_parts) if desc_parts else None

        return {
            "candidate_id": candidate_id,
            "source_email_id": email.email_id,
            "thread_id": email.thread_id,
            "title": title,
            "description": description,
            "assignee_id": routing.assignee_id,
            "category": (
                getattr(routing.category, 'value', routing.category)
                if routing.category is not None
                else None
            ),
            "priority": (
                getattr(routing.priority, 'value', routing.priority)
                if routing.priority is not None
                else None
            ),
            "due_date": (
                extraction.due_date.isoformat()
                if extraction.due_date is not None
                else None
            ),
            "deal_value_inr": extraction.deal_value_inr,
            "company_name": extraction.company_name,
            "confidence": extraction.confidence,
        }

        # Omit None values so we don't overwrite existing valid data during PATCH updates
        return {k: v for k, v in payload.items() if v is not None}
    def _save_thread(
        self,
        thread_id: str,
        candidate_id: str,
        task_id: str,
        email_id: str,
    ) -> None:

        thread = self.db.get(Thread, thread_id)

        now = datetime.now(timezone.utc)

        if thread is None:
            thread = Thread(
                thread_id=thread_id,
                candidate_id=candidate_id,
                current_task_id=task_id,
                last_email_id=email_id,
                updated_at=now,
            )

            self.db.add(thread)

        else:
            thread.current_task_id = task_id
            thread.last_email_id = email_id
            thread.updated_at = now