from unittest.mock import Mock

from app.services.idempotency import IdempotencyService


CANDIDATE_ID = "candidate@example.com"


def test_completed_email_is_detected():
    db = Mock()

    result = Mock()
    result.scalar_one_or_none.return_value = "em_001"

    db.execute.return_value = result

    service = IdempotencyService(db)

    assert service.email_already_processed(
        "em_001",
        CANDIDATE_ID,
    ) is True

    db.execute.assert_called_once()


def test_failed_email_is_not_considered_processed():
    db = Mock()

    result = Mock()
    result.scalar_one_or_none.return_value = None

    db.execute.return_value = result

    service = IdempotencyService(db)

    assert service.email_already_processed(
        "em_002",
        CANDIDATE_ID,
    ) is False

    db.execute.assert_called_once()


def test_unknown_email_is_not_processed():
    db = Mock()

    result = Mock()
    result.scalar_one_or_none.return_value = None

    db.execute.return_value = result

    service = IdempotencyService(db)

    assert service.email_already_processed(
        "does_not_exist",
        CANDIDATE_ID,
    ) is False

    db.execute.assert_called_once()
