from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.config import Settings, get_settings
from llm.lmstudio_client import LMStudioAPIError, LMStudioClient, LMStudioConnectionError
from schemas.llm import (
    LMStudioChatRequest,
    LMStudioChatResponse,
    LMStudioEmbeddingRequest,
    LMStudioEmbeddingResponse,
    LMStudioHealthResponse,
)

router = APIRouter(prefix="/llm", tags=["llm"])


def get_lmstudio_client(settings: Settings = Depends(get_settings)) -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )


@router.get("/health", response_model=LMStudioHealthResponse)
async def lmstudio_health(
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> LMStudioHealthResponse:
    try:
        result = await client.health()
        return LMStudioHealthResponse(**result)
    except LMStudioConnectionError as exc:
        return LMStudioHealthResponse(
            status="offline",
            base_url=client.normalized_base_url,
            error=str(exc),
        )


@router.get("/models")
async def list_lmstudio_models(client: LMStudioClient = Depends(get_lmstudio_client)) -> dict:
    models = await client.list_models()
    return {
        "provider": "lmstudio",
        "base_url": client.normalized_base_url,
        "models": models,
    }


@router.post("/chat", response_model=LMStudioChatResponse)
async def lmstudio_chat(
    request: LMStudioChatRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> LMStudioChatResponse:
    payload = await client.chat_completion(
        model=request.model,
        messages=[message.model_dump() for message in request.messages],
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    return LMStudioChatResponse(
        model=request.model,
        content=content,
        raw=payload,
    )


@router.post("/chat/stream")
async def lmstudio_chat_stream(
    request: LMStudioChatRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        try:
            async for line in client.stream_chat_completion(
                model=request.model,
                messages=[message.model_dump() for message in request.messages],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"{line}\\n\\n"
        except (LMStudioAPIError, LMStudioConnectionError) as exc:
            error_payload = {
                "type": "error",
                "error": str(exc),
            }
            yield f"data: {json.dumps(error_payload)}\\n\\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/embeddings", response_model=LMStudioEmbeddingResponse)
async def lmstudio_embeddings(
    request: LMStudioEmbeddingRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> LMStudioEmbeddingResponse:
    payload = await client.embeddings(model=request.model, input_text=request.input)

    dimensions: int | None = None
    data = payload.get("data", [])
    if data and isinstance(data, list):
        first_embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
        if isinstance(first_embedding, list):
            dimensions = len(first_embedding)

    return LMStudioEmbeddingResponse(
        model=request.model,
        dimensions=dimensions,
        raw=payload,
    )
