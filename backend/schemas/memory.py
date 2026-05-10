from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SaveMemoryRequest(BaseModel):
    kind: str = Field(default="note")
    title: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embed: bool = True
    confidence: float | None = None
    supersedes_id: str | None = None


class SearchMemoryRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


class EmbeddingDebugRequest(BaseModel):
    text: str = Field(min_length=1)


class ArchiveMemoryRequest(BaseModel):
    reason: str = "Archived by user request."


class MemoryItemResponse(BaseModel):
    id: str
    kind: str
    title: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    lifecycle: str = "active"
    confidence: float | None = None
    supersedes_id: str | None = None


class SaveMemoryResponse(BaseModel):
    item: MemoryItemResponse
    vector_status: dict[str, Any] | None = None


class SearchMemoryResponse(BaseModel):
    query: str
    mode: str
    items: list[dict[str, Any]]
    semantic_count: int
    keyword_count: int
    error: str | None = None
    embedding_model: str
    qdrant_collection: str
