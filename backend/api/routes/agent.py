from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent.direct_runner import run_direct_agent
from agent.langgraph_runner import (
    LangGraphUnavailableError,
    ServiqGraphRuntimeError,
    run_langgraph_agent,
)
from core.config import Settings, get_settings
from core.logging import get_logger
from llm.lmstudio_client import LMStudioAPIError, LMStudioClient, LMStudioConnectionError
from schemas.agent import AgentHealthResponse, AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/agent", tags=["agent"])
logger = get_logger(__name__)


def get_lmstudio_client(settings: Settings = Depends(get_settings)) -> LMStudioClient:
    return LMStudioClient(
        base_url=settings.lmstudio_base_url,
        api_key=settings.lmstudio_api_key,
        timeout_seconds=settings.lmstudio_timeout_seconds,
    )


async def resolve_model(requested_model: str | None, client: LMStudioClient) -> str:
    if requested_model:
        return requested_model

    models = await client.list_models()

    if not models:
        raise HTTPException(
            status_code=503,
            detail="No LM Studio models are available. Load a model in LM Studio first.",
        )

    model_id = models[0].get("id")

    if not isinstance(model_id, str) or not model_id:
        raise HTTPException(
            status_code=503,
            detail="LM Studio returned models, but no valid model id was found.",
        )

    return model_id


@router.get("/health", response_model=AgentHealthResponse)
async def agent_health() -> AgentHealthResponse:
    return AgentHealthResponse(
        status="ok",
        runtime="langgraph",
        stage="process-11-conversation-recall",
        graph_nodes=[
            "prepare_context",
            "classify_request",
            "retrieve_memory",
            "recall_conversation",
            "run_task_loop",
            "call_local_model",
            "save_conversation",
            "finalize_response",
        ],
    )


@router.post("/run", response_model=AgentRunResponse)
async def run_agent(
    request: AgentRunRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> AgentRunResponse:
    model = await resolve_model(request.model, client)
    history = [message.model_dump() for message in request.history]

    try:
        result = await run_langgraph_agent(
            lmstudio_client=client,
            session_id=request.session_id,
            model=model,
            user_message=request.message,
            history=history,
        )

        return AgentRunResponse(**result)

    except (LangGraphUnavailableError, ServiqGraphRuntimeError) as exc:
        logger.exception("agent_langgraph_error", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"LangGraph agent error: {type(exc).__name__}: {exc}",
        ) from exc

    except (LMStudioConnectionError, LMStudioAPIError) as exc:
        logger.exception("agent_lmstudio_error", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"LM Studio error: {type(exc).__name__}: {exc}",
        ) from exc

    except Exception as exc:  # noqa: BLE001
        logger.exception("agent_unhandled_error", error=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Unhandled agent error: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/run-direct", response_model=AgentRunResponse)
async def run_agent_direct(
    request: AgentRunRequest,
    client: LMStudioClient = Depends(get_lmstudio_client),
) -> AgentRunResponse:
    model = await resolve_model(request.model, client)

    try:
        result = await run_direct_agent(
            lmstudio_client=client,
            session_id=request.session_id,
            model=model,
            user_message=request.message,
            history=[message.model_dump() for message in request.history],
        )

        return AgentRunResponse(**result)
    except (LMStudioConnectionError, LMStudioAPIError) as exc:
        logger.exception("agent_direct_lmstudio_error", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"LM Studio error: {type(exc).__name__}: {exc}",
        ) from exc
