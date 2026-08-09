"""
In-memory mock of the shared Task API.

Used when TASK_API_BASE_URL is not a real HTTP endpoint.
Implements the same interface as TaskAPIClient so the rest of
the pipeline doesn't need to know whether it's real or mock.
"""

import threading
import uuid
from datetime import datetime, timezone


class MockTaskAPIClient:
    """Thread-safe in-memory Task API mock."""

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get_users(self) -> list[dict]:
        return [
            {"user_id": "u_aarti", "name": "Aarti Menon", "department": "Sales — Enterprise"},
            {"user_id": "u_rohit", "name": "Rohit Sharma", "department": "Sales — SMB"},
            {"user_id": "u_meera", "name": "Meera Iyer", "department": "Marketing"},
            {"user_id": "u_karan", "name": "Karan Doshi", "department": "Alliances"},
            {"user_id": "u_divya", "name": "Divya Rao", "department": "Finance"},
            {"user_id": "u_triage", "name": "Triage Queue", "department": "Operations"},
        ]

    def get_tasks(
        self,
        candidate_id: str,
        limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            tasks = [
                t for t in self._tasks.values()
                if t.get("candidate_id") == candidate_id
            ]
            return tasks[:limit]

    def create_task(self, payload: dict) -> dict:
        task_id = f"tsk_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        task = {
            **payload,
            "task_id": task_id,
            "created_at": now,
            "updated_at": now,
        }

        with self._lock:
            self._tasks[task_id] = task

        # Return the same shape as the real API
        return {
            "task_id": task_id,
            "candidate_id": payload.get("candidate_id"),
            "source_email_id": payload.get("source_email_id"),
            "created_at": now,
        }

    def update_task(self, task_id: str, payload: dict) -> dict:
        with self._lock:
            if task_id not in self._tasks:
                # If we don't have the task in mock, create a stub
                self._tasks[task_id] = {"task_id": task_id}

            task = self._tasks[task_id]
            task.update(payload)
            task["updated_at"] = datetime.now(timezone.utc).isoformat()

            return dict(task)

    def delete_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)
