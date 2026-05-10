from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings, get_settings
from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService
from schemas.memory import (
    ArchiveMemoryRequest,
    EmbeddingDebugRequest,
    SaveMemoryRequest,
    SaveMemoryResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
)

router = APIRouter(prefix="/memory", tags=["memory"])


def get_lmstudio_client(settings: Settings = Depends(get_settings)) -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )


def get_memory_service(client: LMStudioClient = Depends(get_lmstudio_client)) -> MemoryService:
    return MemoryService(lmstudio_client=client)


@router.get("/health")
async def memory_health(service: MemoryService = Depends(get_memory_service)) -> dict:
    return await service.health()


@router.get("/items")
async def list_memory(limit: int = 50, kind: str | None = None, lifecycle: str | None = "active") -> dict:
    service = MemoryService()
    return {
        "items": service.list_memory(limit=limit, kind=kind, lifecycle=lifecycle),
    }


@router.get("/decisions")
async def list_memory_decisions(session_id: str | None = None, limit: int = 50) -> dict:
    service = MemoryService()
    return {
        "decisions": service.list_memory_decisions(session_id=session_id, limit=limit),
    }


@router.post("/save", response_model=SaveMemoryResponse)
async def save_memory(
    request: SaveMemoryRequest,
    service: MemoryService = Depends(get_memory_service),
) -> dict:
    return await service.save_memory(
        kind=request.kind,
        title=request.title,
        content=request.content,
        source=request.source,
        tags=request.tags,
        metadata=request.metadata,
        embed=request.embed,
        confidence=request.confidence,
        supersedes_id=request.supersedes_id,
    )


@router.post("/search", response_model=SearchMemoryResponse)
async def search_memory(
    request: SearchMemoryRequest,
    service: MemoryService = Depends(get_memory_service),
) -> dict:
    return await service.search_memory(query=request.query, limit=request.limit)


@router.post("/{memory_id}/archive")
async def archive_memory(memory_id: str, request: ArchiveMemoryRequest) -> dict:
    service = MemoryService()
    item = service.sqlite_store.update_memory_lifecycle(
        memory_id=memory_id,
        lifecycle="archived",
        metadata_patch={"archive_reason": request.reason},
    )

    if not item:
        raise HTTPException(status_code=404, detail="Memory not found.")

    return {
        "item": service.memory_item_to_dict(item),
    }


@router.post("/debug/embedding")
async def debug_embedding(
    request: EmbeddingDebugRequest,
    service: MemoryService = Depends(get_memory_service),
) -> dict:
    embedding = await service.create_embedding(request.text)
    return {
        "embedding_model": service.lmstudio_client.base_url,
        "dimensions": len(embedding),
        "preview": embedding[:12],
    }
