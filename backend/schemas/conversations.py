from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConversationSessionResponse(BaseModel):
    session_id: str
    message_count: int
    first_message_at: str | None = None
    last_message_at: str | None = None


class ListConversationSessionsResponse(BaseModel):
    sessions: list[ConversationSessionResponse]


class ConversationMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    model: str | None = None
    route: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ListConversationMessagesResponse(BaseModel):
    messages: list[ConversationMessageResponse]


class SearchConversationsRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)


class SearchConversationsResponse(BaseModel):
    messages: list[ConversationMessageResponse]
