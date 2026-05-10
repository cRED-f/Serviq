from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.memory_center_store import (
    archive_memory_item,
    create_memory_item,
    delete_memory_item,
    get_memory_item,
    get_memory_stats,
    list_memory_items,
    restore_memory_item,
    search_memory_items,
    update_memory_item,
)

router = APIRouter(prefix="/memory-center", tags=["memory-center"])


class MemoryCreateRequest(BaseModel):
    title: str | None = None
    content: str
    category: str = "general"
    importance: str = Field(default="medium", pattern="^(low|medium|high)$")
    source: str = "manual"


class MemoryUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    importance: str | None = Field(default=None, pattern="^(low|medium|high)$")
    status: str | None = Field(default=None, pattern="^(active|archived|deleted)$")


class MemorySearchRequest(BaseModel):
    query: str
    include_archived: bool = False
    limit: int = 20


@router.get("")
async def list_memories(
    status: str = Query(default="active", pattern="^(active|archived|deleted)$"),
    query: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    return {
        "memories": await list_memory_items(status=status, query=query, limit=limit),
        "stats": await get_memory_stats(),
    }


@router.get("/stats")
async def memory_stats() -> dict[str, Any]:
    return {"stats": await get_memory_stats()}


@router.post("")
async def create_memory(request: MemoryCreateRequest) -> dict[str, Any]:
    try:
        memory = await create_memory_item(
            title=request.title,
            content=request.content,
            category=request.category,
            importance=request.importance,
            source=request.source,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"memory": memory}


@router.post("/search")
async def search_memories(request: MemorySearchRequest) -> dict[str, Any]:
    return {
        "memories": await search_memory_items(
            query=request.query,
            include_archived=request.include_archived,
            limit=request.limit,
        )
    }


@router.get("/{memory_id}")
async def get_memory(memory_id: str) -> dict[str, Any]:
    memory = await get_memory_item(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Memory item not found: {memory_id}")
    return {"memory": memory}


@router.patch("/{memory_id}")
async def update_memory(memory_id: str, request: MemoryUpdateRequest) -> dict[str, Any]:
    try:
        memory = await update_memory_item(
            memory_id,
            title=request.title,
            content=request.content,
            category=request.category,
            importance=request.importance,
            status=request.status,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"memory": memory}


@router.post("/{memory_id}/archive")
async def archive_memory(memory_id: str) -> dict[str, Any]:
    try:
        return {"memory": await archive_memory_item(memory_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/{memory_id}/restore")
async def restore_memory(memory_id: str) -> dict[str, Any]:
    try:
        return {"memory": await restore_memory_item(memory_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "memory": await delete_memory_item(memory_id)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
