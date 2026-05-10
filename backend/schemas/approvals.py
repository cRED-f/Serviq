from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from schemas.tools import RunToolResponse


class ApprovalRequestResponse(BaseModel):
    id: str
    session_id: str
    tool_name: str
    risk: str
    args: dict[str, Any]
    reason: str
    status: str
    result: Any = None
    error: str | None = None
    created_at: str
    decided_at: str | None = None
    executed_at: str | None = None


class ListApprovalsResponse(BaseModel):
    approvals: list[ApprovalRequestResponse]


class ApprovalDecisionResponse(BaseModel):
    approval: ApprovalRequestResponse
    tool_result: RunToolResponse | None = None
    assistant_response: str | None = None
    model: str | None = None


class RejectApprovalRequest(BaseModel):
    reason: str | None = Field(default=None)
