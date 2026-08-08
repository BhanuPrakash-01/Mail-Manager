from unittest.mock import Mock, patch

from app.services.task_api import TaskAPIClient


def test_create_task():

    mock_response = Mock()

    mock_response.raise_for_status.return_value = None

    mock_response.json.return_value = {
        "id": "task_123"
    }

    with patch(
        "httpx.post",
        return_value=mock_response,
    ) as mock_post:

        client = TaskAPIClient()

        result = client.create_task(
            {
                "title": "Test task",
                "category": "enterprise_rfp",
            }
        )

    assert result["id"] == "task_123"

    mock_post.assert_called_once()