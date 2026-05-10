from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.directory_access_store import (
    get_directory_access_settings,
    set_allowed_directories,
)
from services.runtime_settings_store import get_runtime_settings, set_runtime_settings
from services.shell_settings_store import get_shell_settings, set_shell_settings

router = APIRouter(prefix="/runtime-settings", tags=["runtime-settings"])


class RuntimeSettingsUpdateRequest(BaseModel):
    selected_embedding_model: str | None = None
    answer_style: str | None = Field(default=None, pattern="^(concise|normal)$")
    accessible_directories: list[str] | None = None
    shell_run_as_administrator: bool | None = None


async def _combined_runtime_settings() -> dict[str, Any]:
    runtime_settings = await get_runtime_settings()
    directory_settings = await get_directory_access_settings()
    shell_settings = await get_shell_settings()
    return {
        **runtime_settings,
        **directory_settings,
        **shell_settings,
    }


@router.get("")
async def read_runtime_settings() -> dict[str, Any]:
    return {
        "settings": await _combined_runtime_settings(),
    }


@router.patch("")
async def update_runtime_settings(request: RuntimeSettingsUpdateRequest) -> dict[str, Any]:
    try:
        await set_runtime_settings(
            selected_embedding_model=request.selected_embedding_model,
            answer_style=request.answer_style,
        )
        if request.accessible_directories is not None:
            await set_allowed_directories(request.accessible_directories)
        if request.shell_run_as_administrator is not None:
            await set_shell_settings(
                shell_run_as_administrator=request.shell_run_as_administrator,
            )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "settings": await _combined_runtime_settings(),
    }
