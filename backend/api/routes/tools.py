from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings, get_settings
from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService
from schemas.tools import ListToolsResponse, RunToolRequest, RunToolResponse, ToolLogResponse
from tools.base import ToolExecutionContext
from tools.execution_log import ToolExecutionLogStore
from tools.registry import ToolNotFoundError, ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


def get_lmstudio_client(settings: Settings = Depends(get_settings)) -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )


def get_tool_registry() -> ToolRegistry:
    return ToolRegistry()


@router.get("", response_model=ListToolsResponse)
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)) -> dict:
    return {
        "tools": registry.list_tools(),
    }


@router.get("/logs", response_model=ToolLogResponse)
async def list_tool_logs(limit: int = 50, session_id: str | None = None) -> dict:
    return {
        "logs": ToolExecutionLogStore().list_logs(limit=limit, session_id=session_id),
    }


@router.post("/run", response_model=RunToolResponse)
async def run_tool(
    request: RunToolRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> RunToolResponse:
    memory_service = MemoryService(lmstudio_client=client)
    context = ToolExecutionContext(
        session_id=request.session_id,
        lmstudio_client=client,
        memory_service=memory_service,
    )

    try:
        result = await registry.execute_tool(
            name=request.name,
            args=request.args,
            context=context,
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RunToolResponse(
        name=result.name,
        ok=result.ok,
        risk=result.risk.value,
        output=result.output,
        error=result.error,
        approval_required=result.approval_required,
        metadata=result.metadata,
    )
