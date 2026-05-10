from __future__ import annotations

import json
import platform
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from core.config import Settings, get_settings
from llm.lmstudio_client import LMStudioClient
from memory.service import MemoryService
from schemas.approvals import ApprovalDecisionResponse, ListApprovalsResponse
from schemas.tools import RunToolResponse
from tools.approval_store import ApprovalNotFoundError, ApprovalStateError, ToolApprovalStore
from tools.base import ToolExecutionContext
from tools.registry import ToolRegistry

router = APIRouter(prefix="/approvals", tags=["approvals"])


def get_lmstudio_client(settings: Settings = Depends(get_settings)) -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )


def get_registry() -> ToolRegistry:
    return ToolRegistry()


async def resolve_default_model(client: LMStudioClient) -> str | None:
    try:
        models = await client.list_models()
    except Exception:  # noqa: BLE001 - approval execution should still return raw tool result.
        return None

    if not models:
        return None

    model_id = models[0].get("id")
    return model_id if isinstance(model_id, str) and model_id else None


def build_tool_result_summary(
    *,
    approval: dict[str, Any],
    tool_result: RunToolResponse,
) -> str:
    payload = {
        "approval": {
            "id": approval["id"],
            "tool_name": approval["tool_name"],
            "risk": approval["risk"],
            "args": approval["args"],
            "status": approval["status"],
        },
        "tool_result": tool_result.model_dump(),
    }

    return json.dumps(payload, indent=2, default=str)


async def create_assistant_response_from_tool_result(
    *,
    client: LMStudioClient,
    model: str,
    approval: dict[str, Any],
    tool_result: RunToolResponse,
) -> str:
    """Ask LM Studio to produce the final user-facing answer after approved tool execution."""

    tool_summary = build_tool_result_summary(approval=approval, tool_result=tool_result)
    os_name = platform.system() or "unknown"

    payload = await client.chat_completion(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Serviq, Fahim's local AI agent. "
                    "A previously requested tool has now been approved and executed. "
                    "Use only the actual tool result below. Do not invent output. "
                    "If the tool failed, explain the actual failure plainly. "
                    "Do not claim Python subprocess is broken just because a command was not found. "
                    "If a command is not recognized, say it is unavailable in the current shell/OS. "
                    "If it succeeded, summarize the real result and mention useful stdout/stderr/file path details. "
                    f"Current OS: {os_name}."
                ),
            },
            {
                "role": "user",
                "content": (
                    "The approved tool execution completed. "
                    "Give Fahim the final answer based on this actual result:\n\n"
                    f"{tool_summary}"
                ),
            },
        ],
    )

    content = (
        payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    return content or "The approved tool ran, but the model returned an empty final response."


@router.get("", response_model=ListApprovalsResponse)
async def list_approvals(status: str | None = "pending", limit: int = 50) -> dict:
    return {
        "approvals": ToolApprovalStore().list_requests(status=status, limit=limit),
    }


@router.post("/{approval_id}/approve", response_model=ApprovalDecisionResponse)
async def approve_request(
    approval_id: str,
    client: LMStudioClient = Depends(get_lmstudio_client),
    registry: ToolRegistry = Depends(get_registry),
) -> dict:
    try:
        approval = ToolApprovalStore().get_request(approval_id)
        if not approval:
            raise ApprovalNotFoundError(f"Approval request not found: {approval_id}")

        memory_service = MemoryService(lmstudio_client=client)
        context = ToolExecutionContext(
            session_id=approval["session_id"],
            lmstudio_client=client,
            memory_service=memory_service,
        )

        updated_approval, result = await registry.execute_approved_request(
            approval_id=approval_id,
            context=context,
        )

        tool_response = RunToolResponse(
            name=result.name,
            ok=result.ok,
            risk=result.risk.value,
            output=result.output,
            error=result.error,
            approval_required=result.approval_required,
            metadata=result.metadata,
        )

        model = await resolve_default_model(client)
        assistant_response: str | None = None

        if model:
            try:
                assistant_response = await create_assistant_response_from_tool_result(
                    client=client,
                    model=model,
                    approval=updated_approval,
                    tool_result=tool_response,
                )

                memory_service.sqlite_store.save_conversation_message(
                    session_id=updated_approval["session_id"],
                    role="assistant",
                    content=assistant_response,
                    model=model,
                    route="tool_approval_result",
                    metadata={
                        "approval_id": updated_approval["id"],
                        "tool_name": updated_approval["tool_name"],
                        "tool_ok": tool_response.ok,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                assistant_response = (
                    "The approved tool executed, but Serviq could not generate a model summary. "
                    f"Summary generation error: {type(exc).__name__}: {exc}"
                )

        return {
            "approval": updated_approval,
            "tool_result": tool_response.model_dump(),
            "assistant_response": assistant_response,
            "model": model,
        }

    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{approval_id}/reject", response_model=ApprovalDecisionResponse)
async def reject_request(approval_id: str, registry: ToolRegistry = Depends(get_registry)) -> dict:
    try:
        approval = registry.reject_request(approval_id)
        return {
            "approval": approval,
            "tool_result": None,
            "assistant_response": (
                "Approval rejected. I did not execute the requested tool, and no action was taken."
            ),
            "model": None,
        }
    except ApprovalNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ApprovalStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
