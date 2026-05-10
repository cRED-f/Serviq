from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


AgentRoute = Literal["chat", "coding", "planning", "unknown"]


class ServiqAgentState(TypedDict, total=False):
    """Shared state passed through the Serviq LangGraph workflow."""

    session_id: str
    model: str
    user_message: str
    messages: list[dict[str, str]]

    route: AgentRoute
    response: str

    steps: list[str]
    metadata: dict[str, Any]
    error: str | None
