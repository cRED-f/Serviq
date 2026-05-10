from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LMStudioHealthResponse(BaseModel):
    status: Literal["connected", "offline"]
    base_url: str
    model_count: int = 0
    models: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class LMStudioChatRequest(BaseModel):
    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)


class LMStudioChatResponse(BaseModel):
    model: str
    content: str
    raw: dict[str, Any]


class LMStudioEmbeddingRequest(BaseModel):
    model: str = Field(min_length=1)
    input: str | list[str]


class LMStudioEmbeddingResponse(BaseModel):
    model: str
    dimensions: int | None = None
    raw: dict[str, Any]
