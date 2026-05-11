from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.ui_conversation_store import (
    append_message,
    list_messages,
    list_sessions,
    soft_delete_assistant_pair,
    soft_delete_message,
    soft_delete_session,
    touch_session,
    upsert_session,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class SessionCreateRequest(BaseModel):
    id: str | None = None
    title: str = "New chat"
    preview: str = ""


class SessionTouchRequest(BaseModel):
    title: str | None = None
    preview: str | None = None


class MessageCreateRequest(BaseModel):
    id: str | None = None
    role: str = Field(pattern="^(user|assistant)$")
    content: str
    steps: list[str] | None = None
    task_trace: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


def _decode_json_field(value: str | None, default: Any) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _message_response(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "created_at": row["created_at"],
        "sort_index": row["sort_index"],
        "steps": _decode_json_field(row.get("steps_json"), []),
        "task_trace": _decode_json_field(row.get("task_trace_json"), []),
        "metadata": _decode_json_field(row.get("metadata_json"), {}),
    }


@router.get("/sessions")
async def get_sessions() -> dict[str, Any]:
    return {"sessions": await list_sessions()}


@router.post("/sessions")
async def create_session(request: SessionCreateRequest) -> dict[str, Any]:
    session_id = request.id or f"serviq-{uuid.uuid4()}"
    session = await upsert_session(
        session_id=session_id,
        title=request.title,
        preview=request.preview,
    )
    return {"session": session}


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, request: SessionTouchRequest) -> dict[str, Any]:
    await touch_session(
        session_id=session_id,
        title=request.title,
        preview=request.preview,
    )
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str) -> dict[str, Any]:
    rows = await list_messages(session_id)
    return {"messages": [_message_response(row) for row in rows]}


@router.post("/sessions/{session_id}/messages")
async def create_message(session_id: str, request: MessageCreateRequest) -> dict[str, Any]:
    try:
        row = await append_message(
            session_id=session_id,
            role=request.role,
            content=request.content,
            message_id=request.id,
            steps_json=json.dumps(request.steps or []),
            task_trace_json=json.dumps(request.task_trace or []),
            metadata_json=json.dumps(request.metadata or {}),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": _message_response(row)}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, Any]:
    await soft_delete_session(session_id)
    return {"ok": True}


@router.delete("/messages/{message_id}")
async def delete_message(message_id: str) -> dict[str, Any]:
    await soft_delete_message(message_id)
    return {"ok": True, "deleted": [message_id]}


@router.delete("/messages/{message_id}/pair")
async def delete_message_pair(message_id: str) -> dict[str, Any]:
    result = await soft_delete_assistant_pair(message_id)
    return {"ok": True, **result}
