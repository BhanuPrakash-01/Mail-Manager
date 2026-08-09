import httpx

from app.config import settings


class TaskAPIError(Exception):
    """Raised when the Task API request fails."""


class TaskAPIClient:

    def __init__(self):
        self.base_url = settings.task_api_base_url.rstrip("/")

        self.timeout = httpx.Timeout(
            settings.task_api_timeout_seconds
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    def get_users(self) -> list[dict]:
        try:
            response = httpx.get(
                f"{self.base_url}/users",
                headers=self._headers(),
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as exc:
            raise TaskAPIError(
                f"Failed to fetch users: {exc}"
            ) from exc

    def get_tasks(
        self,
        candidate_id: str,
        limit: int = 100,
    ) -> list[dict]:
        try:
            response = httpx.get(
                f"{self.base_url}/tasks",
                params={
                    "candidate_id": candidate_id,
                    "limit": limit,
                },
                headers=self._headers(),
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as exc:
            raise TaskAPIError(
                f"Failed to fetch tasks: {exc}"
            ) from exc

    def create_task(
        self,
        payload: dict,
    ) -> dict:
        try:
            response = httpx.post(
                f"{self.base_url}/tasks",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as exc:
            raise TaskAPIError(
                f"Failed to create task: {exc}"
            ) from exc

    def update_task(
        self,
        task_id: str,
        payload: dict,
    ) -> dict:
        try:
            response = httpx.patch(
                f"{self.base_url}/tasks/{task_id}",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )

            response.raise_for_status()

            return response.json()

        except httpx.HTTPError as exc:
            raise TaskAPIError(
                f"Failed to update task {task_id}: {exc}"
            ) from exc


def get_task_api_client():
    """
    Factory: returns MockTaskAPIClient when the Task API URL
    is a placeholder, otherwise returns the real HTTP client.
    """
    from app.services.mock_task_api import MockTaskAPIClient

    url = settings.task_api_base_url.strip()
    placeholder_values = {
        "", "your-task-api-url", "mock", "placeholder",
        "http://localhost:0", "none",
    }

    if url.lower() in placeholder_values:
        print("[TaskAPI] Using MOCK Task API (in-memory)")
        return MockTaskAPIClient()

    print(f"[TaskAPI] Using REAL Task API at {url}")
    return TaskAPIClient()