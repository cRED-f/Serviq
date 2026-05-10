from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.tool_settings_store import (
    ToolDisabledError,
    get_disabled_tool_ids,
    get_enabled_tool_ids,
    get_tool_setting,
    list_tool_settings,
    require_tool_enabled,
    set_tool_enabled,
)

router = APIRouter(prefix="/tool-settings", tags=["tool-settings"])


class ToolUpdateRequest(BaseModel):
    enabled: bool


class ToolCheckRequest(BaseModel):
    tool_id: str


@router.get("")
async def get_tools() -> dict[str, Any]:
    tools = await list_tool_settings()
    return {
        "tools": tools,
        "enabled_tool_ids": [tool["id"] for tool in tools if tool["enabled"]],
        "disabled_tool_ids": [tool["id"] for tool in tools if not tool["enabled"]],
    }


@router.get("/enabled")
async def get_enabled_tools() -> dict[str, Any]:
    return {
        "enabled_tool_ids": await get_enabled_tool_ids(),
        "disabled_tool_ids": await get_disabled_tool_ids(),
    }


@router.get("/{tool_id}")
async def get_tool(tool_id: str) -> dict[str, Any]:
    tool = await get_tool_setting(tool_id)

    if tool is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_id}")

    return {"tool": tool}


@router.patch("/{tool_id}")
async def update_tool(tool_id: str, request: ToolUpdateRequest) -> dict[str, Any]:
    try:
        tool = await set_tool_enabled(tool_id, request.enabled)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"tool": tool}


@router.post("/check")
async def check_tool_enabled(request: ToolCheckRequest) -> dict[str, Any]:
    try:
        await require_tool_enabled(request.tool_id)
    except ToolDisabledError as error:
        raise HTTPException(
            status_code=403,
            detail={
                "type": "tool_disabled",
                "message": str(error),
                "tool_id": request.tool_id,
            },
        ) from error

    return {
        "ok": True,
        "tool_id": request.tool_id,
    }
