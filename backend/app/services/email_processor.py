from datetime import datetime, timezone

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
                cleaned_email
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
                extraction,
                received_at=email.received_at,
            )

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
        if routing.decision.value == "skip":
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
        existing_task_id = self.thread_service.find_existing_task(
            thread_id=email.thread_id,
            candidate_id=candidate_id,
        )

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

                task_id = task_response.get("id")

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

        email_record = Email(
            email_id=email.email_id,
            thread_id=email.thread_id,
            candidate_id=candidate_id,
            received_at=email.received_at,
            from_name=email.from_name,
            from_email=email.from_email,
            subject=email.subject,
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

        self.db.add(processing)
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
                routing.category.value
                if routing.category is not None
                else None
            ),
            assignee_id=routing.assignee_id,
            priority=(
                routing.priority.value
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

        self.db.add(processing)
        self.db.flush()

        return processing

    def _build_task_payload(
        self,
        email: EmailInput,
        extraction,
        routing,
        candidate_id: str,
    ) -> dict:

        return {
            "candidate_id": candidate_id,
            "source_email_id": email.email_id,
            "thread_id": email.thread_id,
            "title": email.subject,
            "description": email.body,
            "assignee_id": routing.assignee_id,
            "category": (
                routing.category.value
                if routing.category is not None
                else None
            ),
            "priority": (
                routing.priority.value
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