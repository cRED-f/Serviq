from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDefinitionResponse(BaseModel):
    name: str
    description: str
    risk: str
    parameters: dict[str, Any]
    enabled: bool


class ListToolsResponse(BaseModel):
    tools: list[ToolDefinitionResponse]


class RunToolRequest(BaseModel):
    name: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    session_id: str = "manual-tool-session"


class RunToolResponse(BaseModel):
    name: str
    ok: bool
    risk: str
    output: Any = None
    error: str | None = None
    approval_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolLogResponse(BaseModel):
    logs: list[dict[str, Any]]
