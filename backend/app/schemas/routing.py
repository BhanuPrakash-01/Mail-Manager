from enum import Enum

from pydantic import BaseModel


class RoutingDecision(str, Enum):
    CREATE_TASK = "create_task"
    UPDATE_TASK = "update_task"
    SKIP = "skip"


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RoutingResult(BaseModel):
    decision: RoutingDecision

    category: str | None = None
    assignee_id: str | None = None
    priority: TaskPriority | None = None

    reason: str