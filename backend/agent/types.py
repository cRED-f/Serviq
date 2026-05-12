from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal


class TaskStatus(StrEnum):
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class OrchestratorAction(StrEnum):
    FINAL_ANSWER = "final_answer"
    TOOL_CALL = "tool_call"
    ASK_USER = "ask_user"


TaskStepType = Literal[
    "plan",
    "tool_call",
    "tool_result",
    "entity_update",
    "approval_pause",
    "final_answer",
    "error",
]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TaskStep:
    index: int
    type: TaskStepType
    title: str
    details: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CollectedEntity:
    type: str
    value: Any
    source: str
    confidence: float = 0.6
    created_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskStateSnapshot:
    task_id: str
    session_id: str
    goal: str
    status: TaskStatus
    current_step: int
    max_steps: int
    collected_entities: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)
    pending_confirmation: dict[str, Any] | None = None
    selected_options: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(slots=True)
class OrchestratorResult:
    session_id: str
    model: str
    route: str
    response: str
    status: TaskStatus
    steps: list[str]
    task_trace: list[dict[str, Any]] = field(default_factory=list)
    task_state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_agent_response(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model": self.model,
            "route": self.route,
            "response": self.response,
            "steps": self.steps,
            "task_trace": self.task_trace,
            "metadata": {
                **self.metadata,
                "task_status": self.status.value,
                "task_state": self.task_state,
            },
        }

    def to_execute_response(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "model": self.model,
            "route": self.route,
            "status": self.status.value,
            "response": self.response,
            "steps": self.steps,
            "task_trace": self.task_trace,
            "task_state": self.task_state,
            "metadata": self.metadata,
        }
