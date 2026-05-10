from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.runtime_settings_store import get_runtime_settings, set_runtime_settings

router = APIRouter(prefix="/runtime-settings", tags=["runtime-settings"])


class RuntimeSettingsUpdateRequest(BaseModel):
    selected_embedding_model: str | None = None
    answer_style: str | None = Field(default=None, pattern="^(concise|normal)$")


@router.get("")
async def read_runtime_settings() -> dict[str, Any]:
    return {
        "settings": await get_runtime_settings(),
    }


@router.patch("")
async def update_runtime_settings(request: RuntimeSettingsUpdateRequest) -> dict[str, Any]:
    try:
        settings = await set_runtime_settings(
            selected_embedding_model=request.selected_embedding_model,
            answer_style=request.answer_style,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "settings": settings,
    }
