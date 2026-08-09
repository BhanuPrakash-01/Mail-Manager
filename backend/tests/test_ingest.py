from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.db.session import get_db
from app.models.email import Email
from app.models.email_processing import EmailProcessing
from app.models.processing_run import ProcessingRun
from app.models.thread import Thread


TEST_CANDIDATE = "integration-test@example.com"


def cleanup_database():
    db = SessionLocal()

    try:
        # Delete child records first because of foreign keys.
        db.execute(
            delete(EmailProcessing).where(
                EmailProcessing.email_id.in_(
                    db.query(Email.email_id)
                    .filter(
                        Email.candidate_id == TEST_CANDIDATE
                    )
                )
            )
        )

        db.execute(
            delete(Thread).where(
                Thread.candidate_id == TEST_CANDIDATE
            )
        )

        db.execute(
            delete(Email).where(
                Email.candidate_id == TEST_CANDIDATE
            )
        )

        db.execute(
            delete(ProcessingRun).where(
                ProcessingRun.candidate_id == TEST_CANDIDATE
            )
        )

        db.commit()

    finally:
        db.close()


def override_get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def build_routing(
    decision="create_task",
):
    routing = Mock()

    routing.decision = decision
    routing.category = "product"
    routing.assignee_id = "u_rohit"
    routing.priority = "medium"
    routing.reason = "Product enquiry"

    return routing


def build_extraction():
    extraction = Mock()

    extraction.due_date = None
    extraction.deal_value_inr = 500000
    extraction.company_name = "Integration Test Corp"
    extraction.confidence = 0.95

    return extraction


def build_email(
    email_id,
    thread_id,
    subject="Need a product demo",
):
    return {
        "email_id": email_id,
        "thread_id": thread_id,
        "message_index": 0,
        "from_name": "John",
        "from_email": "john@example.com",
        "to": "sales@example.com",
        "cc": [],
        "subject": subject,
        "body": "We would like a product demo.",
        "received_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "attachments": [],
        "is_reply": False,
    }


def test_ingest_creates_task_and_persists_data(
    monkeypatch,
):
    cleanup_database()

    mock_gemini = Mock()
    mock_gemini.extract.return_value = build_extraction()

    mock_rule_engine = Mock()
    mock_rule_engine.route.return_value = build_routing(
        "create_task"
    )

    mock_task_api = Mock()
    mock_task_api.create_task.return_value = {
        "task_id": "task_integration_001"
    }

    monkeypatch.setattr(
        "app.main.GeminiService",
        lambda: mock_gemini,
    )

    monkeypatch.setattr(
        "app.main.RuleEngine",
        lambda: mock_rule_engine,
    )

    monkeypatch.setattr(
        "app.main.get_task_api_client",
        lambda: mock_task_api,
    )

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    try:
        response = client.post(
            "/ingest",
            json={
                "candidate_id": TEST_CANDIDATE,
                "emails": [
                    build_email(
                        "integration_email_001",
                        "integration_thread_001",
                    )
                ],
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "queued"
        run_id = data["run_id"]

        get_response = client.get(f"/ingest/{run_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()

        assert get_data["status"] == "completed"
        assert get_data["processed_count"] == 1
        assert get_data["created_count"] == 1
        assert get_data["updated_count"] == 0
        assert get_data["skipped_count"] == 0
        assert get_data["error_count"] == 0

        mock_task_api.create_task.assert_called_once()

        db = SessionLocal()

        try:
            email = db.get(
                Email,
                "integration_email_001",
            )

            assert email is not None
            assert email.thread_id == "integration_thread_001"
            assert email.candidate_id == TEST_CANDIDATE

            processing = db.get(
                EmailProcessing,
                "integration_email_001",
            )

            assert processing is not None
            assert processing.decision == "create_task"
            assert processing.task_id == "task_integration_001"
            assert processing.processing_status == "completed"

            thread = db.get(
                Thread,
                "integration_thread_001",
            )

            assert thread is not None
            assert thread.current_task_id == "task_integration_001"
            assert thread.last_email_id == "integration_email_001"

            run = (
                db.query(ProcessingRun)
                .filter(
                    ProcessingRun.run_id
                    == data["run_id"]
                )
                .one()
            )

            assert run.status == "completed"
            assert run.processed_count == 1
            assert run.created_count == 1
            assert run.updated_count == 0
            assert run.skipped_count == 0
            assert run.error_count == 0

        finally:
            db.close()

    finally:
        app.dependency_overrides.clear()
        cleanup_database()


def test_ingest_updates_existing_thread_task(
    monkeypatch,
):
    cleanup_database()

    mock_gemini = Mock()
    mock_gemini.extract.return_value = build_extraction()

    mock_rule_engine = Mock()
    mock_rule_engine.route.return_value = build_routing(
        "create_task"
    )

    mock_task_api = Mock()

    # First request creates the task.
    mock_task_api.create_task.return_value = {
        "task_id": "task_thread_001"
    }

    monkeypatch.setattr(
        "app.main.GeminiService",
        lambda: mock_gemini,
    )

    monkeypatch.setattr(
        "app.main.RuleEngine",
        lambda: mock_rule_engine,
    )

    monkeypatch.setattr(
        "app.main.get_task_api_client",
        lambda: mock_task_api,
    )

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    try:
        first_response = client.post(
            "/ingest",
            json={
                "candidate_id": TEST_CANDIDATE,
                "emails": [
                    build_email(
                        "thread_email_001",
                        "same_thread_001",
                    )
                ],
            },
        )

        assert first_response.status_code == 200

        # The second request represents a reply
        # in the same conversation.
        second_email = build_email(
            "thread_email_002",
            "same_thread_001",
            subject="Re: Need a product demo",
        )

        second_email["message_index"] = 1
        second_email["is_reply"] = True

        mock_task_api.update_task.return_value = {
            "id": "task_thread_001"
        }

        second_response = client.post(
            "/ingest",
            json={
                "candidate_id": TEST_CANDIDATE,
                "emails": [second_email],
            },
        )

        assert second_response.status_code == 200

        data = second_response.json()

        assert data["status"] == "queued"
        run_id = data["run_id"]

        get_response = client.get(f"/ingest/{run_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()

        assert get_data["status"] == "completed"
        assert get_data["processed_count"] == 1
        assert get_data["created_count"] == 0
        assert get_data["updated_count"] == 1
        assert get_data["skipped_count"] == 0
        assert get_data["error_count"] == 0

        mock_task_api.update_task.assert_called_once()

        update_args = (
            mock_task_api
            .update_task
            .call_args
            .args
        )

        assert update_args[0] == "task_thread_001"

        db = SessionLocal()

        try:
            thread = db.get(
                Thread,
                "same_thread_001",
            )

            assert thread is not None
            assert (
                thread.current_task_id
                == "task_thread_001"
            )
            assert (
                thread.last_email_id
                == "thread_email_002"
            )

            processing = db.get(
                EmailProcessing,
                "thread_email_002",
            )

            assert processing is not None
            assert processing.decision == "update_task"
            assert (
                processing.task_id
                == "task_thread_001"
            )

        finally:
            db.close()

    finally:
        app.dependency_overrides.clear()
        cleanup_database()


def test_ingest_skips_email_without_creating_task(
    monkeypatch,
):
    cleanup_database()

    mock_gemini = Mock()
    mock_gemini.extract.return_value = build_extraction()

    mock_rule_engine = Mock()
    mock_rule_engine.route.return_value = build_routing(
        "skip"
    )

    mock_task_api = Mock()

    monkeypatch.setattr(
        "app.main.GeminiService",
        lambda: mock_gemini,
    )

    monkeypatch.setattr(
        "app.main.RuleEngine",
        lambda: mock_rule_engine,
    )

    monkeypatch.setattr(
        "app.main.get_task_api_client",
        lambda: mock_task_api,
    )

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    try:
        response = client.post(
            "/ingest",
            json={
                "candidate_id": TEST_CANDIDATE,
                "emails": [
                    build_email(
                        "skip_email_001",
                        "skip_thread_001",
                    )
                ],
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "queued"
        run_id = data["run_id"]

        get_response = client.get(f"/ingest/{run_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()

        assert get_data["status"] == "completed"
        assert get_data["processed_count"] == 1
        assert get_data["created_count"] == 0
        assert get_data["updated_count"] == 0
        assert get_data["skipped_count"] == 1
        assert get_data["error_count"] == 0

        mock_task_api.create_task.assert_not_called()
        mock_task_api.update_task.assert_not_called()

        db = SessionLocal()

        try:
            processing = db.get(
                EmailProcessing,
                "skip_email_001",
            )

            assert processing is not None
            assert processing.decision == "skip"
            assert processing.processing_status == "completed"

            thread = db.get(
                Thread,
                "skip_thread_001",
            )

            assert thread is None

        finally:
            db.close()

    finally:
        app.dependency_overrides.clear()
        cleanup_database()