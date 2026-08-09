
from unittest.mock import Mock

from app.schemas.email import EmailInput
from app.schemas.processing import ProcessingStatus
from app.services.email_processor import EmailProcessor

from app.schemas.processing import ProcessingStatus


def build_processor():
    db = Mock()

    # By default, tests should represent a new thread.
    db.execute.return_value.scalar_one_or_none.return_value = None

    preprocessor = Mock()
    gemini_service = Mock()
    rule_engine = Mock()
    task_api = Mock()

    processor = EmailProcessor(
        db=db,
        preprocessor=preprocessor,
        gemini_service=gemini_service,
        rule_engine=rule_engine,
        task_api=task_api,
    )

    return (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    )


def build_email(
    email_id="em_001",
    thread_id="thread_001",
):
    return EmailInput(
        email_id=email_id,
        thread_id=thread_id,
        message_index=0,
        from_name="John",
        from_email="john@example.com",
        to="sales@example.com",
        cc=[],
        subject="Need a demo",
        body="I would like a product demo.",
        received_at="2026-08-09T10:00:00Z",
    )


def configure_create_task_flow(
    preprocessor,
    gemini_service,
    rule_engine,
):
    cleaned_email = Mock()

    extraction = Mock()
    extraction.due_date = None
    extraction.deal_value_inr = 2_500_000
    extraction.company_name = "Meridian Steel"
    extraction.confidence = 0.91

    routing = Mock()
    routing.decision.value = "create_task"
    routing.category.value = "enterprise_rfp"
    routing.assignee_id = "u_aarti"
    routing.priority.value = "high"
    routing.reason = "Enterprise RFP"

    preprocessor.preprocess.return_value = cleaned_email
    gemini_service.extract.return_value = extraction
    rule_engine.route.return_value = routing

    return extraction, routing


def test_duplicate_email_is_skipped():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=True
    )

    email = build_email()

    result = processor.process(
        email=email,
        candidate_id="Candidate@Example.COM",
        run_id="run_001",
    )

    assert result.email_id == "em_001"
    assert result.decision == "skip"
    assert result.status == ProcessingStatus.COMPLETED
    assert result.task_id is None

    db.add.assert_not_called()
    db.flush.assert_not_called()

    preprocessor.preprocess.assert_not_called()
    gemini_service.extract.assert_not_called()
    rule_engine.route.assert_not_called()
    task_api.create_task.assert_not_called()
    task_api.update_task.assert_not_called()


def test_new_email_is_saved():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    email = build_email(
        email_id="em_002",
        thread_id="thread_002",
    )

    try:
        processor.process(
            email=email,
            candidate_id=" Candidate@Example.COM ",
            run_id="run_001",
        )
    except Exception:
        pass

    assert db.add.call_count >= 1

    saved_email = db.add.call_args_list[0].args[0]

    assert saved_email.email_id == "em_002"
    assert saved_email.thread_id == "thread_002"
    assert saved_email.candidate_id == "candidate@example.com"
    assert saved_email.from_email == "john@example.com"
    assert saved_email.subject == "Need a demo"


def test_new_email_is_preprocessed_and_sent_to_gemini():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    cleaned_email = Mock()
    extraction = Mock()

    preprocessor.preprocess.return_value = cleaned_email
    gemini_service.extract.return_value = extraction

    email = build_email(
        email_id="em_003",
        thread_id="thread_003",
    )

    try:
        processor.process(
            email=email,
            candidate_id="candidate@example.com",
            run_id="run_001",
        )
    except Exception:
        pass

    preprocessor.preprocess.assert_called_once_with(email)

    gemini_service.extract.assert_called_once_with(
        cleaned_email
    )


def test_extracted_email_is_sent_to_rule_engine():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    cleaned_email = Mock()
    extraction = Mock()
    routing = Mock()

    preprocessor.preprocess.return_value = cleaned_email
    gemini_service.extract.return_value = extraction
    rule_engine.route.return_value = routing

    email = build_email(
        email_id="em_004",
        thread_id="thread_004",
    )

    try:
        processor.process(
            email=email,
            candidate_id="candidate@example.com",
            run_id="run_001",
        )
    except Exception:
        pass

    rule_engine.route.assert_called_once_with(
        extraction,
        received_at=email.received_at,
    )


def test_routing_decision_is_persisted():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    extraction, routing = configure_create_task_flow(
        preprocessor,
        gemini_service,
        rule_engine,
    )

    email = build_email(
        email_id="em_005",
        thread_id="thread_005",
    )

    try:
        processor.process(
            email=email,
            candidate_id="candidate@example.com",
            run_id="run_001",
        )
    except Exception:
        pass

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.email_id == "em_005"
    assert saved_processing.run_id == "run_001"
    assert saved_processing.decision == "create_task"
    assert saved_processing.category == "enterprise_rfp"
    assert saved_processing.assignee_id == "u_aarti"
    assert saved_processing.priority == "high"
    assert saved_processing.deal_value_inr == 2_500_000
    assert saved_processing.company_name == "Meridian Steel"
    assert saved_processing.confidence == 0.91


def test_skip_decision_does_not_call_task_api():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    cleaned_email = Mock()

    extraction = Mock()
    extraction.due_date = None
    extraction.deal_value_inr = None
    extraction.company_name = None
    extraction.confidence = 0.97

    routing = Mock()
    routing.decision.value = "skip"
    routing.category = None
    routing.assignee_id = None
    routing.priority = None
    routing.reason = "Outbound/vendor email"

    preprocessor.preprocess.return_value = cleaned_email
    gemini_service.extract.return_value = extraction
    rule_engine.route.return_value = routing

    email = build_email(
        email_id="em_006",
        thread_id="thread_006",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    assert result.email_id == "em_006"
    assert result.decision == "skip"
    assert result.status == ProcessingStatus.COMPLETED
    assert result.task_id is None

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.decision == "skip"
    assert saved_processing.processing_status == "completed"

    task_api.create_task.assert_not_called()
    task_api.update_task.assert_not_called()


def test_new_thread_creates_task():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    processor.thread_service.find_existing_task = Mock(
        return_value=None
    )

    extraction, routing = configure_create_task_flow(
        preprocessor,
        gemini_service,
        rule_engine,
    )

    task_api.create_task.return_value = {
        "id": "task_123"
    }

    email = build_email(
        email_id="em_007",
        thread_id="thread_007",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    task_api.create_task.assert_called_once()
    task_api.update_task.assert_not_called()

    payload = task_api.create_task.call_args.args[0]

    assert payload["candidate_id"] == "candidate@example.com"
    assert payload["source_email_id"] == "em_007"
    assert payload["thread_id"] == "thread_007"
    assert payload["title"] == "Need a demo"
    assert payload["assignee_id"] == "u_aarti"

    assert result.status == ProcessingStatus.COMPLETED
    assert result.task_id == "task_123"

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.task_id == "task_123"
    assert saved_processing.processing_status == "completed"


def test_existing_thread_updates_existing_task():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    processor.thread_service.find_existing_task = Mock(
        return_value="task_existing"
    )

    configure_create_task_flow(
        preprocessor,
        gemini_service,
        rule_engine,
    )

    task_api.update_task.return_value = {
        "id": "task_existing"
    }

    email = build_email(
        email_id="em_008",
        thread_id="thread_008",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    task_api.update_task.assert_called_once()
    task_api.create_task.assert_not_called()

    task_id = task_api.update_task.call_args.args[0]

    assert task_id == "task_existing"

    assert result.status == ProcessingStatus.COMPLETED
    assert result.task_id == "task_existing"


def test_task_api_failure_is_recorded():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    processor.thread_service.find_existing_task = Mock(
        return_value=None
    )

    configure_create_task_flow(
        preprocessor,
        gemini_service,
        rule_engine,
    )

    from app.services.task_api import TaskAPIError

    task_api.create_task.side_effect = TaskAPIError(
        "Task API unavailable"
    )

    email = build_email(
        email_id="em_009",
        thread_id="thread_009",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    assert result.status == ProcessingStatus.TASK_API_ERROR
    assert result.error_stage == "task_api"
    assert result.error_message == "Task API unavailable"

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.processing_status == "task_api_error"
    assert saved_processing.error_stage == "task_api"
    assert saved_processing.error_message == "Task API unavailable"




def test_preprocessor_failure_is_recorded():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    preprocessor.preprocess.side_effect = RuntimeError(
        "preprocessor failed"
    )

    email = build_email(
        email_id="em_error_001",
        thread_id="thread_error_001",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    assert result.status == ProcessingStatus.PROCESSING_ERROR
    assert result.decision == "processing_error"
    assert result.error_stage == "preprocessor"
    assert result.error_message == "preprocessor failed"

    assert db.add.call_count == 2

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.email_id == "em_error_001"
    assert saved_processing.run_id == "run_001"
    assert saved_processing.processing_status == "processing_error"
    assert saved_processing.error_stage == "preprocessor"
    assert saved_processing.error_message == "preprocessor failed"
    assert saved_processing.processed_at is not None


def test_rule_engine_failure_is_recorded():
    (
        processor,
        db,
        preprocessor,
        gemini_service,
        rule_engine,
        task_api,
    ) = build_processor()

    processor.idempotency_service.email_already_processed = Mock(
        return_value=False
    )

    preprocessor.preprocess.return_value = "clean email"

    extraction = Mock()
    gemini_service.extract.return_value = extraction

    rule_engine.route.side_effect = RuntimeError(
        "rule engine failed"
    )

    email = build_email(
        email_id="em_error_003",
        thread_id="thread_error_003",
    )

    result = processor.process(
        email=email,
        candidate_id="candidate@example.com",
        run_id="run_001",
    )

    assert result.status == ProcessingStatus.PROCESSING_ERROR
    assert result.decision == "processing_error"
    assert result.error_stage == "rule_engine"
    assert result.error_message == "rule engine failed"

    assert db.add.call_count == 2

    saved_processing = db.add.call_args_list[1].args[0]

    assert saved_processing.email_id == "em_error_003"
    assert saved_processing.run_id == "run_001"
    assert saved_processing.processing_status == "processing_error"
    assert saved_processing.error_stage == "rule_engine"
    assert saved_processing.error_message == "rule engine failed"
    assert saved_processing.processed_at is not None

    task_api.create_task.assert_not_called()
    task_api.update_task.assert_not_called()

