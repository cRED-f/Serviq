from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService


class ToolRisk(StrEnum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


@dataclass(slots=True)
class ToolExecutionContext:
    session_id: str
    lmstudio_client: LMStudioClient
    memory_service: MemoryService


@dataclass(slots=True)
class ToolResult:
    name: str
    ok: bool
    risk: ToolRisk
    output: Any = None
    error: str | None = None
    approval_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


ToolHandler = Callable[[dict[str, Any], ToolExecutionContext], Awaitable[ToolResult]]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    risk: ToolRisk
    parameters: dict[str, Any]
    handler: ToolHandler
    enabled: bool = True
