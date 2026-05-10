from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1)
    model: str | None = None
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    history: list[AgentMessage] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    session_id: str
    model: str
    route: str
    response: str
    steps: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentHealthResponse(BaseModel):
    status: Literal["ok"]
    runtime: str
    stage: str
    graph_nodes: list[str]
